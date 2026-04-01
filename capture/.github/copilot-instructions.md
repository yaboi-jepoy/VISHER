# VISHER — Copilot Instructions

## Project Overview
VISHER is a real-time AI voice detection pipeline designed to identify AI-generated (deepfake) voices in live audio streams, targeting vishing (voice phishing) attacks. It captures system audio output in configurable chunks, sends each chunk to a local FastAPI inference server, and fires desktop notifications based on the result.

This repository contains only the **capture pipeline**. The inference server lives in a separate directory (`../server/`, cloned from `KaushiML3/Deepfake-voice-detection_Yamnet`).

---

## Project Structure
```
capture/
├── .github/
│   └── copilot-instructions.md   ← you are here
├── visher_platform/
│   ├── __init__.py               ← exposes start_stream and notify via runtime detection
│   ├── audio_linux.py            ← Linux audio backend (PipeWire/ALSA via PortAudio)
│   ├── audio_windows.py          ← Windows audio backend (WASAPI via PortAudio)
│   ├── notify_linux.py           ← Linux notifications (plyer → libnotify)
│   └── notify_windows.py         ← Windows notifications (plyer → win32 toast)
├── capture.py                    ← platform-independent entry point and CLI
├── inference.py                  ← platform-independent queue, WAV encoding, HTTP POST
├── config.py                     ← all constants in one place
└── requirements.txt
```

---

## Architecture

```
System Audio Output (loopback/monitor)
    │
    ▼
visher_platform/audio_{linux|windows}.py  (start_stream)
    │  auto-detects active monitor source if no device specified
    │  captures at native device rate, resamples to 16kHz
    │  fills buffer, slices into fixed-size chunks
    ▼
queue.Queue  (thread-safe audio chunk queue)
    │
    ▼
inference.py → inference_worker (background thread)
    │  normalizes amplitude
    │  converts chunk → WAV bytes in memory → HTTP POST
    ▼
FastAPI server at localhost:8000/depfake
    │  returns {"status": 1, "Message": "FAKE"} or "REAL"
    ▼
visher_platform/notify_{linux|windows}.py  (notify)
    │
    ▼
Desktop notification daemon
```

Two threads are intentional: the audio callback must never block, so all I/O (HTTP, notifications) is offloaded to the worker thread in `inference.py`.

---

## Module Responsibilities

### `config.py` — platform-independent
All configurable constants. No logic, no imports beyond stdlib. Every other module imports from here. Contains:
- `CHUNK_DURATION_SEC`
- `SAMPLE_RATE` (fixed at 16000, never configurable)
- `CHANNELS`
- `SERVER_URL`
- `REQUEST_TIMEOUT`
- `NOTIFICATION_TITLE`
- `NOTIFICATION_APP`

### `capture.py` — platform-independent
- CLI entry point using `argparse`
- Detects platform via `platform.system()` and imports the correct backend modules
- Calls `start_stream()` from the appropriate audio backend
- Passes the `audio_queue` and `stop_event` to `inference.run_worker()`
- No audio logic, no notification logic, no HTTP logic

### `inference.py` — platform-independent
- Owns the `queue.Queue` and `threading.Event`
- `numpy_to_wav_bytes()` — converts float32 numpy array to WAV bytes using `io.BytesIO` + `wave` (no disk writes)
- `inference_worker()` — background thread: pops chunks, POSTs to server, calls `notify()`
- `run_worker()` — starts the worker thread and returns it
- Imports `notify` from `visher_platform/__init__.py`
- Imports all constants from `config.py`

### `visher_platform/__init__.py` — runtime platform detection
Detects `platform.system()` at import time and exposes two unified symbols:
- `start_stream(audio_queue, chunk_samples, device)` — starts audio capture
- `notify(title, message, urgent)` — fires a desktop notification

No platform-specific code here — only imports from the appropriate submodule.

### `visher_platform/audio_linux.py` — Linux only
- Implements `find_monitor_device() -> str | None`
  - Runs `pactl list sources short` via `subprocess`
  - Parses output line by line looking for a source whose name contains `.monitor` and whose status column is `RUNNING`
  - Returns the source name string of the first match, or `None` if none found
  - Never raises — wraps in try/except and returns `None` on failure
