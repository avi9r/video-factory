"""Vertical short assembly helpers (9:16)."""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from lib.audio import get_audio_duration
from lib.captions import (
    CaptionCue,
    burn_captions_on_video,
    collect_job_caption_cues,
    write_srt_file,
)
from lib.motion import ken_burns, _next_effect
from lib.stitch import concatenate_scenes, mix_background_music, final_render


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] short_video: {msg}")


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        err = result.stderr[-1500:] if result.stderr else "unknown"
        raise RuntimeError(f"FFmpeg failed: {err}")


def prepare_vertical_image(src: str, dest: str, resolution: str = "1080x1920") -> str:
    """Center-crop / pad source image to vertical resolution."""
    w, h = resolution.split("x")
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},setsar=1"
    )
    _run_ffmpeg([
        "ffmpeg", "-y", "-i", src,
        "-vf", vf,
        "-frames:v", "1",
        str(out),
    ])
    return str(out)


def clamp_duration(video_path: str, output_path: str, target_seconds: float, fps: int = 30) -> str:
    """Trim or pad (with freeze) to exact short duration."""
    target = max(1.0, float(target_seconds))
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Trim if longer; tpad freeze if shorter
    vf = f"tpad=stop_mode=clone:stop_duration=0.5,trim=duration={target},setpts=PTS-STARTPTS"
    af = f"apad=pad_dur={target},atrim=0:{target},asetpts=PTS-STARTPTS"
    _run_ffmpeg([
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"trim=duration={target},setpts=PTS-STARTPTS",
        "-af", af,
        "-r", str(fps),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-t", str(target),
        str(out),
    ])
    _ = vf
    return str(out)


def render_short_visual_clips(
    image_paths: list[str],
    durations: list[float],
    output_dir: str,
    *,
    resolution: str = "1080x1920",
    fps: int = 30,
) -> list[str]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    clips: list[str] = []
    prev = None
    for i, (img, dur) in enumerate(zip(image_paths, durations)):
        effect = _next_effect(i, prev)
        prev = effect
        dest = out_dir / f"visual_{i:02d}.mp4"
        ken_burns(img, str(dest), max(0.8, dur), effect=effect, fps=fps, output_size=resolution)
        clips.append(str(dest))
    return clips


def mux_scene(video_path: str, audio_path: str, output_path: str, fps: int = 30) -> str:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    audio_dur = get_audio_duration(audio_path)
    _run_ffmpeg([
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-filter_complex",
        f"[0:v]trim=duration={audio_dur},setpts=PTS-STARTPTS[v];"
        f"[1:a]atrim=0:{audio_dur},asetpts=PTS-STARTPTS[a]",
        "-map", "[v]", "-map", "[a]",
        "-r", str(fps),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(out),
    ])
    return str(out)


def assemble_short_video(
    *,
    scene_videos: list[str],
    audio_dir: Path,
    scene_ids: list[str],
    channel_config: dict,
    music_path: str | None,
    output_dir: Path,
    target_seconds: int,
    quiet_music: bool = False,
) -> dict:
    """Concatenate scenes, mix music, burn captions, clamp duration."""
    fps = int(channel_config.get("video", {}).get("fps", 30))
    resolution = channel_config.get("resolution") or channel_config.get("video", {}).get(
        "resolution", "1080x1920"
    )
    blocks = output_dir / "blocks"
    blocks.mkdir(parents=True, exist_ok=True)

    concat_path = str(blocks / "concat.mp4")
    concatenate_scenes(scene_videos, concat_path, transition="crossfade", transition_duration=0.25, fps=fps)

    mixed = concat_path
    if music_path and not quiet_music:
        music_out = str(blocks / "with_music.mp4")
        vol = float(channel_config.get("music", {}).get("volume", 0.11))
        mix_background_music(concat_path, music_path, music_out, volume=vol)
        mixed = music_out

    cues = collect_job_caption_cues(scene_ids, audio_dir)
    srt_path = output_dir / "captions.srt"
    write_srt_file(cues, srt_path)

    captioned = str(blocks / "captioned.mp4")
    # Ensure ASS playres matches vertical
    cfg = dict(channel_config)
    caps = dict(cfg.get("captions") or {})
    caps.setdefault("play_res_x", 1080)
    caps.setdefault("play_res_y", 1920)
    cfg["captions"] = caps
    burn_captions_on_video(mixed, cues, captioned, cfg)

    rendered = str(blocks / "rendered.mp4")
    final_render(captioned, rendered, resolution=resolution, fps=fps)

    final_path = str(output_dir / "final_short.mp4")
    clamp_duration(rendered, final_path, target_seconds, fps=fps)

    return {
        "final_video": final_path,
        "captions_srt": str(srt_path),
        "cues": len(cues),
    }
