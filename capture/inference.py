"""
Platform-independent inference worker — queue, WAV encoding, HTTP POST.
"""

import io
import sys
import queue
import threading
import wave
from typing import Optional

import numpy as np
import requests

from config import SAMPLE_RATE, CHANNELS, SERVER_URL, REQUEST_TIMEOUT, NOTIFICATION_TITLE
from visher_platform import notify


def numpy_to_wav_bytes(audio_chunk: np.ndarray) -> bytes:
    """
    Convert float32 numpy array to WAV bytes in memory (no disk writes).
    
    Args:
        audio_chunk: float32 numpy array of shape (N,) or (N, 1)
    
    Returns:
        bytes containing WAV data (PCM int16, single-pass encoding)
    """
    # Ensure 1D
    if audio_chunk.ndim > 1:
        audio_chunk = audio_chunk.flatten()
    
    # Clip to [-1, 1] and convert float32 → int16
    audio_chunk = np.clip(audio_chunk, -1.0, 1.0)
    audio_int16 = np.int16(audio_chunk * 32767)
    
    # Write to BytesIO buffer
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(audio_int16.tobytes())
    
    return buffer.getvalue()


def inference_worker(
    audio_queue: queue.Queue,
    stop_event: threading.Event,
    debug: bool = False,
) -> None:
    """
    Background thread: pop chunks, POST to server, fire notifications.
    
    Never raises — all errors are caught and logged to stderr.
    
    Args:
        audio_queue: thread-safe queue of numpy float32 chunks
        stop_event: threading.Event set by main thread to signal shutdown
        debug: if True, notify on all results (FAKE and REAL); else only FAKE
    """
    while not stop_event.is_set():
        try:
            # Block with timeout to allow stop_event to be checked
            try:
                chunk = audio_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            
            # Convert to WAV bytes
            try:
                wav_bytes = numpy_to_wav_bytes(chunk)
            except Exception as e:
                print(f"WAV encoding failed: {e}", file=sys.stderr)
                continue
            
            # POST to server as multipart form data
            try:
                response = requests.post(
                    SERVER_URL,
                    files={"audio_file": ("audio.wav", wav_bytes, "audio/wav")},
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
            except requests.RequestException as e:
                print(f"Server request failed: {e}", file=sys.stderr)
                continue
            except Exception as e:
                print(f"Unexpected error in POST: {e}", file=sys.stderr)
                continue
            
            # Parse response
            try:
                result = response.json()
                status = result.get("status", 0)
                message = result.get("Message", "UNKNOWN")
            except Exception as e:
                print(f"Failed to parse server response: {e}", file=sys.stderr)
                continue
            
            # Determine if fake
            is_fake = status == 1 or message == "FAKE"
            
            # Fire notification
            if debug or is_fake:
                try:
                    notify(
                        title=NOTIFICATION_TITLE,
                        message=f"Detection: {message}",
                        urgent=is_fake,
                    )
                except Exception as e:
                    print(f"Notification error: {e}", file=sys.stderr)
        
        except Exception as e:
            print(f"Unexpected error in inference worker: {e}", file=sys.stderr)


def run_worker(
    audio_queue: queue.Queue,
    stop_event: threading.Event,
    debug: bool = False,
) -> threading.Thread:
    """
    Start inference worker thread.
    
    Args:
        audio_queue: thread-safe queue of numpy float32 chunks
        stop_event: threading.Event to signal shutdown
        debug: if True, notify on all results; else only FAKE
    
    Returns:
        threading.Thread (not joined; caller must manage)
    """
    thread = threading.Thread(
        target=inference_worker,
        args=(audio_queue, stop_event, debug),
        daemon=True,
        name="VISHERInferenceWorker",
    )
    thread.start()
    return thread
