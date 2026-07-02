"""Smooth Ken Burns motion for static images using FFmpeg zoompan."""

import filecmp
import subprocess
from datetime import datetime
from pathlib import Path

# Gentle effects — subtle movement reads more professional than aggressive pans
EFFECTS = ["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "drift"]
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}

# Upscale before zoompan so sub-pixel pans stay smooth (standard Ken Burns trick)
UPSCALE_FILTER = "scale=4000:-2:flags=lanczos"
OUTPUT_SIZE = "1920x1080"
MAX_ZOOM = 0.10       # visible but still professional
PAN_ZOOM = 1.08
DEFAULT_MAX_SEGMENT = 7.0   # max seconds per visual beat before a cut


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] motion: {msg}")


def _format_ffmpeg_error(stderr: str) -> str:
    keywords = ("error", "invalid", "failed", "no such")
    lines = [ln for ln in stderr.splitlines() if any(k in ln.lower() for k in keywords)]
    if lines:
        return "\n".join(lines[-10:])
    return stderr[-2000:]


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {_format_ffmpeg_error(result.stderr)}")


def _ease_expr(frames: int) -> str:
    """Smoothstep ease-in-out: slow start, smooth middle, slow end."""
    denom = max(frames - 1, 1)
    t = f"on/{denom}"
    return f"({t})*({t})*(3-2*({t}))"


def _zoompan_filter(effect: str, frames: int, fps: int) -> str:
    ease = _ease_expr(frames)
    base = f"d={frames}:s={OUTPUT_SIZE}:fps={fps}"
    z_delta = MAX_ZOOM
    z_pan = PAN_ZOOM

    filters = {
        # Slow push-in toward center
        "zoom_in": (
            f"zoompan=z='1+{z_delta}*({ease})':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':{base}"
        ),
        # Slow pull-back from slight zoom
        "zoom_out": (
            f"zoompan=z='{1 + z_delta}-{z_delta}*({ease})':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':{base}"
        ),
        # Horizontal pans with gentle zoom
        "pan_left": (
            f"zoompan=z='{z_pan}':"
            f"x='(iw-iw/zoom)*({ease})':y='ih/2-(ih/zoom/2)':{base}"
        ),
        "pan_right": (
            f"zoompan=z='{z_pan}':"
            f"x='(iw-iw/zoom)*(1-({ease}))':y='ih/2-(ih/zoom/2)':{base}"
        ),
        "pan_up": (
            f"zoompan=z='{z_pan}':"
            f"x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-({ease}))':{base}"
        ),
        # Very subtle diagonal drift (documentary-style)
        "drift": (
            f"zoompan=z='1+{z_delta * 0.6}*({ease})':"
            f"x='(iw-iw/zoom)*0.35*({ease})':"
            f"y='(ih-ih/zoom)*0.2*(1-({ease}))':{base}"
        ),
    }
    return filters[effect]


def split_visual_duration(
    total_seconds: float,
    max_segment: float = DEFAULT_MAX_SEGMENT,
    min_segment: float = 3.5,
) -> list[float]:
    """Split a long scene into shorter visual beats (documentary-style pacing)."""
    total_seconds = max(total_seconds, 0.5)
    if total_seconds <= max_segment:
        return [round(total_seconds, 3)]

    segments: list[float] = []
    remaining = total_seconds
    while remaining > min_segment * 0.5:
        if remaining <= max_segment:
            segments.append(round(remaining, 3))
            break
        seg = min(max_segment, max(min_segment, remaining / 2))
        segments.append(round(seg, 3))
        remaining = round(remaining - seg, 3)

    drift = round(total_seconds - sum(segments), 3)
    if segments and abs(drift) > 0.02:
        segments[-1] = round(max(min_segment * 0.5, segments[-1] + drift), 3)
    return segments or [round(total_seconds, 3)]


def _images_are_same(main_path: str, broll_path: str) -> bool:
    """True when b-roll is missing, same path, or byte-identical to main."""
    main_p = Path(main_path)
    broll_p = Path(broll_path)
    if not broll_p.exists():
        return True
    if main_p.resolve() == broll_p.resolve():
        return True
    try:
        return filecmp.cmp(main_p, broll_p, shallow=False)
    except OSError:
        return False


def build_scene_timeline(
    duration: float,
    main_path: str,
    broll_path: str,
    *,
    use_broll: bool,
    broll_at_second: int = 5,
    max_segment: float = DEFAULT_MAX_SEGMENT,
) -> list[tuple[str, float]]:
    """
    Build ordered (image, duration) beats for one scene.
    - Single image / per-scene: split into ~7s Ken Burns segments on main only.
    - Main + b-roll: alternate main and b-roll each segment (even pacing).
    """
    segment_durations = split_visual_duration(duration, max_segment)
    same = _images_are_same(main_path, broll_path)

    if not use_broll or same:
        return [(main_path, seg) for seg in segment_durations]

    # Alternate main / b-roll every segment — no 5s flash then 40s on main
    timeline: list[tuple[str, float]] = []
    for i, seg_dur in enumerate(segment_durations):
        img = broll_path if i % 2 == 1 else main_path
        timeline.append((img, seg_dur))
    return timeline


