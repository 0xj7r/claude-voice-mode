#!/bin/bash
# Claude Code Stop hook: triggers TTS on assistant response
# Receives JSON on stdin with transcript_path

VOICE_MODE_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${VOICE_MODE_DIR}/venv/bin/python3"

if [ ! -f "$PYTHON" ]; then
    PYTHON="$(which python3)"
fi

exec "$PYTHON" "${VOICE_MODE_DIR}/tts_player.py"
