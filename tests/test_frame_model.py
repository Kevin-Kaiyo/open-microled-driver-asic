"""Independent frame integrity, adversarial state and quantization checks."""
from fractions import Fraction
import hashlib
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from control.frame_model import (Frame, FrameError, FrameReceiver, code_to_duty,
                                 decode_frame, encode_frame, pack_codes, unpack_codes)


def independent_crc32(data: bytes) -> int:
    """Bitwise reflected IEEE CRC; deliberately does not call model or zlib."""
    crc = 0xFFFFFFFF
    for octet in data:
        crc ^= octet
        for _ in range(8):
            crc = (crc >> 1) ^ (0xEDB88320 if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


def repaired_crc(data: bytes) -> bytes:
    return data[:-4] + struct.pack(">I", independent_crc32(data[:-4]))


def receiver(**kwargs) -> FrameReceiver:
    defaults = dict(pixel_count=3, boundary_period_ns=100,
                    command_timeout_ns=1000, receive_timeout_ns=50)
    defaults.update(kwargs)
    return FrameReceiver(**defaults)


class FrameIntegrityTests(unittest.TestCase):
    def test_fixed_external_crc_vector_and_wire_golden(self):
        self.assertEqual(independent_crc32(b"123456789"), 0xCBF43926)
        golden = bytes.fromhex(
            "4d4c4558010c000100000001000000000000000000000002010001568c54")
        frame = Frame(1, 0, (16,))
        self.assertEqual(encode_frame(frame), golden)
        self.assertEqual(decode_frame(golden, 1), frame)
        self.assertEqual(independent_crc32(golden[:-4]),
                         int.from_bytes(golden[-4:], "big"))

    def test_msb_first_nibbles_and_zero_padding(self):
        codes = (0, 2048, 4095)
        self.assertEqual(pack_codes(codes), bytes.fromhex("000800fff0"))
        self.assertEqual(unpack_codes(bytes.fromhex("000800fff0"), 3), codes)
        self.assertEqual(pack_codes((4095, 0)), bytes.fromhex("fff000"))

    def test_all_codes_have_bounded_independent_quantization_error(self):
        duties = [code_to_duty(code) for code in range(4096)]
        self.assertEqual(duties[0], 0)
        self.assertEqual(duties[-1], 256)
        self.assertEqual(len(set(duties)), 257)
        self.assertEqual(duties, sorted(duties))
        for code, duty in enumerate(duties):
            self.assertLessEqual(abs(Fraction(duty, 256) - Fraction(code, 4095)),
                                 Fraction(1, 512))
        self.assertEqual([code_to_duty(v) for v in (0, 16, 1024, 2048, 4079, 4095)],
                         [0, 1, 64, 128, 255, 256])

    def test_invalid_code_and_metadata_not_silently_clamped(self):
        for value in (-1, 4096, 0.5, True):
            with self.assertRaises(ValueError):
                code_to_duty(value)
        with self.assertRaises(ValueError):
            Frame(2**32, 0, (0,))
        with self.assertRaises(ValueError):
            Frame(0, -1, (0,))

    def test_predefined_malformed_frames(self):
        wire = encode_frame(Frame(1, 0, (0, 2048, 4095)))
        malformed = {
            "partial_header": wire[:10],
            "partial_frame": wire[:-1],
            "extra_bytes": wire + b"\x00",
            "wrong_magic": b"FAIL" + wire[4:],
            "wrong_version": wire[:4] + b"\x02" + wire[5:],
            "wrong_code_width": wire[:5] + b"\x08" + wire[6:],
            "wrong_pixel_count": wire[:6] + b"\x00\x00" + wire[8:],
            "wrong_payload_length": wire[:20] + b"\x00\x00\x00\x04" + wire[24:],
            "bad_crc": wire[:-1] + bytes([wire[-1] ^ 1]),
            "nonzero_padding": repaired_crc(wire[:28] + bytes([wire[28] | 1]) + wire[29:]),
        }
        for expected, packet in malformed.items():
            with self.subTest(expected=expected):
                with self.assertRaises(FrameError) as error:
                    decode_frame(packet, 3)
                self.assertEqual(error.exception.reason, expected)

    def test_crc_every_single_bit_error_in_header_and_payload(self):
        wire = encode_frame(Frame(4, 2, (16, 2048, 4079)))
        for byte_index in range(len(wire) - 4):
            for bit in range(8):
                damaged = bytearray(wire)
                damaged[byte_index] ^= 1 << bit
                with self.assertRaises(FrameError):
                    decode_frame(bytes(damaged), 3)


class AtomicCommitTests(unittest.TestCase):
    def test_partial_then_atomic_commit_and_snapshot_independence(self):
        model = receiver()
        mutable_codes = [16, 2048, 4095]
        frame = Frame(1, 5, mutable_codes)
        wire = encode_frame(frame)
        mutable_codes[1] = 0
        self.assertIsNone(model.receive_chunk(wire[:11], 10))
        self.assertEqual(model.active_codes, (0, 0, 0))
        accepted = model.receive_chunk(wire[11:], 30, end=True)
        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.commit_time_ns, 100)
        model.advance(99)
        self.assertEqual(model.active_codes, (0, 0, 0))
        model.advance(100)
        self.assertEqual(model.active_codes, (16, 2048, 4095))
        self.assertEqual(model.active_duties, (1, 128, 256))
        self.assertEqual(model.active_payload_sha256,
                         hashlib.sha256(bytes.fromhex("010800fff0")).hexdigest())

    def test_origin_and_exact_boundary_strictly_next(self):
        model = receiver(pixel_count=1, boundary_origin_ns=2000,
                         boundary_period_ns=256000, command_timeout_ns=3000000)
        first = model.receive(encode_frame(Frame(1, 0, (1024,))), 1000)
        self.assertEqual(first.commit_time_ns, 2000)
        model.advance(2000)
        exact = model.receive(encode_frame(Frame(2, 2000, (2048,))), 2000)
        self.assertEqual(exact.commit_time_ns, 258000)
        model.advance(257999)
        self.assertEqual(model.active_codes, (1024,))
        model.advance(258000)
        self.assertEqual(model.active_codes, (2048,))

    def test_newest_valid_pending_supersedes_without_partial_active_change(self):
        model = receiver()
        model.receive(encode_frame(Frame(1, 10, (1, 2, 3))), 10)
        model.receive(encode_frame(Frame(2, 20, (4, 5, 6))), 20)
        model.advance(100)
        self.assertEqual(model.active_frame_id, 2)
        self.assertEqual(model.active_codes, (4, 5, 6))
        self.assertEqual([event["frame_id"] for event in model.events
                          if event["event"] == "frame_committed"], [2])

    def test_duplicate_out_of_order_future_and_stale_have_predefined_results(self):
        model = receiver()
        model.receive(encode_frame(Frame(10, 10, (4, 5, 6))), 10)
        cases = [(10, 20, 20, "duplicate_id"), (9, 20, 20, "out_of_order_id"),
                 (11, 31, 30, "future_timestamp"),
                 (11, 0, 1000, "expired_before_commit")]
        for frame_id, stamp, arrival, reason in cases:
            result = model.receive(encode_frame(Frame(frame_id, stamp, (7, 8, 9))), arrival)
            self.assertFalse(result.accepted)
            self.assertEqual(result.reason, reason)
        self.assertEqual(model.last_accepted_frame_id, 10)

    def test_timeout_waits_for_boundary_and_cannot_replay_id_after_expiry(self):
        model = receiver(command_timeout_ns=250)
        model.receive(encode_frame(Frame(1, 10, (16, 2048, 4095))), 10)
        model.advance(299)
        self.assertEqual(model.active_frame_id, 1)
        model.advance(300)
        self.assertEqual(model.active_codes, (0, 0, 0))
        self.assertIsNone(model.active_frame_id)
        result = model.receive(encode_frame(Frame(1, 300, (1, 2, 3))), 300)
        self.assertEqual(result.reason, "duplicate_id")
        timeout = [event for event in model.events if event["event"] == "command_timeout"]
        self.assertEqual([event["time_ns"] for event in timeout], [300])

    def test_same_boundary_new_commit_wins_without_intermediate_clear(self):
        model = receiver(command_timeout_ns=250)
        model.receive(encode_frame(Frame(1, 10, (1, 2, 3))), 10)
        model.advance(100)
        model.receive(encode_frame(Frame(2, 290, (4, 5, 6))), 290)
        model.advance(300)
        self.assertEqual(model.active_frame_id, 2)
        self.assertFalse(any(event["event"] == "command_timeout" for event in model.events))

    def test_assembly_timeout_discards_and_complete_receive_cannot_mix(self):
        model = receiver()
        wire = encode_frame(Frame(1, 0, (1, 2, 3)))
        model.receive_chunk(wire[:7], 10)
        self.assertEqual(model.receive(wire, 20).reason, "receiver_busy")
        model.advance(59)
        self.assertFalse(any(event["event"] == "receive_timeout" for event in model.events))
        model.advance(60)
        self.assertEqual(model.active_codes, (0, 0, 0))
        self.assertEqual(model.events[-1]["received_bytes"], 7)
        self.assertTrue(model.receive(wire, 61).accepted)

    def test_bad_transactions_do_not_change_clean_commit_timeline(self):
        clean, dirty = receiver(), receiver()
        first = encode_frame(Frame(1, 10, (16, 1024, 2048)))
        second = encode_frame(Frame(2, 150, (0, 4079, 4095)))
        for model in (clean, dirty):
            model.receive(first, 10)
        dirty.receive(first[:-1], 20)
        corrupted = bytearray(first)
        corrupted[25] ^= 1
        dirty.receive(bytes(corrupted), 30)
        dirty.receive(first, 40)
        dirty.receive(encode_frame(Frame(0, 50, (1, 2, 3))), 50)
        for model in (clean, dirty):
            model.receive(second, 150)
            model.advance(250)
        def commits(model):
            return [event for event in model.events if event["event"] == "frame_committed"]
        self.assertEqual(commits(clean), commits(dirty))
        self.assertEqual(clean.active_codes, dirty.active_codes)

    def test_large_time_jump_preserves_event_order_and_monotonic_clock(self):
        model = receiver(command_timeout_ns=250)
        model.receive(encode_frame(Frame(1, 10, (1, 2, 3))), 10)
        model.advance(1000000)
        state_events = [event for event in model.events
                        if event["event"] in ("frame_committed", "command_timeout")]
        self.assertEqual([(event["event"], event["time_ns"]) for event in state_events],
                         [("frame_committed", 100), ("command_timeout", 300)])
        with self.assertRaises(ValueError):
            model.advance(999999)


if __name__ == "__main__":
    unittest.main()
