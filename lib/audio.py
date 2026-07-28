"""Text-to-speech via Kokoro."""

import subprocess
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

_pipeline = None
SAMPLE_RATE = 24000


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] audio: {msg}")


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from kokoro import KPipeline

        _pipeline = KPipeline(lang_code="a")
    return _pipeline


def get_audio_duration(audio_path: str) -> float:
    info = sf.info(audio_path)
    return info.duration


def generate_scene_voiceover(
    text: str,
    channel_config: dict,
    output_path: str,
    voice: str | None = None,
    speed: float | None = None,
    *,
    scene_id: str | None = None,
) -> str:
    from lib.captions import CaptionCue, estimate_timings_proportional, save_scene_timings, split_narration_units
    from lib.script import clean_narration_for_tts

    clean = clean_narration_for_tts(text)
    voice_key = voice or channel_config.get("voice", {}).get("default", "default")
    speed_val = speed or channel_config.get("voice", {}).get("speed", 0.85)
    voice_id = VOICES.get(voice_key, VOICES["default"])
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _log(f"TTS -> {out.name} (voice={voice_key})")

    units = split_narration_units(clean)
    timings: list[CaptionCue] = []
    audio_chunks: list[np.ndarray] = []
    offset = 0.0

    try:
        pipeline = _get_pipeline()
        if units:
            for unit in units:
                unit_audio: list[np.ndarray] = []
                for _, _, audio in pipeline(unit, voice=voice_id, speed=speed_val):
                    if audio is not None:
                        unit_audio.append(np.array(audio))
                if unit_audio:
                    segment = np.concatenate(unit_audio)
                    dur = len(segment) / SAMPLE_RATE
                    timings.append(CaptionCue(text=unit.strip(), start=offset, end=offset + dur))
                    offset += dur
                    audio_chunks.append(segment)
        else:
            for _, _, audio in pipeline(clean, voice=voice_id, speed=speed_val):
                if audio is not None:
                    audio_chunks.append(np.array(audio))

        if audio_chunks:
            combined = np.concatenate(audio_chunks)
            sf.write(str(out), combined, SAMPLE_RATE)
            normalize_voice_wav(str(out))
            if scene_id and not timings:
                timings = estimate_timings_proportional(clean, get_audio_duration(str(out)))
            if scene_id and timings:
                save_scene_timings(out.parent, scene_id, timings)
        else:
            _write_silence(out, 3.0)
            if scene_id:
                save_scene_timings(out.parent, scene_id, [])
    except Exception as e:
        _log(f"Kokoro failed ({e}), writing silence placeholder")
        _write_silence(out, max(3.0, len(clean.split()) * 0.4))
        if scene_id:
            save_scene_timings(
                out.parent,
                scene_id,
                estimate_timings_proportional(clean, get_audio_duration(str(out))),
            )

    return str(out)


def _write_silence(path: Path, duration: float) -> None:
    samples = int(SAMPLE_RATE * duration)
    sf.write(str(path), np.zeros(samples, dtype=np.float32), SAMPLE_RATE)


def normalize_voice_wav(path: str, *, integrated_lufs: float = -18.0) -> str:
    """Bring Kokoro narration to a consistent loudness before mixing."""
    src = Path(path)
    if not src.is_file():
        return path
    tmp = src.with_suffix(".norm.wav")
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(src),
                "-af", f"loudnorm=I={integrated_lufs}:TP=-1.5:LRA=11:print_format=none",
                str(tmp),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        _ = result
        tmp.replace(src)
    except Exception as e:
        _log(f"Voice normalize skipped ({e})")
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return str(src)


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
        )
        paths.append(str(out_path))
    return paths