def _concat_silent_clips(clip_paths: list[str], output_path: str, fps: int = 30) -> str:
    """Concatenate video-only clips (Ken Burns segments) with hard cuts."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if len(clip_paths) == 1:
        _run_ffmpeg(["ffmpeg", "-y", "-i", clip_paths[0], "-c:v", "copy", "-an", str(out)])
        return str(out)

    inputs: list[str] = []
    for p in clip_paths:
        inputs += ["-i", p]
    n = len(clip_paths)
    streams = "".join(f"[{i}:v]" for i in range(n))
    _run_ffmpeg([
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", f"{streams}concat=n={n}:v=1:a=0[v]",
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(fps), "-an",
        str(out),
    ])
    return str(out)


def render_scene_visual(
    timeline: list[tuple[str, float]],
    output_path: str,
    fps: int = 30,
    segment_transition: str = "cut",
) -> str:
    """Render Ken Burns segments and concatenate into one silent video."""
    if not timeline:
        raise ValueError("Empty visual timeline")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = out.parent / f".{out.stem}_segments"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    segment_paths: list[str] = []
    prev_effect: str | None = None
    for i, (image_path, seg_dur) in enumerate(timeline):
        effect = _next_effect(i, prev_effect)
        prev_effect = effect
        seg_out = tmp_dir / f"seg_{i:02d}.mp4"
        ken_burns(image_path, str(seg_out), seg_dur, effect=effect, fps=fps)
        segment_paths.append(str(seg_out))

    if segment_transition == "cut":
        return _concat_silent_clips(segment_paths, str(out), fps=fps)

    from lib.stitch import concatenate_scenes
    return concatenate_scenes(
        segment_paths,
        str(out),
        transition=segment_transition,
        transition_duration=0.35,
        fps=fps,
    )


def ken_burns(
    image_path: str,
    output_path: str,
    duration_seconds: float,
    effect: str = "zoom_in",
    fps: int = 30,
) -> str:
    if effect not in EFFECTS:
        raise ValueError(f"Unknown effect: {effect}. Must be one of {EFFECTS}")

    duration_seconds = max(duration_seconds, 0.1)
    frames = max(int(round(duration_seconds * fps)), 2)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    zoompan = _zoompan_filter(effect, frames, fps)
    vf = f"{UPSCALE_FILTER},{zoompan},format=yuv420p"

    _log(f"ken_burns {effect} ({duration_seconds:.1f}s, {frames}f) -> {out.name}")
    _run_ffmpeg([
        "ffmpeg", "-y", "-loop", "1", "-i", image_path,
        "-vf", vf,
        "-frames:v", str(frames),
        "-c:v", "libx264", "-preset", "medium", "-crf", "17",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-movflags", "+faststart", "-an", str(out),
    ])
    return str(out)


def apply_random_motion(
    image_path: str,
    output_path: str,
    duration_seconds: float,
    fps: int = 30,
) -> str:
    import random
    effect = random.choice(EFFECTS)
    return ken_burns(image_path, output_path, duration_seconds, effect=effect, fps=fps)


def _next_effect(index: int, prev_effect: str | None) -> str:
    # Alternate zoom and pan so motion doesn't feel repetitive
    preferred = ["zoom_in", "pan_right", "zoom_out", "pan_left", "drift", "pan_up"]
    effect = preferred[index % len(preferred)]
    if prev_effect and effect == prev_effect:
        effect = preferred[(index + 1) % len(preferred)]
    return effect


def apply_motion_batch(
    image_paths: list[str],
    output_dir: str,
    durations: list[float],
    fps: int = 30,
) -> list[str]:
    if len(image_paths) != len(durations):
        raise ValueError("image_paths and durations must have the same length")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[str] = []
    prev_effect: str | None = None
    total = len(image_paths)

    for i, (image_path, duration) in enumerate(zip(image_paths, durations)):
        effect = _next_effect(i, prev_effect)
        prev_effect = effect
        stem = Path(image_path).stem
        out_path = out_dir / f"{stem}_motion.mp4"
        _log(f"Applying motion {i + 1}/{total}: {effect}")
        ken_burns(image_path, str(out_path), duration, effect=effect, fps=fps)
        results.append(str(out_path))

    return results


def add_particle_overlay(
    video_path: str,
    output_path: str,
    particle_type: str = "dust",
) -> str:
    filters = {
        "dust": "noise=alls=8:allf=t",
        "bokeh": "gblur=sigma=2,eq=brightness=0.05:saturation=1.3",
        "light_leak": "colorbalance=rs=0.08:gs=0.04:bs=-0.02,eq=brightness=0.03",
    }
    if particle_type not in filters:
        raise ValueError(f"Unknown particle_type: {particle_type}. Must be dust, bokeh, or light_leak")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _log(f"Adding {particle_type} overlay -> {out.name}")
    _run_ffmpeg([
        "ffmpeg", "-y", "-i", video_path,
        "-vf", filters[particle_type],
        "-c:a", "copy", str(out),
    ])
    return str(out)
