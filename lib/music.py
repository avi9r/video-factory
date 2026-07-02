"""Background music path resolution."""

from pathlib import Path

from lib.config import MUSIC_BASE


def get_music_for_act(niche_id: str, act: str, channel_config: dict) -> str | None:
    music_cfg = channel_config.get("music", {})
    filename = music_cfg.get(act)
    if not filename:
        return None
    path = MUSIC_BASE / niche_id / f"{filename}.mp3"
    if path.exists():
        return str(path)
    wav_path = MUSIC_BASE / niche_id / f"{filename}.wav"
    if wav_path.exists():
        return str(wav_path)
    return None


def list_available_music(niche_id: str) -> list[str]:
    music_dir = MUSIC_BASE / niche_id
    if not music_dir.exists():
        return []
    files = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
    return [f.stem for f in files]
