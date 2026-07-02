"""FFmpeg video assembly and stitching."""

import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from lib.audio import get_audio_duration
from lib.color_grade import apply_lut
from lib.music import get_music_for_act
from lib.text_overlay import create_intro_card, create_title_card


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] stitch: {msg}")


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


def _encode_flags(fps: int = 30) -> list[str]:
    return ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k"]


def _is_video(path: str) -> bool:
    return Path(path).suffix.lower() in {".mp4", ".mov", ".webm", ".mkv"}


def create_scene_video(
    image_path: str,
    broll_path: str,
    audio_path: str,
    output_path: str,
    broll_at_second: int = 5,
    transition: str = "crossfade",
    use_broll: bool = True,
    fps: int = 30,
    max_segment_seconds: float = 7.0,
) -> str:
    """
    Build one scene: multiple Ken Burns segments (hard cuts), then mux narration audio.
    Avoids b-roll overlay glitches and keeps visuals changing every few seconds.
    """
    from lib.motion import build_scene_timeline, render_scene_visual, split_visual_duration

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    duration = max(get_audio_duration(audio_path), 1.0)
    timeline = build_scene_timeline(
        duration,
        image_path,
        broll_path,
        use_broll=use_broll,
        broll_at_second=broll_at_second,
        max_segment=max_segment_seconds,
    )
    beat_count = len(timeline)
    _log(
        f"Creating scene video ({duration:.1f}s, {beat_count} beats, "
        f"broll={'yes' if use_broll else 'no'}) -> {Path(output_path).name}"
    )

    # Normalize segment lengths to match audio exactly
    total_planned = sum(seg for _, seg in timeline)
    if total_planned > 0 and abs(total_planned - duration) > 0.05:
        ratio = duration / total_planned
        timeline = [(img, round(seg * ratio, 3)) for img, seg in timeline]
        drift = round(duration - sum(seg for _, seg in timeline), 3)
        if timeline and abs(drift) > 0.01:
            img, last = timeline[-1]
            timeline[-1] = (img, round(last + drift, 3))

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        visual_path = tmp / "visual.mp4"
        render_scene_visual(timeline, str(visual_path), fps=fps, segment_transition="cut")

        _run_ffmpeg([
            "ffmpeg", "-y",
            "-i", str(visual_path),
            "-i", audio_path,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(duration),
            "-shortest",
            output_path,
        ])

    return output_path


def _probe_duration(path: str) -> float:
    probe = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(json.loads(probe.stdout)["format"]["duration"])


def concatenate_scenes(
    scene_paths: list[str],
    output_path: str,
    transition: str = "crossfade",
    transition_duration: float = 0.5,
    fps: int = 30,
) -> str:
    if not scene_paths:
        raise ValueError("No scene paths provided")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if len(scene_paths) == 1:
        _run_ffmpeg(["ffmpeg", "-y", "-i", scene_paths[0], "-c", "copy", output_path])
        return output_path

    if transition == "cut":
        _log(f"Concatenating {len(scene_paths)} scenes (cut)")
        inputs: list[str] = []
        for p in scene_paths:
            inputs += ["-i", str(p)]
        n = len(scene_paths)
        streams = "".join(f"[{i}:v][{i}:a]" for i in range(n))
        filter_complex = f"{streams}concat=n={n}:v=1:a=1[v][a]"
        _run_ffmpeg([
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            *_encode_flags(fps),
            output_path,
        ])
        return output_path

    if transition == "crossfade":
        _log(f"Concatenating {len(scene_paths)} scenes (crossfade)")
        durations = []
        for p in scene_paths[:-1]:
            durations.append(_probe_duration(p))

        inputs: list[str] = []
        for p in scene_paths:
            inputs += ["-i", str(p)]

        n = len(scene_paths)
        filter_parts = []
        offset = 0.0

        for i in range(n - 1):
            offset += durations[i] - transition_duration
            if i == 0:
                va = "[0:v]"
                aa = "[0:a]"
            else:
                va = f"[vx{i}]"
                aa = f"[ax{i}]"

            vb = f"[{i + 1}:v]"
            ab = f"[{i + 1}:a]"

            vout = f"[vx{i + 1}]" if i < n - 2 else "[vout]"
            aout = f"[ax{i + 1}]" if i < n - 2 else "[aout]"

            filter_parts.append(
                f"{va}{vb}xfade=transition=fade:"
                f"duration={transition_duration}:offset={offset:.3f}{vout}"
            )
            filter_parts.append(
                f"{aa}{ab}acrossfade=d={transition_duration}{aout}"
            )

        filter_complex = ";".join(filter_parts)

        _run_ffmpeg([
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            *_encode_flags(fps),
            output_path,
        ])
        return output_path

    raise ValueError(f"Unknown transition: {transition}")


