"""
VISHER — Real-time AI voice detection pipeline.
Entry point and CLI for the capture system.
"""

import sys
import argparse
import platform as platform_module
import queue
import threading
import signal

import sounddevice as sd

from config import SAMPLE_RATE, CHANNELS, CHUNK_DURATION_SEC
from inference import run_worker


def list_devices() -> None:
    """Print available input devices and exit."""
    devices = sd.query_devices()
    print("Available input devices:")
    for i, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            print(f"  [{i}] {device['name']}")
    sys.exit(0)


def main() -> None:
    """CLI entry point — parse args, detect platform, start stream and worker."""
    
    parser = argparse.ArgumentParser(
        description="VISHER — Real-time AI voice detection for vishing attacks"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Debug mode: notify on every chunk (REAL and FAKE)",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Input device index (see --list)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=CHUNK_DURATION_SEC,
        help=f"Chunk duration in seconds (default: {CHUNK_DURATION_SEC})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available input devices and exit",
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_devices()
    
    # Update chunk duration if specified
    import config as config_module
    if args.duration != CHUNK_DURATION_SEC:
        config_module.CHUNK_DURATION_SEC = args.duration
    
    # Platform detection
    system = platform_module.system()
    print(f"Detected OS: {system}", file=sys.stderr)
    
    # Import platform-specific start_stream
    try:
        if system == "Linux":
            from visher_platform.audio_linux import start_stream
        elif system == "Windows":
            from visher_platform.audio_windows import start_stream
        else:
            print(f"Unsupported platform: {system}", file=sys.stderr)
            sys.exit(1)
    except ImportError as e:
        print(f"Failed to import audio backend: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Compute chunk size
    chunk_samples = int(SAMPLE_RATE * args.duration)
    
    print(f"Chunk: {chunk_samples} samples / {args.duration}s (at {SAMPLE_RATE} Hz)", file=sys.stderr)
    
    # Create queue and stop event
    audio_queue: queue.Queue = queue.Queue(maxsize=10)
    stop_event = threading.Event()
    
    # Start inference worker
    worker_thread = run_worker(audio_queue, stop_event, debug=args.debug)
    print("Inference worker started", file=sys.stderr)
    
    # Start audio stream
    try:
        stream = start_stream(audio_queue, chunk_samples, device=args.device)
        print(f"Audio stream started (device={args.device})", file=sys.stderr)
    except Exception as e:
        print(f"Failed to start audio stream: {e}", file=sys.stderr)
        stop_event.set()
        sys.exit(1)
    
    # Signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print("\nShutting down...", file=sys.stderr)
        stop_event.set()
        stream.stop()
        stream.close()
        worker_thread.join(timeout=2.0)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Keep main thread alive
    print("VISHER running — press Ctrl+C to exit", file=sys.stderr)
    try:
        while True:
            signal.pause()
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
