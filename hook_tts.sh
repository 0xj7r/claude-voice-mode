#!/bin/bash
# Claude Code Stop hook: triggers TTS on assistant response
# Receives JSON on stdin

VOICE_MODE_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${VOICE_MODE_DIR}/venv/bin/python3"
LOG="${VOICE_MODE_DIR}/.hook.log"

if [ ! -f "$PYTHON" ]; then
    PYTHON="$(which python3)"
fi

# Log hook invocation for debugging
INPUT=$(cat)
echo "$(date): Hook fired, input length=${#INPUT}" >> "$LOG"
echo "$INPUT" | head -c 500 >> "$LOG"
echo "" >> "$LOG"

echo "$INPUT" | "$PYTHON" "${VOICE_MODE_DIR}/tts_player.py" 2>> "$LOG"
