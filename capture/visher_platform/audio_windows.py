"""
Windows audio capture backend using sounddevice (PortAudio/WASAPI).
Auto-detects loopback devices and resamples to 16kHz.
"""

import sys
from typing import Optional
from math import gcd
import queue
import numpy as np
import sounddevice as sd
from scipy import signal

from config import SAMPLE_RATE, CHANNELS, CHUNK_DURATION_SEC


def find_monitor_device() -> Optional[str]:
    """
    Auto-detect a Windows loopback/stereo mix device.
    
    Scans all devices for one whose name contains:
    - "Stereo Mix", "What U Hear", or "Loopback" (case-insensitive)
    - AND has input channels > 0
    
    Returns:
        Device name string of the first match, or None if not found.
        Never raises — returns None on failure.
    """
    try:
        devices = sd.query_devices()
        if not isinstance(devices, list):
            devices = [devices]
        
        for device in devices:
            if device["max_input_channels"] > 0:
                name_lower = device["name"].lower()
                if any(x in name_lower for x in ["stereo mix", "what u hear", "loopback"]):
                    return device["name"]
        
        return None
    except Exception:
        return None


def start_stream(
    audio_queue: queue.Queue, chunk_samples: int, device: Optional[int | str] = None
) -> sd.InputStream:
    """
    Start audio stream on Windows.
    Captures at device's native rate, resamples to 16000 Hz.
    
    Args:
        audio_queue: thread-safe queue to push audio chunks into (16kHz)
        chunk_samples: ignored (calculated based on config duration)
        device: optional device index or name
    
    Returns:
        sounddevice.InputStream — caller is responsible for cleanup
    """
    
    # Auto-detect loopback device if not specified
    if device is None:
        loopback_name = find_monitor_device()
        if loopback_name:
            device = loopback_name
        else:
            print("[WARN] No loopback/monitor device found. Falling back to default input.", file=sys.stderr)
            device = None
    
    # Query device to get native sample rate
    if device is not None:
        try:
            dev_info = sd.query_devices(device)
            native_rate = int(dev_info["default_samplerate"])
        except Exception:
            print(f"[WARN] Failed to query device {device}. Using default input.", file=sys.stderr)
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
