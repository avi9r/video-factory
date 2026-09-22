"""Caption timing, ASS/SRT export, and FFmpeg burn-in."""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from lib.audio import get_audio_duration


@dataclass
class CaptionCue:
    text: str
    start: float
    end: float


def _log(msg: str) -> None:
    from datetime import datetime

    print(f"[{datetime.now().strftime('%H:%M:%S')}] captions: {msg}")


def split_narration_units(text: str, max_words: int = 16) -> list[str]:
    """Split narration into TTS/caption units (sentences, then comma chunks)."""
    text = re.sub(r"\s+", " ", str(text or "").strip())
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)
    units: list[str] = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        words = sentence.split()
        if len(words) <= max_words:
            units.append(sentence)
            continue
        parts = re.split(r"(?<=[,;])\s+", sentence)
        chunk: list[str] = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if len(part.split()) <= max_words:
                if chunk:
                    units.append(" ".join(chunk))
                    chunk = []
                units.append(part)
            else:
                chunk.extend(part.split())
                while len(chunk) > max_words:
                    units.append(" ".join(chunk[:max_words]))
                    chunk = chunk[max_words:]
        if chunk:
            units.append(" ".join(chunk))
    return units


def estimate_timings_proportional(text: str, duration: float) -> list[CaptionCue]:
    units = split_narration_units(text)
    if not units or duration <= 0:
        return []
    weights = [max(1, len(u.split())) for u in units]
    total = sum(weights)
    cues: list[CaptionCue] = []
    t = 0.0
    for unit, weight in zip(units, weights):
        seg = duration * (weight / total)
        cues.append(CaptionCue(text=unit.strip(), start=t, end=t + seg))
        t += seg
    if cues:
        cues[-1].end = duration
    return cues


def save_scene_timings(audio_dir: Path, scene_id: str, cues: list[CaptionCue]) -> str:
    audio_dir.mkdir(parents=True, exist_ok=True)
    path = audio_dir / f"{scene_id}_timings.json"
    payload = [{"text": c.text, "start": round(c.start, 3), "end": round(c.end, 3)} for c in cues]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def load_scene_timings(audio_dir: Path, scene_id: str) -> list[CaptionCue]:
    path = audio_dir / f"{scene_id}_timings.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [CaptionCue(**item) for item in raw if item.get("text")]


def merge_block_timings(scene_ids: list[str], audio_dir: Path) -> list[CaptionCue]:
    """Merge per-scene timings for block-level video (one_image mode)."""
    merged: list[CaptionCue] = []
    offset = 0.0
    for scene_id in scene_ids:
        wav = audio_dir / f"{scene_id}_voice.wav"
        if not wav.exists():
            continue
        dur = get_audio_duration(str(wav))
        cues = load_scene_timings(audio_dir, scene_id)
        if not cues:
            continue
        for cue in cues:
            merged.append(
                CaptionCue(
                    text=cue.text,
                    start=cue.start + offset,
                    end=min(cue.end + offset, offset + dur),
                )
            )
        offset += dur
    return merged


def caption_style(channel_config: dict) -> dict:
    cfg = channel_config.get("captions", {})
    colors = channel_config.get("color_scheme", {})
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "font_name": str(cfg.get("font_name", "Arial")),
        "font_size": int(cfg.get("font_size", 44)),
        "primary_color": str(cfg.get("primary_color", colors.get("text", "#FFFFFF"))),
        "outline_color": str(cfg.get("outline_color", "#000000")),
        "outline": int(cfg.get("outline", 3)),
        "margin_v": int(cfg.get("margin_v", 72)),
        "max_chars_per_line": int(cfg.get("max_chars_per_line", 42)),
        "shadow": int(cfg.get("shadow", 1)),
        "play_res_x": int(cfg.get("play_res_x", 1920)),
        "play_res_y": int(cfg.get("play_res_y", 1080)),
    }


def captions_enabled(channel_config: dict) -> bool:
    return caption_style(channel_config).get("enabled", True)


