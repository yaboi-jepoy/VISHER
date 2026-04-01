"""
VISHER configuration — all platform-independent constants.
No logic, no imports beyond stdlib.
"""

# Audio capture settings
CHUNK_DURATION_SEC = 3      # seconds per audio chunk sent to server
SAMPLE_RATE = 16000         # Hz — must match YAMNet model input, never change
CHANNELS = 1                # mono

# Server communication
SERVER_URL = "http://localhost:8000/depfake"
REQUEST_TIMEOUT = 10        # seconds

# Notifications
NOTIFICATION_TITLE = "VISHER"
NOTIFICATION_APP = "VISHER Voice Detection"
