"""
Platform-specific module loader — detects OS and exposes unified interface.
Exposes: start_stream(), notify()
"""

import platform as platform_module
from typing import Callable

# Detect OS at import time
_system = platform_module.system()

if _system == "Linux":
    from .audio_linux import start_stream
    from .notify_linux import notify
elif _system == "Windows":
    from .audio_windows import start_stream
    from .notify_windows import notify
else:
    raise RuntimeError(f"Unsupported platform: {_system}")

__all__ = ["start_stream", "notify"]
