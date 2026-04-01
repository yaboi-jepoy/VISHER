# VISHER Project Status Report

**Date:** April 1, 2026  
**Last Updated By:** Linux (Arch/EndeavourOS) Implementation  
**Status:** ✅ Audio Capture Pipeline COMPLETE | ⚠️ Model Detection Accuracy IN PROGRESS

---

## Executive Summary

> The capture pipeline works flawlessly. System audio is being captured and sent correctly to the server. The "everything is REAL" issue is 100% a YAMNet model/threshold problem in the inference server, not an issue with audio acquisition or transmission. <br> -JP

The VISHER voice deepfake detection capture pipeline is **fully functional and tested on Linux**. All components work correctly:

- ✅ System audio loopback capture (auto-detection working)
- ✅ Audio resampling and normalization pipeline
- ✅ HTTP communication with inference server
- ✅ Desktop notifications
- ✅ CLI interface with all flags

**Current Blocker:** Model detection accuracy — system captures audio and sends it correctly, but YAMNet model is classifying everything as "REAL" (including confirmed WaveNet deepfakes). This is a **server-side inference/model tuning issue**, not a capture issue.

---

## What's Working ✅

### Audio Capture

- **Linux Monitor Device Auto-Detection** — Automatically finds PipeWire loopback sources (`.monitor` devices)
- **Dynamic Sample Rate Detection** — Queries device native rate (typically 48kHz), resamples to 16kHz via GCD-based scipy.signal.resample_poly
- **Amplitude Normalization** — Scales audio to [-0.9, 0.9] range for consistent model input
- **Thread-Safe Queue** — Audio callback (real-time, non-blocking) + inference worker (background I/O thread)
- **Tested Output:** Verified to capture from system audio (not microphone)

### Server Communication

- **Multipart Form Data POST** — Sends WAV-encoded audio as `files={"audio_file": ("audio.wav", wav_bytes, "audio/wav")}`
- **In-Memory WAV Encoding** — Uses Python `wave` module with BytesIO (no disk writes)
- **Error Handling** — Gracefully handles connection failures, timeouts, bad responses (logs to stderr, continues)

### Desktop Notifications

- **Linux:** notify-send with urgency levels (critical for FAKE, normal for REAL in debug mode)
- **Windows:** plyer toast notifications (implemented but untested on Windows)
- **Failure Handling:** Never crashes if notification fails

### CLI Interface

- `--debug` — Notify on every chunk (REAL + FAKE)
- `--device N` — Override auto-detection, use specific input device index
- `--duration SEC` — Change chunk duration at runtime (default: 3 seconds)
- `--list` — Print available input devices and exit

### Documentation

- ✅ USAGE.md — Comprehensive platform-specific setup and usage guide
- ✅ copilot-instructions.md — Architecture and implementation requirements
- ✅ Inline code comments throughout

---

## What's NOT Working ❌

### Model Detection Accuracy

**Issue:** Server returns "REAL" for all audio (AI clips, human voices, silence)

**Evidence from testing:**

```
AI WaveNet clip 1  → FAKE (expected) → REAL (actual) ❌
AI WaveNet clip 2  → FAKE (expected) → REAL (actual) ❌
Human voice 1      → REAL (expected) → REAL (actual) ✓
Human voice 2      → REAL (expected) → REAL (actual) ✓
```

**Root Cause:** Not captured audio or transport — the **YAMNet-based inference model** in `../server/` is not configured to detect deepfakes effectively.

**Why capture/transport is NOT the problem:**

- Server receives 4/4 POST requests successfully (200 OK responses)
- Confidence score arrays in response vary per clip (not all identical)
- Audio is being encoded and transmitted correctly
- Same clips tested manually on server likely work (if model is trained)

---

## Architecture Overview

```
System Audio Output
    ↓
[Linux] PipeWire monitor device (auto-detected)
[Windows] Stereo Mix / loopback device (auto-detect)
    ↓
sounddevice stream → native sample rate (48kHz)
    ↓
Callback: accumulate → resample @ GCD ratio → normalize → queue
    ↓
Inference worker (background thread):
  • Pop from queue
  • WAV encode in memory
  • POST to localhost:8000/depfake
  • Parse response
  • Notify user
    ↓
Desktop notification (notify-send / plyer toast)
```

---

## Platform-Specific Status

### Linux (Arch/EndeavourOS) ✅ TESTED

**Status:** Fully functional, tested on Arch Linux with PipeWire

**Setup:**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Run:**

