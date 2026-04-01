# VISHER Capture — Usage Guide

VISHER is a real-time AI voice detection pipeline designed to identify AI-generated (deepfake) voices in live audio streams, targeting vishing (voice phishing) attacks.

---

## Prerequisites

### Python

- **Python 3.10+** (required, Python 3.11 is recommended)
- Verify: `python --version`

### All Platforms

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   This installs:
   - `numpy` — audio array handling
   - `scipy` — signal processing (resampling)
   - `sounddevice` — cross-platform audio capture via PortAudio
   - `requests` — HTTP communication with inference server
   - `plyer` — cross-platform desktop notifications

2. **Inference server must be running** at `http://localhost:8000/depfake`
   - See `../server/` for setup instructions
   - Server expects WAV audio data and returns `{"status": 1, "Message": "FAKE"}` or `"REAL"`

---

## Linux Setup

### System Dependencies

Install `libnotify` for desktop notifications:

**Arch/EndeavourOS:**

```bash
sudo pacman -S libnotify
```

**Ubuntu/Debian:**

```bash
sudo apt-get install libnotify-bin
```

**Fedora:**

```bash
sudo dnf install libnotify
```

### Audio Setup

Audio is captured via **PipeWire/ALSA** through PortAudio. The system **auto-detects monitor (loopback) devices** on startup — no manual configuration needed for standard setups.

**To verify available devices:**

```bash
python capture.py --list
```

This prints all input devices. By default, if no device is specified:

- Scans for PipeWire monitor sources (`.monitor` suffix) with RUNNING status
- Falls back to system default input if no loopback device is found
- Captures at the device's native sample rate and resamples to 16000 Hz

**To capture from a non-loopback device** (e.g., microphone):

```bash
python capture.py --device 16  # Use index 16
```

### Running on Linux

**Auto-detects loopback device (if available):**

```bash
python capture.py
```

This will automatically find and use a PipeWire monitor source, or fall back to default input.

**Use a specific device:**

```bash
python capture.py --device 16  # e.g., microphone at index 16
```

**Debug mode (notify on all detections):**

```bash
python capture.py --debug
```

**Custom chunk duration:**

```bash
python capture.py --duration 5  # 5-second chunks instead of 3
```

### Expected Behavior

- Audio captured at device's native rate (auto-detected, typically 48000 Hz for loopback)
- Resampled to 16000 Hz for YAMNet model
- Normalized for consistent signal levels
- Converted to WAV in memory → sent to server via HTTP POST
- **Production mode:** Desktop notification only on `FAKE` detection
- **Debug mode:** Notification on every chunk result
- Press `Ctrl+C` to exit gracefully

### Troubleshooting

**Auto-detection not finding loopback device:**

- Verify monitor sources exist: `pactl list sources | grep monitor`
- Check if source is RUNNING: `pactl list sources short | grep monitor`
- If no monitor source, create one: `pactl load-module module-loopback`
- Use `--device` flag to specify device manually: `python capture.py --device 18`

**No audio devices found:**

- Verify microphone is connected: `pactl list sources`
- Check PipeWire is running: `pactl info` (should show PipeWire server info)
- If using ALSA: `arecord -l` to list ALSA devices

**Notifications not appearing:**

- Verify notification daemon is running: `systemctl --user status` (check for `notification`)
- On AwesomeWM, Sway, i3, etc., ensure a libnotify-compatible daemon is active (dunst, mako, swaync)
- Test manually: `notify-send "Test" "Notification"`

**Connection errors to server:**

- Verify server is running: `curl http://localhost:8000/depfake` (should fail gracefully, not connection refused)
- Check server URL in `config.py`

---

## Windows Setup

### System Dependencies

**No system dependencies required.** All components are bundled with Python packages:

- PortAudio is bundled with `sounddevice` wheel
- Windows notification API is native (no extra install needed)

### Audio Setup

Audio uses **WASAPI** (Windows Audio Session API) for low-latency capture. The system **auto-detects loopback devices** ("Stereo Mix", "What U Hear", "Loopback") on startup.

**To verify available devices:**

```bash
python capture.py --list
```

By default, if no device is specified:

- Scans for loopback/stereo mix devices
- Falls back to system default input if none found
- Captures at the device's native sample rate and resamples to 16000 Hz

**To capture from a specific microphone or device:**

```bash
python capture.py --device 1  # Use device at index 1
```

### Running on Windows

**Auto-detects loopback device (if available):**

```bash
python capture.py
```

This will automatically find and use Stereo Mix or equivalent, or fall back to default input.

**Use a specific device:**

```bash
python capture.py --device 1  # e.g., microphone at index 1
```

**Debug mode:**

```bash
python capture.py --debug
```

**Custom chunk duration:**

```bash
python capture.py --duration 5  # 5-second chunks instead of 3
```

### Expected Behavior

