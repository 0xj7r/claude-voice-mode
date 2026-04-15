#!/bin/bash
# Toggle Claude Code voice mode on/off
# Usage: voice        (toggle)
#        voice on     (force on)
#        voice off    (force off)
#        voice status (show current state)
CONFIG="${HOME}/.claude/voice-mode/config.json"
PYTHON="${HOME}/.claude/voice-mode/venv/bin/python3"

current=$("$PYTHON" -c "
import json
with open('$CONFIG') as f:
    c = json.load(f)
print(c.get('tts', {}).get('enabled', True))
")

set_voice() {
    local val="$1"
    "$PYTHON" -c "
import json
with open('$CONFIG') as f:
    c = json.load(f)
c['tts']['enabled'] = $val
with open('$CONFIG', 'w') as f:
    json.dump(c, f, indent=2)
"
}

show_status() {
    if [ "$1" = "True" ]; then
        echo -e "\033[95m8==D\033[0m tts mode \033[92mon\033[0m  (! tts to toggle)"
    else
        echo -e "\033[90m8==D tts mode off\033[0m (! tts to toggle)"
    fi
}

case "${1:-}" in
    on)
        set_voice "True"
        show_status "True"
        ;;
    off)
        set_voice "False"
        show_status "False"
        ;;
    status)
        show_status "$current"
        ;;
    *)
        if [ "$current" = "True" ]; then
            set_voice "False"
            show_status "False"
        else
            set_voice "True"
            show_status "True"
        fi
        ;;
esac