def add_act_transition(
    video_path: str,
    act_title: str,
    channel_config: dict,
    output_path: str,
    fps: int = 30,
) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        card = tmp / "act_card.png"
        card_video = tmp / "act_card.mp4"
        create_title_card(act_title, channel_config, str(card))
        card_dur = 2.0
        _run_ffmpeg([
            "ffmpeg", "-y", "-loop", "1", "-i", str(card),
            "-c:v", "libx264", "-t", str(card_dur), "-pix_fmt", "yuv420p",
            "-r", str(fps), "-vf", "scale=1920:1080", "-an", str(card_video),
        ])
        main_dur = _probe_duration(video_path)
        total_dur = main_dur + card_dur
        _run_ffmpeg([
            "ffmpeg", "-y", "-i", video_path, "-i", str(card_video),
            "-filter_complex",
            f"[0:v][1:v]concat=n=2:v=1:a=0[v];[0:a]apad=whole_dur={total_dur}[a]",
            "-map", "[v]", "-map", "[a]",
            *_encode_flags(fps),
            output_path,
        ])
    return output_path


def mix_background_music(
    video_path: str,
    music_path: str,
    output_path: str,
    music_volume: float = 0.12,
    fade_in: float = 2.0,
    fade_out: float = 3.0,
) -> str:
    if not music_path or not Path(music_path).exists():
        subprocess.run(["ffmpeg", "-y", "-i", video_path, "-c", "copy", output_path], check=True)
        return output_path

    _log("Mixing background music")
    duration = _probe_duration(video_path)
    fade_out_start = max(0.0, duration - fade_out)

    _run_ffmpeg([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-stream_loop", "-1",
        "-i", str(music_path),
        "-filter_complex",
        f"[1:a]volume={music_volume},"
        f"afade=t=in:st=0:d={fade_in},"
        f"afade=t=out:st={fade_out_start}:d={fade_out}[music];"
        f"[0:a][music]amix=inputs=2:duration=first[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        str(output_path),
    ])
    return output_path


def add_intro_outro(
    video_path: str,
    channel_config: dict,
    output_path: str,
    fps: int = 30,
) -> str:
    intro_dur = 3.0
    outro_dur = 5.0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        intro_card = tmp / "intro.png"
        outro_card = tmp / "outro.png"
        intro_vid = tmp / "intro.mp4"
        outro_vid = tmp / "outro.mp4"
        create_intro_card(channel_config, str(intro_card))
        outro_text = channel_config.get("script", {}).get("outro_text", "Subscribe for more")
        create_title_card(outro_text, channel_config, str(outro_card))
        for card, vid, dur in [(intro_card, intro_vid, intro_dur), (outro_card, outro_vid, outro_dur)]:
            _run_ffmpeg([
                "ffmpeg", "-y", "-loop", "1", "-i", str(card),
                "-c:v", "libx264", "-t", str(dur), "-pix_fmt", "yuv420p",
                "-r", str(fps), "-vf", "scale=1920:1080", "-an", str(vid),
            ])
        main_dur = _probe_duration(video_path)
        total_dur = intro_dur + main_dur + outro_dur
        _run_ffmpeg([
            "ffmpeg", "-y",
            "-i", str(intro_vid), "-i", video_path, "-i", str(outro_vid),
            "-filter_complex",
            f"[0:v][1:v][2:v]concat=n=3:v=1:a=0[v];[1:a]apad=whole_dur={total_dur}[a]",
            "-map", "[v]", "-map", "[a]",
            *_encode_flags(fps),
            output_path,
        ])
    return output_path


def final_render(
    video_path: str,
    output_path: str,
    resolution: str = "1920x1080",
    fps: int = 30,
) -> str:
    w, h = resolution.split("x")
    _log(f"Final render -> {output_path}")
    _run_ffmpeg([
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"scale={w}:{h}",
        "-r", str(fps), "-c:v", "libx264", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
        output_path,
    ])
    return output_path