- Audio captured at device's native sample rate (auto-detected)
- Resampled to 16000 Hz for YAMNet model
- Normalized for consistent signal levels
- Converted to WAV in memory → HTTP POST to server
- **Production mode:** Toast notification only on `FAKE` detection
- **Debug mode:** Toast on every chunk result
- Press `Ctrl+C` to exit gracefully

### Troubleshooting

**Auto-detection not finding loopback device:**

- Enable "Stereo Mix" in Windows Sound settings (if available):
  1. Right-click speaker icon → Open Sound settings
  2. Advanced → Recording devices
  3. Right-click empty area → Show Disabled Devices
  4. Right-click "Stereo Mix" → Enable
- Use `--device` flag to specify device manually: `python capture.py --device 1`

**No audio devices found:**

- Open Settings → Sound → check that your microphone is enabled and set as default
- Run `python capture.py --list` again

**Notifications not appearing:**

- Verify action center is enabled: Settings → System → Notifications & actions
- Check that VISHER notifications are not blocked: Settings → System → Notifications → Advanced options

**Connection to server fails:**

- Verify server at `http://localhost:8000/depfake` is accessible
- If running server on a different machine, update `SERVER_URL` in `config.py`

---

## CLI Reference

### Flags

| Flag             | Behavior                                                     |
| ---------------- | ------------------------------------------------------------ |
| _(none)_         | **Production mode** — notify only on `FAKE` detections       |
| `--debug`        | **Debug mode** — notify on every chunk (`REAL` and `FAKE`)   |
| `--device N`     | Use input device at index N (see `--list`)                   |
| `--duration SEC` | Chunk duration in seconds (default: 3, e.g., `--duration 5`) |
| `--list`         | Print available input devices and exit                       |

### Examples

List all devices:

```bash
python capture.py --list
```

Run in debug mode with 5-second chunks:

```bash
python capture.py --debug --duration 5
```

Run with specific device:

```bash
python capture.py --device 16
```

Run in production mode with auto-detected device:

```bash
python capture.py
```

---

## Configuration

All constants are in [config.py](config.py):

```python
CHUNK_DURATION_SEC = 3       # seconds per chunk (can be overridden via --duration flag)
SAMPLE_RATE = 16000          # Hz — fixed for YAMNet model compatibility, never change
CHANNELS = 1                 # mono
SERVER_URL = "http://localhost:8000/depfake"
REQUEST_TIMEOUT = 10         # seconds to wait for server response
NOTIFICATION_TITLE = "VISHER"
NOTIFICATION_APP = "VISHER Voice Detection"
```

### Changeable Settings

- **Chunk duration:** Use `--duration` flag at runtime (recommended) or edit `CHUNK_DURATION_SEC`
- **Server URL:** Edit `config.py` if running server on non-localhost address
- **Request timeout:** Edit `config.py` if network is slow

### Fixed Settings

- `SAMPLE_RATE` **must remain 16000 Hz** — it's the required input for the YAMNet model
- Capture device rate is auto-detected from actual hardware

---

## Architecture Overview

```
Device Audio (native rate: auto-detected)
    │
    ▼
Audio Callback (sounddevice | PipeWire/ALSA on Linux, WASAPI on Windows)
    │  accumulates audio in device's native rate
    ▼
Resampling (scipy.signal.resample_poly)
    │  converts native rate → 16000 Hz using GCD-based ratio
    ▼
Amplitude Normalization
    │  scales to [-0.9, 0.9] for consistent levels
    ▼
Queue (thread-safe)
    │
    ▼
Inference Worker (background thread)
    │  converts chunk → WAV bytes in memory → HTTP POST
    ▼
FastAPI Server (localhost:8000/depfake)
    │  returns {"status": 1, "Message": "FAKE"} or "REAL"
    ▼
Desktop Notification
    │
    ▼
Notification Daemon (libnotify on Linux, toast on Windows)
```

**Key design:** Audio callback never blocks. All resampling, normalization, encoding, network I/O, and notification calls run on a separate worker thread.

---

## Error Handling

- **Network errors, timeouts, bad responses:** Logged to stderr, pipeline continues
- **Notification failures:** Logged to stderr, pipeline continues
- **Audio capture errors:** Logged to stderr, pipeline continues
- **Critical errors (e.g., server unreachable on startup):** Printed to stderr, graceful exit

All errors go to `stderr` so they don't interfere with standard output.

---

## Stopping the Program

Press `Ctrl+C` at any time to gracefully shut down:

1. Audio stream stops
2. Inference worker thread joins with 2-second timeout
3. Program exits

---

## Next Steps

1. Ensure the **inference server** is running (see `../server/`)
2. Run `python capture.py --list` to verify microphone access
3. Start with `python capture.py --debug` to see all detections
4. Switch to `python capture.py` for production (FAKE detections only)
