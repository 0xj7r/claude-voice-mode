#!/bin/bash
# Start the TTS daemon (run in a separate terminal)
VOICE_MODE_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${VOICE_MODE_DIR}/venv/bin/python3"
exec "$PYTHON" -u "${VOICE_MODE_DIR}/tts_player.py" --daemon
