"""Human voiceover recording."""

import threading
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

_recording = False
_elapsed = 0.0
_stop_event = threading.Event()
_record_thread = None
_record_data = []


def _log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] recorder: {msg}")


def list_input_devices() -> list[dict]:
    devices = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            devices.append({"id": i, "name": dev["name"], "channels": dev["max_input_channels"]})
    return devices


def get_recording_status() -> dict:
    return {"recording": _recording, "elapsed_seconds": _elapsed}


def stop_recording() -> None:
    global _recording
    _stop_event.set()
    _recording = False


def _record_loop(output_path: str, duration_seconds: float | None, device_id: int | None, sample_rate: int):
    global _recording, _elapsed, _record_data
    _record_data = []
    _stop_event.clear()
    _recording = True
    _elapsed = 0.0

    def callback(indata, frames, time_info, status):
        global _elapsed
        _record_data.append(indata.copy())
        _elapsed += frames / sample_rate

    stream_kwargs = {"samplerate": sample_rate, "channels": 1, "callback": callback}
    if device_id is not None:
        stream_kwargs["device"] = device_id

    with sd.InputStream(**stream_kwargs):
        if duration_seconds:
            sd.sleep(int(duration_seconds * 1000))
        else:
            while not _stop_event.is_set():
                sd.sleep(100)
    _recording = False
    if _record_data:
        audio = np.concatenate(_record_data, axis=0)
        sf.write(output_path, audio, sample_rate)
    _log(f"Recording saved: {output_path}")


def record_section(
    output_path: str,
    duration_seconds: float | None = None,
    device_id: int | None = None,
    sample_rate: int = 44100,
) -> str:
    global _record_thread
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    _record_thread = threading.Thread(
        target=_record_loop,
        args=(output_path, duration_seconds, device_id, sample_rate),
        daemon=True,
    )
    _record_thread.start()
    if duration_seconds:
        _record_thread.join()
    return output_path


def normalize_audio(input_path: str, output_path: str, target_db: float = -20.0) -> str:
    data, sr = sf.read(input_path)
    if len(data) == 0:
        sf.write(output_path, data, sr)
        return output_path
    peak = np.max(np.abs(data))
    if peak > 0:
        target_amp = 10 ** (target_db / 20)
        data = data * (target_amp / peak)
    sf.write(output_path, np.clip(data, -1.0, 1.0), sr)
    return output_path


def reduce_noise(input_path: str, output_path: str) -> str:
    data, sr = sf.read(input_path)
    if len(data) == 0:
        sf.write(output_path, data, sr)
        return output_path
    noise_samples = min(int(sr * 0.5), len(data))
    noise_floor = np.mean(np.abs(data[:noise_samples]))
    data = np.where(np.abs(data) < noise_floor * 1.5, data * 0.1, data)
    sf.write(output_path, data, sr)
    return output_path
