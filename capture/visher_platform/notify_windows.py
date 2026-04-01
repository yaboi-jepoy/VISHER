"""
Windows notification backend using plyer (win32 toast).
"""

import sys
from plyer import notification


def notify(title: str, message: str, urgent: bool = False) -> None:
    """
    Fire a desktop notification on Windows via win32 toast.
    
    Args:
        title: notification title
        message: notification message
        urgent: ignored on Windows (toast doesn't support urgency)
    
    Notification failure never crashes the pipeline.
    """
    try:
        notification.notify(
            title=title,
            message=message,
            app_name="VISHER",
            timeout=5,  # seconds
        )
    except Exception as e:
        print(f"Notification failed: {e}", file=sys.stderr)