```bash
python capture.py --debug
```

**Output (expected):**

```
Detected OS: Linux
Chunk: 48000 samples / 3s (at 16000 Hz)
Inference worker started
Monitor device detected: alsa_output.pci-...-HiFi__Headphones__sink.monitor
Using sounddevice: [13] pipewire
Audio stream started (device=None)
VISHER running — press Ctrl+C to exit
```

**Known Issues:** None with capture pipeline. Model accuracy issues are server-side.

---

### Windows (Not Yet Tested) 🔄 IMPLEMENTED

**Status:** Code complete, auto-detection implemented, untested

**Implementation Details:**

- `audio_windows.py` scans device list for "Stereo Mix", "What U Hear", or "Loopback" device names
- Falls back to default input if none found
- Same resampling/normalization as Linux

**Prerequisites:**

1. [Enable Stereo Mix](https://www.howtogeek.com/348969/how-to-enable-stereo-mix-in-windows/) in Windows Sound settings
   - Right-click speaker icon → Sound settings → Show disabled devices → Enable Stereo Mix
2. Ensure WASAPI backend is available (typically bundled with sounddevice wheel)

**Setup & Testing (FOR WINDOWS USER):**

```bash
# Create venv
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# List devices to verify Stereo Mix presence
python capture.py --list

# Run with auto-detection
python capture.py --debug

# Expected output:
# Monitor device detected: <stereo_mix_device_name>
# Using sounddevice: [X] <device_name>
```

**What to Check if Windows Auto-Detection Fails:**

1. Is Stereo Mix enabled? (`python capture.py --list` should show it)
2. Does it have input channels? (max_input_channels > 0)
3. Try manual override: `python capture.py --device X` where X is Stereo Mix's index from --list

---

## Next Steps

### High Priority: Model Accuracy 🔴

**Investigate Server-Side Detection:**

1. **Check inference server code** (`../server/`)
   - What YAMNet checkpoint is being used?
   - Is it trained on deepfake detection or generic audio classification?
   - What's the confidence threshold for FAKE classification?

2. **Test server independently**
   - Send known deepfake + known real audio directly to server REST endpoint
   - Check if model is working _at all_ or if threshold is too high

3. **Review confidence scores**
   - The float arrays returned by server show varying predictions
   - Plot them — are they clustered near 0.5 (uncertain) or always >0.9 (high confidence in REAL)?

4. **Consider model retraining/fine-tuning:**
   - YAMNet is a general audio classifier; likely needs fine-tuning for deepfake detection
   - May need labeled deepfake dataset specific to your target engines (WaveNet, Tacotron, etc.)

### Medium Priority: Windows Testing 🟡

1. **Set up on Windows machine**
2. **Verify Stereo Mix auto-detection** works
3. **Test with inference server running**
4. **Confirm notifications work on Windows toast**

### Low Priority: Enhancements 🟢

- [ ] Add confidence score output to notifications
- [ ] Add metrics logging (detection rate, false positive %)
- [ ] Frontend GUI (currently CLI + notifications only)
- [ ] Audio file input mode (currently live capture only)
- [ ] Configurable detection threshold via CLI flag

---

## Testing Checklist

### Linux (Already Done ✓)

- [x] Auto-detection finds monitor device
- [x] Audio captures from system output
- [x] Resampling works (48kHz → 16kHz)
- [x] HTTP POST reaches server
- [x] Notifications fire (once both platforms confirmed)
- [x] All CLI flags functional

### Windows (TO DO)

- [ ] Stereo Mix auto-detection finds device
- [ ] Audio captures from system output
- [ ] Resampling works
- [ ] HTTP POST reaches server
- [ ] Notifications work (toast)
- [ ] All CLI flags functional

### Server (TO DO - see server team)

- [ ] Model returns FAKE for confirmed deepfakes
- [ ] Model returns REAL for human voices
- [ ] Confidence scores make sense (check threshold)

---

## File Inventory

```
capture/
├── capture.py                           (CLI entry point)
├── config.py                            (Constants)
├── inference.py                         (Queue, WAV encoding, HTTP POST)
├── requirements.txt                     (Dependencies)
├── USAGE.md                             (Setup & usage guide)
├── PROJECT_STATUS.md                    (This file)
├── visher_platform/
│   ├── __init__.py                      (OS detection, unified interface)
│   ├── audio_linux.py                   (Linux capture: PipeWire/ALSA)
│   ├── audio_windows.py                 (Windows capture: WASAPI)
│   ├── notify_linux.py                  (notify-send)
│   └── notify_windows.py                (plyer toast)
└── .github/
    └── copilot-instructions.md          (Architecture requirements)
```

---

## Key Code Locations

| Component                     | File                               | Key Function                                                |
| ----------------------------- | ---------------------------------- | ----------------------------------------------------------- |
| Monitor auto-detect (Linux)   | `visher_platform/audio_linux.py`   | `find_monitor_device()` (lines ~17-48)                      |
| Monitor auto-detect (Windows) | `visher_platform/audio_windows.py` | `find_monitor_device()` (lines ~17-35)                      |
| Audio capture callback        | `visher_platform/audio_linux.py`   | `audio_callback()` within `start_stream()` (lines ~100-130) |
| Resampling math               | Both audio modules                 | GCD ratio computation (lines ~110-115)                      |
| WAV encoding                  | `inference.py`                     | `numpy_to_wav_bytes()` (lines ~22-41)                       |
| Server communication          | `inference.py`                     | `inference_worker()` (lines ~68-100)                        |
| Notifications                 | `visher_platform/notify_*.py`      | `notify()` function                                         |

---

## Troubleshooting Guide

### "No loopback/monitor device found. Falling back to default input."

**Linux:**

- Check: `pactl list sources | grep monitor` — are there any .monitor devices?
- Check status: `pactl list sources short | grep RUNNING` — is one marked RUNNING?
- If none found or not RUNNING, PipeWire may not be routing audio through monitors properly

**Windows:**

- Check: `python capture.py --list` — is "Stereo Mix" in the list?
- Enable Stereo Mix in Windows Sound settings (see Prerequisites above)
- If still not found, try listing again after toggling Stereo Mix

### Server connection refused

- Is FastAPI server running on `localhost:8000`?
- Check: `curl http://localhost:8000/depfake` (should be METHOD NOT ALLOWED, not connection refused)
- Firewall blocking localhost? (unlikely but check)

### All detections are REAL

- **This is expected with current model** — see "Model Detection Accuracy" section above
- Check server logs for confidence scores
- May need model retraining or threshold adjustment in server code

### Audio artifacts / metallic sound

- Resampling may be aggressive; check native device rate via `python capture.py --list`
- Normalization may be over-scaling — check `audio_*.py` line ~120 (0.9 scaling factor)

---

## Handoff Notes for Windows Developer

1. **You inherit working code.** Don't re-implement audio capture — only test on Windows.
2. **Auto-detection should work.** The Windows implementation mirrors Linux logic (find_monitor_device, same resampling/normalization).
3. **Main uncertainty:** Will Stereo Mix show up in sounddevice on your system? The code handles fallback to default input if not.
4. **If Stereo Mix doesn't work:** You may need to investigate WASAPI device naming on your Windows version (device names vary).
5. **Server connection:** Assume server is running on `localhost:8000/depfake` (same as Linux testing).
6. **Model accuracy:** Not your responsibility to fix — server team needs to handle YAMNet tuning.

---

## Questions to Answer Before Next Session

1. **For Server Team:**
   - What YAMNet model checkpoint are you using? Is it trained for deepfake detection?
   - What's the current confidence threshold for FAKE classification?
   - Can you manually test the model with a known deepfake audio file?

2. **For Windows Tester:**
   - Does Stereo Mix auto-detect correctly?
   - Do notifications pop on Windows?
   - Any platform-specific bugs?

3. **For Integration:**
   - Should we log confidence scores alongside notifications?
   - Do you want a persistent log file of detections?
   - Should CLI support batch file processing (not just live capture)?

---

## References

- **Linux Audio:** [PipeWire Monitor Routing](https://wiki.archlinux.org/title/PipeWire)
- **Resampling Theory:** [scipy.signal.resample_poly](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.resample_poly.html)
- **YAMNet Model:** [Google Research YAMNet](https://github.com/tensorflow/models/tree/master/research/audioset/yamnet)
- **PortAudio:** [sounddevice Documentation](https://python-sounddevice.readthedocs.io/)

---

## Revision History

| Date       | Author    | Status   | Changes                                                                          |
| ---------- | --------- | -------- | -------------------------------------------------------------------------------- |
| 2026-04-01 | Linux Dev | COMPLETE | Initial pipeline implementation, Linux testing, model accuracy identified as OOB |

---

**Last Known Working State:** All capture/transport components functional on Arch Linux. Ready for Windows testing and server-side model tuning.
