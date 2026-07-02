"""FFmpeg color grading."""

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from lib.config import LUT_BASE


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] color_grade: {msg}")


def apply_lut(video_path: str, lut_name: str, output_path: str) -> str:
    lut_path = LUT_BASE / f"{lut_name}.cube"
    if not lut_path.exists():
        _log(f"LUT not found: {lut_path}, skipping")
        shutil.copy2(video_path, output_path)
        return output_path
    _log(f"Applying LUT {lut_name}")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"lut3d={lut_path}",
        "-c:a", "copy", output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def apply_color_correction(
    video_path: str,
    brightness: float = 0.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    output_path: str | None = None,
) -> str:
    out = output_path or video_path.replace(".mp4", "_corrected.mp4")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"eq=brightness={brightness}:contrast={contrast}:saturation={saturation}",
        "-c:a", "copy", out,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out
