"""Independent frame/commit experiment; this is a functional model, not RTL.

The complete contract is docs/specifications/frame-experiment-v0.1.md.
All times are integer nanoseconds in one declared monotonic experiment clock.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import struct
from typing import Iterable
import zlib


MAGIC = b"MLEX"
VERSION = 1
CODE_WIDTH = 12
MAX_CODE = 4095
MAX_DUTY = 256
HEADER = struct.Struct(">4sBBHIQI")
CRC = struct.Struct(">I")


def _integer(value: int, minimum: int, maximum: int, name: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in {minimum}..{maximum}")
    return value


def code_to_duty(code: int) -> int:
    """Nearest 0..256 duty; exact off/full-on and no extra PWM resolution."""
    _integer(code, 0, MAX_CODE, "code")
    return (code * MAX_DUTY + MAX_CODE // 2) // MAX_CODE


def pack_codes(codes: Iterable[int]) -> bytes:
    """Pack codes MSB first, with zero bits padding the final byte."""
    accumulator = bits = 0
    output = bytearray()
    for code in codes:
        _integer(code, 0, MAX_CODE, "code")
        accumulator = (accumulator << CODE_WIDTH) | code
        bits += CODE_WIDTH
        while bits >= 8:
            bits -= 8
            output.append((accumulator >> bits) & 255)
        accumulator &= (1 << bits) - 1
    if bits:
        output.append(accumulator << (8 - bits))
    return bytes(output)


def unpack_codes(payload: bytes, count: int) -> tuple[int, ...]:
    _integer(count, 1, 65535, "count")
    expected = (count * CODE_WIDTH + 7) // 8
    if len(payload) != expected:
        raise FrameError("wrong_payload_length")
    padding = expected * 8 - count * CODE_WIDTH
    if padding and payload[-1] & ((1 << padding) - 1):
        raise FrameError("nonzero_padding")
    accumulator = bits = 0
    output: list[int] = []
    for octet in payload:
        accumulator = (accumulator << 8) | octet
        bits += 8
        if bits >= CODE_WIDTH:
            bits -= CODE_WIDTH
            output.append((accumulator >> bits) & MAX_CODE)
            accumulator &= (1 << bits) - 1
    return tuple(output)


@dataclass(frozen=True)
class Frame:
    frame_id: int
    timestamp_ns: int
    codes: tuple[int, ...]

    def __post_init__(self) -> None:
        _integer(self.frame_id, 0, 2**32 - 1, "frame_id")
        _integer(self.timestamp_ns, 0, 2**64 - 1, "timestamp_ns")
        object.__setattr__(self, "codes", tuple(self.codes))
        _integer(len(self.codes), 1, 65535, "pixel_count")
        for code in self.codes:
            _integer(code, 0, MAX_CODE, "code")

    @property
    def payload_sha256(self) -> str:
        return hashlib.sha256(pack_codes(self.codes)).hexdigest()


class FrameError(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def encode_frame(frame: Frame) -> bytes:
    payload = pack_codes(frame.codes)
    body = HEADER.pack(MAGIC, VERSION, CODE_WIDTH, len(frame.codes),
                       frame.frame_id, frame.timestamp_ns, len(payload)) + payload
    return body + CRC.pack(zlib.crc32(body) & 0xFFFFFFFF)


def decode_frame(wire: bytes, expected_pixels: int | None = None) -> Frame:
    """Reject malformed data before it can enter the pending/active state."""
    if len(wire) < HEADER.size:
        raise FrameError("partial_header")
    magic, version, width, count, frame_id, timestamp, length = HEADER.unpack_from(wire)
    if magic != MAGIC:
        raise FrameError("wrong_magic")
    if version != VERSION:
        raise FrameError("wrong_version")
    if width != CODE_WIDTH:
        raise FrameError("wrong_code_width")
    if count == 0 or (expected_pixels is not None and count != expected_pixels):
        raise FrameError("wrong_pixel_count")
    if length != (count * CODE_WIDTH + 7) // 8:
        raise FrameError("wrong_payload_length")
    expected_length = HEADER.size + length + CRC.size
    if len(wire) < expected_length:
        raise FrameError("partial_frame")
    if len(wire) > expected_length:
        raise FrameError("extra_bytes")
    expected_crc = CRC.unpack_from(wire, len(wire) - CRC.size)[0]
    if zlib.crc32(wire[:-CRC.size]) & 0xFFFFFFFF != expected_crc:
        raise FrameError("bad_crc")
    return Frame(frame_id, timestamp, unpack_codes(wire[HEADER.size:-CRC.size], count))


@dataclass(frozen=True)
class ReceiveResult:
    accepted: bool
    reason: str
    accept_time_ns: int
    frame_id: int | None = None
    commit_time_ns: int | None = None
    payload_sha256: str | None = None
    wire_sha256: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class FrameReceiver:
    """One assembly, one pending frame, and one atomic active state.

    A complete valid newer frame replaces pending. Invalid transactions hold
    active. An expired active command clears codes at a declared boundary.
    No hardware interface, receiver RTL, protection circuit or optical output
    is established by this class.
    """

    def __init__(self, pixel_count: int, boundary_period_ns: int,
                 command_timeout_ns: int, receive_timeout_ns: int,
                 boundary_origin_ns: int = 0):
        self.pixel_count = _integer(pixel_count, 1, 65535, "pixel_count")
        self.boundary_period_ns = _integer(boundary_period_ns, 1, 2**64 - 1,
                                          "boundary_period_ns")
        self.boundary_origin_ns = _integer(boundary_origin_ns, 0, 2**64 - 1,
                                          "boundary_origin_ns")
        self.command_timeout_ns = _integer(command_timeout_ns, 1, 2**64 - 1,
                                          "command_timeout_ns")
        self.receive_timeout_ns = _integer(receive_timeout_ns, 1, 2**64 - 1,
                                          "receive_timeout_ns")
        self.now_ns = 0
        self.active_codes = (0,) * pixel_count
        self.active_frame_id: int | None = None
        self.active_timestamp_ns: int | None = None
        self.last_accepted_frame_id: int | None = None
        self.pending: Frame | None = None
        self.pending_commit_ns: int | None = None
        self.events: list[dict] = []
        self._assembly = bytearray()
        self._assembly_deadline_ns: int | None = None
        self._active_timeout_boundary_ns: int | None = None
        self.max_wire_bytes = HEADER.size + (pixel_count * CODE_WIDTH + 7) // 8 + CRC.size

    @property
    def active_payload_sha256(self) -> str:
        return hashlib.sha256(pack_codes(self.active_codes)).hexdigest()

    @property
    def active_duties(self) -> tuple[int, ...]:
        return tuple(code_to_duty(code) for code in self.active_codes)

    def _boundary(self, time_ns: int, strictly_after: bool) -> int:
        delta = time_ns - self.boundary_origin_ns
        if delta < 0:
            return self.boundary_origin_ns
        quotient, remainder = divmod(delta, self.boundary_period_ns)
        step = quotient + int(strictly_after or remainder != 0)
        return self.boundary_origin_ns + step * self.boundary_period_ns

    def _event(self, kind: str, time_ns: int, frame_id: int | None = None,
               reason: str | None = None, **details) -> None:
        self.events.append({"event": kind, "time_ns": time_ns,
                            "frame_id": frame_id, "reason": reason,
                            "active_payload_sha256": self.active_payload_sha256,
                            **details})

    def advance(self, now_ns: int) -> list[dict]:
        """Process due events in order; a boundary commit wins over old expiry."""
        _integer(now_ns, self.now_ns, 2**64 - 1, "now_ns")
        first_new_event = len(self.events)
        while True:
            due = [time for time in (self._assembly_deadline_ns,
                                     self.pending_commit_ns,
                                     self._active_timeout_boundary_ns)
                   if time is not None and time <= now_ns]
            if not due:
                break
            event_time = min(due)
            if self._assembly_deadline_ns == event_time:
                received_bytes = len(self._assembly)
                self._assembly.clear()
                self._assembly_deadline_ns = None
                self._event("receive_timeout", event_time, reason="partial_timeout",
                            received_bytes=received_bytes)
            if self.pending_commit_ns == event_time:
                frame = self.pending
                assert frame is not None
                self.pending = None
                self.pending_commit_ns = None
                self.active_codes = frame.codes
                self.active_frame_id = frame.frame_id
                self.active_timestamp_ns = frame.timestamp_ns
                deadline = frame.timestamp_ns + self.command_timeout_ns
                self._active_timeout_boundary_ns = self._boundary(deadline, False)
                self._event("frame_committed", event_time, frame.frame_id,
                            reason="validated_boundary", timestamp_ns=frame.timestamp_ns,
                            codes=list(frame.codes), duties=list(self.active_duties))
            if self._active_timeout_boundary_ns == event_time:
                expired_id = self.active_frame_id
                self.active_codes = (0,) * self.pixel_count
                self.active_frame_id = None
                self.active_timestamp_ns = None
                self._active_timeout_boundary_ns = None
                self._event("command_timeout", event_time, expired_id,
                            reason="clear_at_boundary", codes=list(self.active_codes),
                            duties=list(self.active_duties))
        self.now_ns = now_ns
        return self.events[first_new_event:]

    def _reject(self, reason: str, now_ns: int, wire: bytes,
                frame_id: int | None = None) -> ReceiveResult:
        result = ReceiveResult(False, reason, now_ns, frame_id,
                               wire_sha256=hashlib.sha256(wire).hexdigest())
        self._event("receive_rejected", now_ns, frame_id, reason=reason,
                    wire_sha256=result.wire_sha256)
        return result

    def _validate_and_stage(self, wire: bytes, now_ns: int) -> ReceiveResult:
        try:
            frame = decode_frame(wire, self.pixel_count)
        except FrameError as error:
            return self._reject(error.reason, now_ns, wire)
        if self.last_accepted_frame_id is not None:
            if frame.frame_id == self.last_accepted_frame_id:
                return self._reject("duplicate_id", now_ns, wire, frame.frame_id)
            if frame.frame_id < self.last_accepted_frame_id:
                return self._reject("out_of_order_id", now_ns, wire, frame.frame_id)
        if frame.timestamp_ns > now_ns:
            return self._reject("future_timestamp", now_ns, wire, frame.frame_id)
        commit_ns = self._boundary(now_ns, True)
        if frame.timestamp_ns + self.command_timeout_ns <= commit_ns:
            return self._reject("expired_before_commit", now_ns, wire, frame.frame_id)
        if self.pending is not None:
            self._event("pending_superseded", now_ns, self.pending.frame_id,
                        reason="newer_complete_frame", replacement_frame_id=frame.frame_id)
        self.pending = frame
        self.pending_commit_ns = commit_ns
        self.last_accepted_frame_id = frame.frame_id
        result = ReceiveResult(True, "validated_pending", now_ns, frame.frame_id,
                               commit_ns, frame.payload_sha256,
                               hashlib.sha256(wire).hexdigest())
        self._event("frame_accepted", now_ns, frame.frame_id,
                    reason=result.reason, commit_time_ns=commit_ns,
                    timestamp_ns=frame.timestamp_ns,
                    payload_sha256=frame.payload_sha256,
                    wire_sha256=result.wire_sha256)
        return result

    def receive(self, wire: bytes, now_ns: int) -> ReceiveResult:
        """Complete transaction shortcut; cannot interrupt a partial assembly."""
        self.advance(now_ns)
        if self._assembly_deadline_ns is not None:
            return self._reject("receiver_busy", now_ns, wire)
        return self._validate_and_stage(bytes(wire), now_ns)

    def receive_chunk(self, data: bytes, now_ns: int,
                      end: bool = False) -> ReceiveResult | None:
        """Append a transport fragment; only an explicit end validates the frame."""
        self.advance(now_ns)
        if self._assembly_deadline_ns is None and data:
            self._assembly_deadline_ns = now_ns + self.receive_timeout_ns
            self._event("assembly_started", now_ns,
                        deadline_ns=self._assembly_deadline_ns)
        self._assembly.extend(data)
        if len(self._assembly) > self.max_wire_bytes:
            wire = bytes(self._assembly)
            self._assembly.clear()
            self._assembly_deadline_ns = None
            return self._reject("extra_bytes", now_ns, wire)
        if not end:
            return None
        wire = bytes(self._assembly)
        self._assembly.clear()
        self._assembly_deadline_ns = None
        return self._validate_and_stage(wire, now_ns)
