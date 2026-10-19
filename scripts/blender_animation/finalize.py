"""Package the rendered teaching animation and record inspectable media evidence."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'build/blender-pwm-animation'
OUT = ROOT / 'docs/research/blender-pwm-animation-20261018'
EV = ROOT / 'evidence/blender-pwm-animation'
EV.mkdir(parents=True, exist_ok=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}.{ms % 1000:03d}'


timeline = json.loads((OUT / 'timeline.json').read_text())
frames = sorted((RAW / 'frames').glob('frame_*.png'))
assert len(frames) == timeline['frames'], (len(frames), timeline['frames'])
assert [f.name for f in frames] == [f'frame_{i:04d}.png' for i in range(1, timeline['frames'] + 1)]
validation = json.loads((EV / 'validation.json').read_text())
# The independent validator raises on any failed check. Retain its full report.
assert validation.get('passed') is True and validation.get('failed_count') == 0
video = OUT / 'animation.mp4'
probe = json.loads(subprocess.check_output([
    '/opt/homebrew/bin/ffprobe', '-v', 'error', '-show_streams', '-show_format', '-show_chapters', '-of', 'json', str(video)
]))
vs = next(s for s in probe['streams'] if s['codec_type'] == 'video')
assert (vs['width'], vs['height']) == (1920, 1080)
assert vs['avg_frame_rate'] == '24/1'
assert int(vs['nb_frames']) == timeline['frames']
assert abs(float(probe['format']['duration']) - timeline['duration_s']) < 0.01
assert len(probe['chapters']) == len(timeline['chapters'])
for actual, expected in zip(probe['chapters'], timeline['chapters']):
    assert actual['tags']['title'] == expected['title']
    assert abs(float(actual['start_time']) - (expected['start_frame'] - 1) / timeline['fps']) < 0.001
with (RAW / 'decode.log').open('w') as log:
    subprocess.run(['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'], check=True, stdout=log, stderr=log)
assert (RAW / 'decode.log').stat().st_size == 0
shutil.copy2(RAW / 'preview/0720.png', OUT / 'poster.png')
shutil.copy2(RAW / 'fonts/LICENSE.txt', OUT / 'Noto-OFL.txt')
shutil.copy2(RAW / 'mapping.json', OUT / 'mapping.json')
shutil.copy2(RAW / 'mapping.json', EV / 'mapping.json')
shutil.copy2(RAW / 'mapping-notes.md', EV / 'mapping-notes.md')
shutil.copy2(EV / 'validation.json', OUT / 'validation.json')
vtt = ['WEBVTT', '']
for c in timeline['chapters']:
    vtt.extend([f"{stamp((c['start_frame'] - 1) / timeline['fps'])} --> {stamp(c['end_frame'] / timeline['fps'])}", c['title'], c['caption'], ''])
(OUT / 'chapters-zh.vtt').write_text('\n'.join(vtt))
artifacts = [p for p in OUT.rglob('*') if p.is_file() and p.suffix != '.blend1' and p.name != 'media-validation.json']
evidence = {
    'status': 'pass',
    'scope': 'Blender artifact, media encoding and visual teaching checks; no new circuit, optical or manufacturing qualification.',
    'resolution': [vs['width'], vs['height']],
    'fps': vs['avg_frame_rate'], 'frames': int(vs['nb_frames']),
    'duration_s': float(probe['format']['duration']),
    'codec': vs['codec_name'], 'pixel_format': vs['pix_fmt'],
    'embedded_chapters': len(probe['chapters']),
    'full_decode_errors': 0,
    'source_gds_sha256': json.loads((RAW / 'mapping.json').read_text())['gds_sha256'],
    'artifacts': {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(artifacts)},
    'scripts': {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / 'scripts/blender_animation').glob('*.py'))},
    'font': {'family': 'Noto Sans CJK SC', 'license': 'SIL Open Font License 1.1', 'sha256': sha(RAW / 'fonts/NotoSansCJKsc-Regular.otf'), 'license_sha256': sha(OUT / 'Noto-OFL.txt')},
    'visual_review_frames': [1, 144, 384, 500, 650, 720, 948, 1040, 1188, 1280, 1490],
    'limitations': [
        'XY comes from r5 GDS; nominal Z is exaggerated by 12 and layer explosion is an additional teaching displacement.',
        'Paths are camera-projected annotations of audited centre lines; channel interpolation and off-chip LED connections are schematic.',
        'Arrows represent conventional current direction; their speed/width does not encode current, delay or charge.',
        'State transitions are slowed teaching scenes; no simulated transient tail, current density, dielectric stack or optical power is shown.',
        'The reference and supply network are cropped in the pixel view; actual BIAS/VSS ports lie outside the crop.'
    ]
}
(EV / 'media-validation.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
shutil.copy2(EV / 'media-validation.json', OUT / 'media-validation.json')
print(json.dumps({'status': 'pass', 'frames': evidence['frames'], 'duration_s': evidence['duration_s'], 'mp4_bytes': video.stat().st_size}, ensure_ascii=False))
