#!/bin/bash
# Stop active TTS playback instantly
PID_FILE="${HOME}/.claude/voice-mode/.tts.pid"

if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        kill -USR1 "$pid"
        echo "TTS stopped."
    else
        rm -f "$PID_FILE"
        echo "No active TTS."
    fi
else
    echo "No active TTS."
fi
