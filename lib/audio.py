"""Text-to-speech via Kokoro."""

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
) -> str:
    from lib.script import clean_narration_for_tts

    clean = clean_narration_for_tts(text)
    voice_key = voice or channel_config.get("voice", {}).get("default", "default")
    speed_val = speed or channel_config.get("voice", {}).get("speed", 0.85)
    voice_id = VOICES.get(voice_key, VOICES["default"])
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _log(f"TTS -> {out.name} (voice={voice_key})")

    try:
        pipeline = _get_pipeline()
        chunks = []
        for _, _, audio in pipeline(clean, voice=voice_id, speed=speed_val):
            if audio is not None:
                chunks.append(np.array(audio))
        if chunks:
            combined = np.concatenate(chunks)
            sf.write(str(out), combined, SAMPLE_RATE)
        else:
            _write_silence(out, 3.0)
    except Exception as e:
        _log(f"Kokoro failed ({e}), writing silence placeholder")
        _write_silence(out, max(3.0, len(clean.split()) * 0.4))

    return str(out)


def _write_silence(path: Path, duration: float) -> None:
    samples = int(SAMPLE_RATE * duration)
    sf.write(str(path), np.zeros(samples, dtype=np.float32), SAMPLE_RATE)


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
            text, channel_config, str(out_path), voice=voice, speed=speed
        )
        paths.append(str(out_path))
    return paths