- Implements `start_stream(audio_queue, chunk_samples, device)`
  - If `device` is `None`, calls `find_monitor_device()` to auto-detect the active monitor source
  - If no monitor is found, falls back to sounddevice default input and prints a warning to stderr
  - Captures at the device's native sample rate (typically 48000 Hz for PipeWire), NOT at 16000 Hz
  - Resamples each chunk from native rate to 16000 Hz using `scipy.signal.resample_poly` before putting on the queue
  - Uses a mutable list `[buffer]` as a container to avoid nonlocal assignment issues in the callback
  - Audio callback slices buffer into capture-rate-sized chunks, resamples to 16kHz, normalizes amplitude, then puts on queue

### `visher_platform/audio_windows.py` — Windows only
- Implements `find_monitor_device() -> str | None`
  - Uses `sounddevice.query_devices()` to scan all devices
  - Looks for a device whose name contains `"Stereo Mix"`, `"What U Hear"`, or `"Loopback"` (case-insensitive) and has input channels > 0
  - Returns the device name string of the first match, or `None` if none found
  - Never raises — wraps in try/except and returns `None` on failure
- Implements `start_stream(audio_queue, chunk_samples, device)`
  - If `device` is `None`, calls `find_monitor_device()` to auto-detect a loopback/stereo mix device
  - If no loopback device is found, falls back to sounddevice default input and prints a warning to stderr
  - Captures at the device's native sample rate (query via `sounddevice.query_devices(device)['default_samplerate']`)
  - Resamples each chunk from native rate to 16000 Hz using `scipy.signal.resample_poly` if native rate differs from 16000
  - Uses a mutable list `[buffer]` as a container to avoid nonlocal assignment issues in the callback
  - Audio callback slices buffer into capture-rate-sized chunks, resamples to 16kHz, normalizes amplitude, then puts on queue

### `visher_platform/notify_linux.py` — Linux only
- Implements `notify(title, message, urgent)`
- Uses `plyer.notification.notify()`
- Sets urgency hint to critical (2) when `urgent=True` for libnotify-compatible daemons
- Always wraps in try/except — notification failure must never crash the pipeline

### `visher_platform/notify_windows.py` — Windows only
- Implements `notify(title, message, urgent)`
- Uses `plyer.notification.notify()`
- No urgency hint (not supported on Windows toast)
- Always wraps in try/except

---

## Audio Device Auto-Detection Logic

This is critical behavior — both platform audio modules must implement it consistently.

### Linux (`audio_linux.py`)
```
find_monitor_device():
  run: pactl list sources short
  for each line:
    if ".monitor" in line AND "RUNNING" in line:
      return parts[1]  # tab-separated: index, name, driver, format, state
  return None
```

### Windows (`audio_windows.py`)
```
find_monitor_device():
  for each device in sd.query_devices():
    if device has input channels > 0:
      if name contains any of: "stereo mix", "what u hear", "loopback" (case-insensitive):
        return device name
  return None
```

### Fallback behavior (both platforms)
If `find_monitor_device()` returns `None`:
- Print warning to stderr: `"[WARN] No loopback/monitor device found. Falling back to default input."`
- Pass `device=None` to sounddevice, which uses system default input
- Pipeline continues — never crash on device detection failure

---

## Amplitude Normalization

Both audio backends must normalize each chunk before putting it on the queue:

```python
max_val = np.max(np.abs(chunk))
if max_val > 0:
    chunk = (chunk / max_val * 0.9).astype(np.float32)
```

This ensures the YAMNet model always receives a properly leveled signal regardless of system volume. Skip normalization silently if the chunk is all zeros (silent).

---

## Sample Rate Handling

- `SAMPLE_RATE = 16000` in `config.py` is the **model's required input rate** — never change it
- Devices may operate at different native rates (commonly 48000 Hz on PipeWire/Linux, varies on Windows)
- Both audio backends must query the device's actual native rate and resample accordingly
- Resampling uses `scipy.signal.resample_poly`:
  - Compute GCD of native rate and 16000 to get exact integer ratio
  - Example: 48000 Hz → 16000 Hz = resample_poly(chunk, 1, 3)
  - Example: 44100 Hz → 16000 Hz = resample_poly(chunk, 160, 441)

---

## Tech Stack

