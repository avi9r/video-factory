"""Professional motion effects for static images using FFmpeg."""

import random
import subprocess
from datetime import datetime
from pathlib import Path

EFFECTS = ["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "diagonal"]
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}


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


def _zoompan_filter(effect: str, frames: int, fps: int) -> str:
    base = f"d={frames}:s=1920x1080:fps={fps}"
    filters = {
        "zoom_in": (
            f"zoompan=z='min(zoom+0.0015,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':{base}"
        ),
        "zoom_out": (
            f"zoompan=z='if(lte(zoom,1.0),1.15,max(1.001,zoom-0.0015))':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':{base}"
        ),
        "pan_left": (
            f"zoompan=z=1.15:x='(iw-iw/zoom)*on/{frames}':y='(ih-ih/zoom)/2':{base}"
        ),
        "pan_right": (
            f"zoompan=z=1.15:x='(iw-iw/zoom)*(1-on/{frames})':y='(ih-ih/zoom)/2':{base}"
        ),
        "pan_up": (
            f"zoompan=z=1.15:x='(iw-iw/zoom)/2':y='(ih-ih/zoom)*(1-on/{frames})':{base}"
        ),
        "diagonal": (
            f"zoompan=z='min(zoom+0.001,1.15)':x='(iw-iw/zoom)*on/{frames}':"
            f"y='(ih-ih/zoom)*(1-on/{frames})':{base}"
        ),
    }
    return filters[effect]


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
    frames = max(int(duration_seconds * fps), 1)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    scale = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"
    zoompan = _zoompan_filter(effect, frames, fps)
    vf = f"{scale},{zoompan}"

    _log(f"ken_burns {effect} ({duration_seconds:.1f}s) -> {out.name}")
    _run_ffmpeg([
        "ffmpeg", "-y", "-loop", "1", "-i", image_path,
        "-vf", vf,
        "-t", str(duration_seconds),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", str(fps), "-an", str(out),
    ])
    return str(out)


def apply_random_motion(
    image_path: str,
    output_path: str,
    duration_seconds: float,
    fps: int = 30,
) -> str:
    effect = random.choice(EFFECTS)
    return ken_burns(image_path, output_path, duration_seconds, effect=effect, fps=fps)


def _next_effect(index: int, prev_effect: str | None) -> str:
    effect = EFFECTS[index % len(EFFECTS)]
    if prev_effect and effect == prev_effect:
        effect = EFFECTS[(index + 1) % len(EFFECTS)]
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
