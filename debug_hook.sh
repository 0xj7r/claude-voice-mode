#!/bin/bash
# Debug: log what the Stop hook receives
cat > /tmp/voice-mode-hook-input.json
echo "Hook fired at $(date)" >> /tmp/voice-mode-debug.log
cat /tmp/voice-mode-hook-input.json >> /tmp/voice-mode-debug.log
echo "" >> /tmp/voice-mode-debug.log
