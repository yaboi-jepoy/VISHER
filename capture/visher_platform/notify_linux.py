"""
Linux notification backend using notify-send (libnotify).
"""

import sys


def notify(title: str, message: str, urgent: bool = False) -> None:
    """
    Fire a desktop notification on Linux via libnotify.
    
    Args:
        title: notification title
        message: notification message
        urgent: if True, use critical urgency (supported by libnotify)
    
    Notification failure never crashes the pipeline.
    """
    try:
        import subprocess
        urgency = "critical" if urgent else "normal"
        subprocess.run(
            ["notify-send", "-u", urgency, title, message],
            timeout=2,
            check=False,
        )
    except Exception as e:
        print(f"Notification failed: {e}", file=sys.stderr)