| Component | Library | Notes |
|---|---|---|
| Audio capture | `sounddevice` | Cross-platform via PortAudio |
| Audio resampling | `scipy.signal.resample_poly` | Native rate → 16kHz |
| Audio encoding | `wave` + `numpy` | float32 → int16 PCM → WAV bytes in memory, never written to disk |
| Inference transport | `requests` | HTTP POST to local FastAPI server |
| Notifications | `plyer` | libnotify on Linux, toast on Windows |
| Device detection (Linux) | `subprocess` + `pactl` | Scans PipeWire monitor sources |
| Device detection (Windows) | `sounddevice.query_devices()` | Scans for Stereo Mix / loopback |
| CLI | `argparse` | stdlib only |

**Python version:** 3.10+
**Target platforms:** Linux (primary), Windows (secondary)

---

## Key Constants (`config.py`)

```python
CHUNK_DURATION_SEC = 3       # seconds per audio chunk sent to server
SAMPLE_RATE        = 16000   # Hz — must match YAMNet model input, never change
CHANNELS           = 1       # mono
SERVER_URL         = "http://localhost:8000/depfake"
REQUEST_TIMEOUT    = 10      # seconds
NOTIFICATION_TITLE = "VISHER"
NOTIFICATION_APP   = "VISHER Voice Detection"
```

`SAMPLE_RATE` is fixed at 16000 Hz because the YAMNet-based inference model requires it. Do not make this configurable or accept it as a CLI argument.

---

## CLI Flags (`capture.py`)

| Flag | Behavior |
|---|---|
| *(none)* | Production mode — notify only on `FAKE` detections, auto-detect monitor device |
| `--debug` | Debug mode — notify on every chunk result (`REAL` and `FAKE`) |
| `--device N` | Override auto-detection, use input device at index N |
| `--list` | Print available input devices and exit |

When `--device` is not specified, `start_stream()` calls `find_monitor_device()` automatically.

---

## Notification Behavior

- **Production mode:** fires a notification only when the server returns `FAKE`. Notification is marked urgent/critical.
- **Debug mode (`--debug`):** fires a notification on every chunk — `FAKE` (urgent) and `REAL` (normal).
- Consecutive `FAKE` detections each trigger their own notification — no suppression or debounce.
- Notification failures must never crash the pipeline. Always wrap `notification.notify()` in try/except.

---

## Coding Conventions

- **No global mutable state** outside of `config.py` constants.
- **Never block the audio callback.** All network I/O and notification calls belong in `inference_worker()`.
- **Fail gracefully.** Connection errors, timeouts, and bad server responses print a warning to stderr and continue — never raise to the main thread.
- **In-memory WAV only.** Never write audio chunks to disk. Use `io.BytesIO` + `wave`.
- **Type hints** on all function signatures.
- **f-strings** for all string formatting.
- **No third-party logging frameworks** — use `print(..., file=sys.stderr)` for errors/warnings, plain `print()` for normal output.
- All configurable values live in `config.py` only. Never hardcode values inline in other modules.
- Platform-specific code must never appear outside the `visher_platform/` directory.
- `capture.py` and `inference.py` must remain importable on both platforms without errors.
- Use `math.gcd` to compute resample ratios — never hardcode ratios like `1, 3`.

---

## Platform Notes

### Linux
- Notification daemon must be running (dunst, mako, swaync, or any libnotify-compatible daemon).
- System dep: `libnotify` (`sudo pacman -S libnotify` on Arch/EndeavourOS).
- System dep: `pactl` — part of `pipewire-pulse` or `pulseaudio-utils`, usually already present.
- Audio routed through PipeWire — monitor sources are named `*.monitor` and appear in `pactl list sources short`.
- `find_monitor_device()` scans for the first RUNNING monitor source automatically.

### Windows
- No extra system dependencies. plyer uses the native Windows notification API.
- PortAudio is bundled with the `sounddevice` wheel on Windows.
- WASAPI is the preferred backend for low-latency capture.
- Loopback capture requires "Stereo Mix" to be enabled in Windows Sound settings (Control Panel → Sound → Recording → Show Disabled Devices → Enable Stereo Mix).
- `find_monitor_device()` scans for Stereo Mix / What U Hear / Loopback device names automatically.

---

## What This Project Is NOT Responsible For

- Training or loading the ML model — that lives in `../server/`.
- The FastAPI server — managed separately in `../server/API/`.
- Audio file storage or logging of recorded audio.
- Any GUI beyond desktop notifications.
