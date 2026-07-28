"""Local SFX catalog and FFmpeg scene-level mixing."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from lib.audio import get_audio_duration
from lib.config import SFX_BASE

MAX_SFX_BUS_VOLUME = 0.10
SAMPLE_RATE = 24000
FADE_IN_SEC = 0.35
FADE_OUT_SEC = 0.45

AMBIENT_KEYWORDS = frozenset({
    "ambient", "rain", "weather", "wind", "storm", "ocean", "waves", "river",
    "brook", "stream", "water", "crowd", "murmur", "chatter", "office", "lobby",
    "traffic", "city", "nature", "forest", "birds", "bees", "fire", "campfire",
    "fireplace", "elevator", "cafeteria", "restaurant", "mall", "coffee", "typing",
    "keyboard", "construction", "factory", "metro", "subway", "train", "highway",
})

ONE_SHOT_KEYWORDS = frozenset({
    "knock", "beep", "ping", "whoosh", "glass", "explosion", "notification",
    "doorbell", "chime", "pop", "flip", "stapler", "siren", "heartbeat", "buzzer",
    "alert", "break", "whistle",
})

DEFAULT_MIX_CONFIG = {
    "ambient_volume_scale": 0.55,
    "one_shot_volume_scale": 0.80,
    "max_bus_volume": MAX_SFX_BUS_VOLUME,
    "ducking_enabled": True,
    "ducking_ratio": 6,
    "ducking_attack_ms": 60,
    "ducking_release_ms": 450,
}

_catalog_cache: dict | None = None


def _log(msg: str) -> None:
    print(f"sfx: {msg}")


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-500:] if result.stderr else "FFmpeg failed")


def load_sfx_catalog(*, refresh: bool = False) -> dict:
    global _catalog_cache
    if _catalog_cache is not None and not refresh:
        return _catalog_cache

    catalog_path = SFX_BASE / "catalog.yaml"
    if not catalog_path.exists():
        _catalog_cache = {}
        return _catalog_cache

    with open(catalog_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    catalog: dict = {}
    for sound_id, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        rel = entry.get("file", "")
        path = SFX_BASE / rel if rel else None
        catalog[sound_id] = {
            **entry,
            "sound_id": sound_id,
            "path": str(path) if path else None,
            "exists": bool(path and path.exists()),
        }
    _catalog_cache = catalog
    return catalog


def resolve_sound(sound_id: str) -> Path | None:
    entry = load_sfx_catalog().get(sound_id)
    if not entry or not entry.get("exists"):
        return None
    return Path(entry["path"])


def sfx_mix_config_from_channel(channel_config: dict | None) -> dict:
    """Build mixer settings from channel YAML `sfx:` block."""
    cfg = dict(DEFAULT_MIX_CONFIG)
    if not channel_config:
        return cfg
    sfx = channel_config.get("sfx", {})
    duck = sfx.get("ducking", {})
    if "ambient_volume_scale" in sfx:
        cfg["ambient_volume_scale"] = float(sfx["ambient_volume_scale"])
    if "one_shot_volume_scale" in sfx:
        cfg["one_shot_volume_scale"] = float(sfx["one_shot_volume_scale"])
    if "max_bus_volume" in sfx:
        cfg["max_bus_volume"] = float(sfx["max_bus_volume"])
    if "ducking_enabled" in duck:
        cfg["ducking_enabled"] = bool(duck["ducking_enabled"])
    if "ratio" in duck:
        cfg["ducking_ratio"] = float(duck["ratio"])
    if "attack_ms" in duck:
        cfg["ducking_attack_ms"] = int(duck["attack_ms"])
    if "release_ms" in duck:
        cfg["ducking_release_ms"] = int(duck["release_ms"])
    return cfg


def catalog_summary_for_llm(*, max_entries: int = 120) -> list[dict]:
    """Compact catalog for LLM SFX annotation — skips missing files."""
    summary = []
    for sound_id, entry in load_sfx_catalog().items():
        if not entry.get("exists"):
            continue
        vr = entry.get("volume_range", [0.04, 0.14])
        summary.append(
            {
                "sound_id": sound_id,
                "tags": entry.get("tags", [])[:4],
                "vol_range": [float(vr[0]), float(vr[1])],
                "kind": "ambient" if _is_ambient_sound(entry) else "one_shot",
            }
        )
        if len(summary) >= max_entries:
            break
    return summary


def catalog_compact_for_llm(*, max_entries: int = 48) -> str:
    """One-line-per-sound catalog to stay within Groq TPM limits."""
    lines = []
    for item in catalog_summary_for_llm(max_entries=max_entries):
        sid = item["sound_id"]
        kind = item["kind"][0]  # a or o
        lo, hi = item["vol_range"]
        tags = ",".join(item.get("tags", [])[:3])
        lines.append(f"{sid}|{kind}|{lo:.2f}-{hi:.2f}|{tags}")
    return "\n".join(lines)


def _is_ambient_sound(entry: dict) -> bool:
    tags = [str(t).lower() for t in entry.get("tags", [])]
    if any(t in ONE_SHOT_KEYWORDS for t in tags):
        return False
    if any(t in AMBIENT_KEYWORDS for t in tags):
        return True
    sound_id = str(entry.get("sound_id", "")).lower()
    ambient_ids = (
        "rain", "wind", "ambience", "crowd", "office", "traffic", "ocean",
        "river", "brook", "stream", "fire", "typing", "metro", "subway",
        "forest", "birds", "mall", "lobby", "cafeteria",
    )
    return any(token in sound_id for token in ambient_ids)


def _clamp_volume(volume: float, entry: dict) -> float:
    vol_range = entry.get("volume_range", [0.04, 0.14])
    lo, hi = float(vol_range[0]), float(vol_range[1])
    return max(lo, min(hi, float(volume)))


def _effective_volume(volume: float, entry: dict, mix_config: dict) -> float:
    vol = _clamp_volume(volume, entry)
    if _is_ambient_sound(entry):
        vol *= float(mix_config.get("ambient_volume_scale", 0.55))
    else:
        vol *= float(mix_config.get("one_shot_volume_scale", 0.80))
    return min(vol, float(mix_config.get("max_bus_volume", MAX_SFX_BUS_VOLUME)))


def _cue_duration_sec(
    cue: dict,
    *,
    scene_duration_sec: float | None,
    start_offset_sec: float,
) -> float:
    """Trim SFX to only the time needed within the scene."""
    if scene_duration_sec is None:
        return max(0.5, float(cue.get("duration_sec", 8)))

    remaining = max(0.3, scene_duration_sec - start_offset_sec)
    requested = cue.get("duration_sec")
    if requested is None:
        return remaining
    return min(max(0.3, float(requested)), remaining)


def _sanitize_cue_list(
    cues: list | None,
    max_cues: int = 2,
    *,
    scene_duration_sec: float | None = None,
    mix_config: dict | None = None,
) -> list[dict]:
    if not cues or not isinstance(cues, list):
        return []

    catalog = load_sfx_catalog()
    mix_cfg = {**DEFAULT_MIX_CONFIG, **(mix_config or {})}
    valid: list[dict] = []
    for cue in cues[:max_cues]:
        if not isinstance(cue, dict):
            continue
        sound_id = cue.get("sound_id")
        entry = catalog.get(sound_id)
        if not entry or not entry.get("exists"):
            continue
        start_offset_sec = max(0.0, float(cue.get("start_offset_sec", 0)))
        duration_sec = _cue_duration_sec(
            cue,
            scene_duration_sec=scene_duration_sec,
            start_offset_sec=start_offset_sec,
        )
        if scene_duration_sec is not None and start_offset_sec >= scene_duration_sec:
            continue
        volume = cue.get("volume", entry.get("default_volume", 0.08))
        valid.append(
            {
                "sound_id": sound_id,
                "start_offset_sec": start_offset_sec,
                "duration_sec": duration_sec,
                "volume": _effective_volume(volume, entry, mix_cfg),
                "ambient": _is_ambient_sound(entry),
            }
        )
    return valid


def sanitize_sfx_cues(script: dict, max_cues: int = 2) -> dict:
    if "hook" in script and isinstance(script["hook"], dict):
        hook_dur = script["hook"].get("duration_seconds")
        script["hook"]["sfx_cues"] = _sanitize_cue_list(
            script["hook"].get("sfx_cues"), max_cues, scene_duration_sec=hook_dur
        )
    for act in script.get("acts", []):
        for scene in act.get("scenes", []):
            scene_dur = scene.get("duration_seconds")
            scene["sfx_cues"] = _sanitize_cue_list(
                scene.get("sfx_cues"), max_cues, scene_duration_sec=scene_dur
            )
    if "outro" in script and isinstance(script["outro"], dict):
        outro_dur = script["outro"].get("duration_seconds")
        script["outro"]["sfx_cues"] = _sanitize_cue_list(
            script["outro"].get("sfx_cues"), max_cues, scene_duration_sec=outro_dur
        )
    return script


def mix_sfx_into_voice(
    voice_wav: str,
    cues: list[dict],
    output_wav: str,
    *,
    mix_config: dict | None = None,
) -> str:
    """Layer local SFX under narration — trimmed to scene length, ducked under voice."""
    mix_cfg = {**DEFAULT_MIX_CONFIG, **(mix_config or {})}
    scene_duration_sec = get_audio_duration(voice_wav)
    cues = _sanitize_cue_list(
        cues,
        scene_duration_sec=scene_duration_sec,
        mix_config=mix_cfg,
    )
    if not cues:
        if voice_wav != output_wav:
            Path(output_wav).write_bytes(Path(voice_wav).read_bytes())
        return output_wav

    resolved: list[tuple[dict, Path]] = []
    for cue in cues:
        path = resolve_sound(cue["sound_id"])
        if path:
            resolved.append((cue, path))
    if not resolved:
        if voice_wav != output_wav:
            Path(output_wav).write_bytes(Path(voice_wav).read_bytes())
        return output_wav

    inputs = ["-i", voice_wav]
    filter_parts: list[str] = []
    sfx_labels: list[str] = []

    for i, (cue, sfx_path) in enumerate(resolved):
        inputs.extend(["-i", str(sfx_path)])
        delay_ms = int(cue["start_offset_sec"] * 1000)
        dur = cue["duration_sec"]
        vol = cue["volume"]
        label = f"[sfx{i}]"
        fade_out_start = max(0.0, dur - FADE_OUT_SEC)
        filter_parts.append(
            f"[{i + 1}:a]aresample={SAMPLE_RATE},"
            f"atrim=0:{dur},"
            f"asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={FADE_IN_SEC},"
            f"afade=t=out:st={fade_out_start}:d={FADE_OUT_SEC},"
            f"adelay={delay_ms}|{delay_ms},"
            f"volume={vol:.4f}{label}"
        )
        sfx_labels.append(label)

    filter_parts.append(
        f"[0:a]aresample={SAMPLE_RATE},asetpts=PTS-STARTPTS,volume=1.0[voice]"
    )

    if len(sfx_labels) == 1:
        sfx_bus = sfx_labels[0]
    else:
        filter_parts.append(
            f"{''.join(sfx_labels)}amix=inputs={len(sfx_labels)}"
            f":duration=longest:dropout_transition=2[sfxbus]"
        )
        sfx_bus = "[sfxbus]"

    if mix_cfg.get("ducking_enabled", True):
        ratio = float(mix_cfg.get("ducking_ratio", 6))
        attack = int(mix_cfg.get("ducking_attack_ms", 60))
        release = int(mix_cfg.get("ducking_release_ms", 450))
        filter_parts.append(
            f"{sfx_bus}[voice]sidechaincompress=threshold=0.02:ratio={ratio}"
            f":attack={attack}:release={release}:level_sc=1[ducked]"
        )
        filter_parts.append(
            "[voice][ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
            "alimiter=limit=0.98:attack=5:release=50[aout]"
        )
    else:
        filter_parts.append(
            f"[voice]{sfx_bus}amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
            f"alimiter=limit=0.98:attack=5:release=50[aout]"
        )

    filter_complex = ";".join(filter_parts)
    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-ar", str(SAMPLE_RATE),
        "-ac", "1",
        "-t", f"{scene_duration_sec:.3f}",
        output_wav,
    ]
    _run_ffmpeg(cmd)
    _log(
        f"mixed {len(resolved)} cue(s) into {Path(voice_wav).name} "
        f"({scene_duration_sec:.1f}s, ducking={'on' if mix_cfg.get('ducking_enabled') else 'off'})"
    )
    return output_wav
