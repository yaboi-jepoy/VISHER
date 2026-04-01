"""
Linux audio capture backend using sounddevice (PortAudio/PipeWire/ALSA).
Auto-detects monitor devices and resamples to 16kHz.
"""

import sys
import subprocess
from typing import Optional
from math import gcd
import queue
import numpy as np
import sounddevice as sd
from scipy import signal

from config import SAMPLE_RATE, CHANNELS, CHUNK_DURATION_SEC


def find_monitor_device() -> Optional[str]:
    """
    Auto-detect a PipeWire/ALSA monitor (loopback) device.
    
    Runs `pactl list sources short` and looks for a source:
    - Name contains ".monitor"
    - Status is "RUNNING"
    
    Returns:
        Device name string of the first match, or None if not found.
        Never raises — returns None on failure.
    """
    try:
        result = subprocess.run(
            ["pactl", "list", "sources", "short"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        
        for line in result.stdout.splitlines():
            parts = line.split('\t')
            if len(parts) >= 5:
                name = parts[1]
                status = parts[4].strip()
                if ".monitor" in name and "RUNNING" in status:
                    return name
        
        return None
    except Exception:
        return None


def start_stream(
    audio_queue: queue.Queue, chunk_samples: int, device: Optional[int | str] = None
) -> sd.InputStream:
    """
    Start audio stream on Linux.
    Captures at device's native rate, resamples to 16000 Hz.
    
    Args:
        audio_queue: thread-safe queue to push audio chunks into (16kHz)
        chunk_samples: ignored (calculated based on config duration)
        device: optional device index or name
    
    Returns:
        sounddevice.InputStream — caller is responsible for cleanup
    """
    
    # Auto-detect monitor device if not specified
    if device is None:
        monitor_name = find_monitor_device()
        if monitor_name:
            print(f"Monitor device detected: {monitor_name}", file=sys.stderr)
            # PipeWire monitor devices are typically exposed through
            # generic sources like "pipewire" or "pulse" in sounddevice.
            # Try to use one of those for loopback audio capture.
            try:
                all_devices = sd.query_devices()
                # Prefer "pipewire" (PipeWire's loopback), then "pulse" (PulseAudio compat)
                preferred_loopbacks = ["pipewire", "pulse"]
                
                for loopback_name in preferred_loopbacks:
                    for dev in all_devices:
                        if dev.get("max_input_channels", 0) > 0 and dev.get("name", "").lower() == loopback_name.lower():
                            device = dev.get("index")
                            print(f"Using sounddevice: [{device}] {dev.get('name')}", file=sys.stderr)
                            break
                    if device is not None:
                        break
                
                if device is None:
                    # Fallback: try generic sources that might capture system audio
                    for dev in all_devices:
                        if dev.get("max_input_channels", 0) > 0 and dev.get("name", "").lower() in ["default", "jack"]:
                            device = dev.get("index")
                            print(f"Using sounddevice (fallback): [{device}] {dev.get('name')}", file=sys.stderr)
                            break
                
                if device is None:
                    print(f"[WARN] Could not find monitor device '{monitor_name}' or loopback source. Using default input.", file=sys.stderr)
            except Exception as e:
                print(f"[WARN] Failed to search devices: {e}. Using default input.", file=sys.stderr)
                device = None
        else:
            print("[WARN] No loopback/monitor device found. Falling back to default input.", file=sys.stderr)
            device = None
    
    # Query device to get native sample rate
    if device is not None:
        try:
            dev_info = sd.query_devices(device)
            native_rate = int(dev_info["default_samplerate"])
        except Exception as e:
            print(f"[WARN] Failed to query device {device}: {e}. Using default input.", file=sys.stderr)
            device = None
            native_rate = sd.default.samplerate or 48000
    else:
        native_rate = sd.default.samplerate or 48000
    
    # Compute capture-side chunk size
    capture_chunk_samples = int(native_rate * CHUNK_DURATION_SEC)
    
    # Mutable list buffer to accumulate raw audio samples
    buffer = [np.array([], dtype=np.float32)]
    
    def audio_callback(indata, frames, time, status):
        """
        Accumulate samples, resample when full chunk available, normalize, push to queue.
        """
        if status:
            print(f"Audio callback warning: {status}", file=sys.stderr)
        
        # Extract audio (mono)
        incoming = indata[:, 0] if CHANNELS == 1 else indata.flatten()
        
        # Append to mutable buffer
        buffer[0] = np.append(buffer[0], incoming)
        
        # Process complete capture chunks
        while len(buffer[0]) >= capture_chunk_samples:
            # Extract one chunk at native rate
            chunk = buffer[0][:capture_chunk_samples].copy()
            buffer[0] = buffer[0][capture_chunk_samples:]
            
            # Resample from native_rate to 16000 Hz if needed
            if native_rate != SAMPLE_RATE:
                # Compute GCD for resample ratio
                gcd_val = gcd(SAMPLE_RATE, native_rate)
                up = SAMPLE_RATE // gcd_val
                down = native_rate // gcd_val
                chunk = signal.resample_poly(chunk, up, down)
            
            # Normalize amplitude
            max_val = np.max(np.abs(chunk))
            if max_val > 0:
                chunk = (chunk / max_val * 0.9).astype(np.float32)
            
            audio_queue.put(chunk.astype(np.float32))
    
    stream = sd.InputStream(
        device=device,
        samplerate=native_rate,
        channels=CHANNELS,
        blocksize=int(native_rate * 0.1),  # 100ms blocks
        callback=audio_callback,
        dtype=np.float32,
    )
    stream.start()
    return stream
