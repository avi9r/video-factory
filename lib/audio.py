"""Text-to-speech via Kokoro with marker-aware pacing and documentary VO chain."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

VOICES = {
    "female_warm": "af_heart",
    "female_bright": "af_bella",
    "female_soft": "af_sky",
    "female_clear": "af_sarah",
    "female_energetic": "af_nova",
    "female_storyteller": "af_alloy",
    "female_young": "af_jessica",
    "female_professional": "af_river",
    "female_alloy": "af_alloy",
    "female_mellow": "af_kore",
    "female_nova": "af_nova",
    "male_deep": "am_adam",
    "male_calm": "am_michael",
    "male_warm": "am_echo",
    "male_authoritative": "am_onyx",
    "male_dramatic": "am_liam",
    "male_young": "am_fenrir",
    "male_smooth": "am_eric",
    "male_friendly": "am_santa",
    "british_female_emma": "bf_emma",
    "british_female_alice": "bf_alice",
    "british_female_isabella": "bf_isabella",
    "british_female_lily": "bf_lily",
    "british_male_george": "bm_george",
    "british_male_lewis": "bm_lewis",
    "british_male_daniel": "bm_daniel",
    "british_male_fable": "bm_fable",
    "default": "af_heart",
}

_pipelines: dict[str, object] = {}
SAMPLE_RATE = 24000
UNIT_GAP_SEC = 0.16
SCENE_GAP_SEC = 0.45
PAUSE_SEC = 0.48
BREATH_SEC = 0.26

_MARKER_RE = re.compile(
    r"\[(pause|breath|slow|fast|emphasis)\]",
    re.IGNORECASE,
)

EMOTION_SPEED_DELTA = {
    "curiosity": -0.02,
    "tension": -0.06,
    "shock": -0.07,
    "empathy": -0.04,
    "revelation": -0.08,
    "resolve": -0.01,
    "urgency": 0.0,
    "calm": -0.04,
    "fear": -0.06,
    "hope": -0.02,
}

TONE_SPEED_DELTA = {
    "urgent whisper": -0.08,
    "measured clarity": -0.04,
    "rising intensity": -0.05,
    "quiet resolve": -0.06,
    "sharp reveal": -0.07,
    "warm closure": -0.03,
    "cold precision": -0.05,
}


@dataclass
class NarrationSpan:
    kind: str  # text | pause | breath
    text: str = ""
    speed_delta: float = 0.0


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] audio: {msg}")


def lang_code_for_voice(voice_id: str) -> str:
    """American voices use 'a'; British Kokoro packs use 'b'."""
    if voice_id.startswith(("bf_", "bm_")):
        return "b"
    return "a"


def _get_pipeline(lang_code: str = "a"):
    if lang_code not in _pipelines:
        from kokoro import KPipeline

        _pipelines[lang_code] = KPipeline(lang_code=lang_code)
    return _pipelines[lang_code]


def get_audio_duration(audio_path: str) -> float:
    info = sf.info(audio_path)
    return info.duration


def silence(duration_sec: float) -> np.ndarray:
    n = max(0, int(SAMPLE_RATE * duration_sec))
    return np.zeros(n, dtype=np.float32)


def emotion_speed_offset(emotion: str | None = None, narration_tone: str | None = None) -> float:
    delta = 0.0
    if emotion:
        delta += EMOTION_SPEED_DELTA.get(str(emotion).strip().lower(), 0.0)
    if narration_tone:
        key = str(narration_tone).strip().lower()
        delta += TONE_SPEED_DELTA.get(key, 0.0)
        if "urgent" in key:
            delta += 0.03
        elif "whisper" in key or "quiet" in key:
            delta -= 0.04
        elif "measured" in key or "calm" in key:
            delta -= 0.02
    return delta


def parse_narration_spans(text: str) -> list[NarrationSpan]:
    """Split narration into text/pause/breath spans with speed modifiers."""
    raw = str(text or "")
    if not raw.strip():
        return []

    spans: list[NarrationSpan] = []
    speed_delta = 0.0
    last = 0
    for match in _MARKER_RE.finditer(raw):
        before = raw[last:match.start()]
        if before.strip():
            spans.append(NarrationSpan(kind="text", text=before, speed_delta=speed_delta))
        elif before and spans and spans[-1].kind == "text":
            spans[-1].text += before

        tag = match.group(1).lower()
        if tag == "pause":
            spans.append(NarrationSpan(kind="pause"))
            speed_delta = 0.0
        elif tag == "breath":
            spans.append(NarrationSpan(kind="breath"))
            speed_delta = 0.0
        elif tag == "slow":
            speed_delta = -0.08
        elif tag == "fast":
            speed_delta = 0.08
        elif tag == "emphasis":
            speed_delta = -0.06
        last = match.end()

    tail = raw[last:]
    if tail.strip():
        spans.append(NarrationSpan(kind="text", text=tail, speed_delta=speed_delta))
    elif tail and spans and spans[-1].kind == "text":
        spans[-1].text += tail

    # Normalize text spans: collapse whitespace, strip ellipsis Kokoro silence traps
    cleaned: list[NarrationSpan] = []
    for span in spans:
        if span.kind != "text":
            cleaned.append(span)
            continue
        text = re.sub(r"\.{3,}", ".", span.text)
        text = re.sub(r"\s+", " ", text).strip(" ,;")
        if text:
            cleaned.append(NarrationSpan(kind="text", text=text, speed_delta=span.speed_delta))
    return cleaned


def _synth_text(
    pipeline,
    text: str,
    voice_id: str,
    speed: float,
) -> np.ndarray:
    chunks: list[np.ndarray] = []
    for _, _, audio in pipeline(text, voice=voice_id, speed=speed):
        if audio is not None:
            chunks.append(np.array(audio, dtype=np.float32))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks)


def generate_scene_voiceover(
    text: str,
    channel_config: dict,
    output_path: str,
    voice: str | None = None,
    speed: float | None = None,
    *,
    scene_id: str | None = None,
    emotion: str | None = None,
    narration_tone: str | None = None,
) -> str:
    from lib.captions import CaptionCue, estimate_timings_proportional, save_scene_timings, split_narration_units
    from lib.tts_speak import speakify_for_tts

    voice_cfg = channel_config.get("voice", {}) or {}
    voice_key = voice or voice_cfg.get("default", "default")
    # Default slower than before — Kokoro sounds less "AI rush" under ~0.82
    base_speed = float(speed if speed is not None else voice_cfg.get("speed", 0.80))
    base_speed = max(0.55, min(1.05, base_speed + emotion_speed_offset(emotion, narration_tone)))
    voice_id = VOICES.get(voice_key, VOICES["default"])
    lang = lang_code_for_voice(voice_id)

    pause_sec = float(voice_cfg.get("pause_sec", PAUSE_SEC))
    breath_sec = float(voice_cfg.get("breath_sec", BREATH_SEC))
    unit_gap = float(voice_cfg.get("unit_gap_sec", UNIT_GAP_SEC))

    # Speakify digits/years before synthesis (keep markers)
    spoken = speakify_for_tts(text)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _log(f"TTS -> {out.name} (voice={voice_key}, lang={lang}, speed={base_speed:.2f})")

    spans = parse_narration_spans(spoken)
    timings: list[CaptionCue] = []
    audio_chunks: list[np.ndarray] = []
    offset = 0.0
    plain_for_fallback = re.sub(r"\[(pause|breath|slow|fast|emphasis)\]", " ", spoken, flags=re.I)
    plain_for_fallback = re.sub(r"\s+", " ", plain_for_fallback).strip()

    try:
        pipeline = _get_pipeline(lang)
        if not spans and plain_for_fallback:
            spans = [NarrationSpan(kind="text", text=plain_for_fallback)]

        for span in spans:
            if span.kind == "pause":
                gap = silence(pause_sec)
                audio_chunks.append(gap)
                offset += pause_sec
                continue
            if span.kind == "breath":
                gap = silence(breath_sec)
                audio_chunks.append(gap)
                offset += breath_sec
                continue

            unit_speed = max(0.55, min(1.05, base_speed + span.speed_delta))
            # Shorter units = more natural micro-pauses from Kokoro phrase boundaries
            units = split_narration_units(span.text, max_words=12)
            if not units:
                units = [span.text]
            for i, unit in enumerate(units):
                segment = _synth_text(pipeline, unit, voice_id, unit_speed)
                if segment.size == 0:
                    continue
                dur = len(segment) / SAMPLE_RATE
                timings.append(CaptionCue(text=unit.strip(), start=offset, end=offset + dur))
                offset += dur
                audio_chunks.append(segment)
                if i < len(units) - 1:
                    audio_chunks.append(silence(unit_gap))
                    offset += unit_gap

        if audio_chunks:
            combined = np.concatenate(audio_chunks)
            sf.write(str(out), combined, SAMPLE_RATE)
            normalize_voice_wav(str(out))
            if scene_id and not timings:
                timings = estimate_timings_proportional(
                    plain_for_fallback, get_audio_duration(str(out))
                )
            if scene_id and timings:
                save_scene_timings(out.parent, scene_id, timings)
        else:
            _write_silence(out, 3.0)
            if scene_id:
                save_scene_timings(out.parent, scene_id, [])
    except Exception as e:
        _log(f"Kokoro failed ({e}), writing silence placeholder")
        _write_silence(out, max(3.0, len(plain_for_fallback.split()) * 0.4))
        if scene_id:
            save_scene_timings(
                out.parent,
                scene_id,
                estimate_timings_proportional(plain_for_fallback, get_audio_duration(str(out))),
            )

    return str(out)


def _write_silence(path: Path, duration: float) -> None:
    samples = int(SAMPLE_RATE * duration)
    sf.write(str(path), np.zeros(samples, dtype=np.float32), SAMPLE_RATE)


def normalize_voice_wav(path: str, *, integrated_lufs: float = -16.5) -> str:
    """Warmer documentary VO chain — less brittle 'AI' top end."""
    src = Path(path)
    if not src.is_file():
        return path
    tmp = src.with_suffix(".norm.wav")
    af = (
        "highpass=f=70,"
        "lowpass=f=10500,"
        "equalizer=f=180:t=h:width=120:g=1.4,"
        "equalizer=f=3200:t=h:width=1600:g=0.6,"
        "acompressor=threshold=-20dB:ratio=2.2:attack=25:release=180:makeup=2.5,"
        f"loudnorm=I={integrated_lufs}:TP=-1.5:LRA=12:print_format=none,"
        "alimiter=limit=0.94"
    )
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-af", af, str(tmp)],
            capture_output=True,
            text=True,
            check=True,
        )
        tmp.replace(src)
    except Exception as e:
        _log(f"Voice normalize skipped ({e})")
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return str(src)


def append_scene_gap(wav_path: str, gap_sec: float = SCENE_GAP_SEC) -> str:
    """Append a short trailing silence so scene concat breathes."""
    path = Path(wav_path)
    if not path.is_file() or gap_sec <= 0:
        return wav_path
    try:
        data, sr = sf.read(str(path), dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)
        gap = np.zeros(int(sr * gap_sec), dtype=np.float32)
        sf.write(str(path), np.concatenate([data, gap]), sr)
    except Exception as e:
        _log(f"Scene gap skipped ({e})")
    return wav_path


def generate_all_voiceovers(
    scenes: list[dict],
    channel_config: dict,
    output_dir: str,
    voice: str | None = None,
    speed: float | None = None,
) -> list[str]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    total = len(scenes)
    for i, scene in enumerate(scenes, 1):
        scene_id = scene.get("scene_id", f"scene_{i}")
        text = scene.get("narration") or scene.get("text", "")
        _log(f"Voiceover {i}/{total}: {scene_id}")
        out_path = out_dir / f"{scene_id}_voice.wav"
        generate_scene_voiceover(
            text,
            channel_config,
            str(out_path),
            voice=voice,
            speed=speed,
            scene_id=scene_id,
            emotion=scene.get("emotion"),
            narration_tone=scene.get("narration_tone"),
        )
        append_scene_gap(str(out_path))
        paths.append(str(out_path))
    return paths