def _hex_to_ass_color(hex_color: str) -> str:
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return "&H00FFFFFF"
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"&H00{b:02X}{g:02X}{r:02X}"


def _wrap_caption_text(text: str, max_chars: int) -> str:
    words = text.split()
    if not words:
        return ""
    lines: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        add = len(word) + (1 if current else 0)
        if current and length + add > max_chars:
            lines.append(" ".join(current))
            current = [word]
            length = len(word)
        else:
            current.append(word)
            length += add
    if current:
        lines.append(" ".join(current))
    return "\\N".join(lines[:2])


def _ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{")


def _format_ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def write_ass_file(cues: list[CaptionCue], output_path: Path, style: dict) -> str:
    primary = _hex_to_ass_color(style.get("primary_color", "#FFFFFF"))
    outline = _hex_to_ass_color(style.get("outline_color", "#000000"))
    font = _ass_escape(style.get("font_name", "Arial"))
    size = style.get("font_size", 44)
    margin_v = style.get("margin_v", 72)
    outline_w = style.get("outline", 3)
    shadow = style.get("shadow", 1)
    max_chars = style.get("max_chars_per_line", 42)
    play_x = int(style.get("play_res_x", 1920))
    play_y = int(style.get("play_res_y", 1080))
    margin_lr = 48 if play_y > play_x else 80

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_x}
PlayResY: {play_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},{primary},&H000000FF,{outline},&H64000000,-1,0,0,0,100,100,0,0,1,{outline_w},{shadow},2,{margin_lr},{margin_lr},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for cue in cues:
        if not cue.text.strip() or cue.end <= cue.start:
            continue
        wrapped = _wrap_caption_text(cue.text.strip(), max_chars)
        if not wrapped:
            continue
        start = _format_ass_time(cue.start)
        end = _format_ass_time(cue.end)
        text = _ass_escape(wrapped)
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(lines), encoding="utf-8-sig")
    return str(output_path)


def write_srt_file(cues: list[CaptionCue], output_path: Path) -> str:
    def _srt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int(round((seconds % 1) * 1000))
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    parts: list[str] = []
    idx = 1
    for cue in cues:
        if not cue.text.strip() or cue.end <= cue.start:
            continue
        parts.append(str(idx))
        parts.append(f"{_srt_time(cue.start)} --> {_srt_time(cue.end)}")
        parts.append(cue.text.strip())
        parts.append("")
        idx += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")
    return str(output_path)


def burn_captions_on_video(
    video_path: str,
    cues: list[CaptionCue],
    output_path: str,
    channel_config: dict,
) -> str:
    if not cues or not captions_enabled(channel_config):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        if Path(video_path).resolve() != Path(output_path).resolve():
            import shutil

            shutil.copy2(video_path, output_path)
        return output_path

    style = caption_style(channel_config)
    ass_path = Path(output_path).with_suffix(".ass")
    write_ass_file(cues, ass_path, style)

    ass_escaped = str(ass_path.resolve()).replace("\\", "/").replace(":", "\\:")
    _log(f"Burning {len(cues)} caption cues -> {Path(output_path).name}")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"ass={ass_escaped}",
        "-c:a", "copy",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        _log(f"Caption burn failed, using uncaptioned video: {result.stderr[-400:]}")
        import shutil

        shutil.copy2(video_path, output_path)
    return output_path


def build_job_caption_files(
    cues: list[CaptionCue],
    job_dir: Path,
    channel_config: dict,
) -> dict[str, str]:
    if not cues:
        return {}
    style = caption_style(channel_config)
    ass_path = job_dir / "captions.ass"
    srt_path = job_dir / "captions.srt"
    write_ass_file(cues, ass_path, style)
    write_srt_file(cues, srt_path)
    return {"ass": str(ass_path), "srt": str(srt_path)}


def collect_job_caption_cues(scene_ids: list[str], audio_dir: Path) -> list[CaptionCue]:
    return merge_block_timings(scene_ids, audio_dir)
