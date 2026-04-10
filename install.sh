#!/bin/bash
set -euo pipefail

# Claude Code Voice Mode Installer
# One-command setup: curl -sSL <url> | bash

VOICE_DIR="${HOME}/.claude/voice-mode"
MODELS_DIR="${VOICE_DIR}/models"
SETTINGS="${HOME}/.claude/settings.json"

KOKORO_MODEL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
KOKORO_VOICES="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
WHISPER_MODEL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"

cyan="\033[96m"
green="\033[92m"
yellow="\033[93m"
red="\033[91m"
reset="\033[0m"
bold="\033[1m"

step() { echo -e "\n${cyan}${bold}[$1/6]${reset} $2"; }
ok()   { echo -e "  ${green}✓${reset} $1"; }
warn() { echo -e "  ${yellow}!${reset} $1"; }
fail() { echo -e "  ${red}✗${reset} $1"; exit 1; }

echo -e "${bold}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║   Claude Code Voice Mode Installer   ║"
echo "  ╚══════════════════════════════════════╝"
echo -e "${reset}"

# 1. Check prerequisites
step 1 "Checking prerequisites..."

if ! command -v python3 &>/dev/null; then
    fail "python3 not found. Install Python 3.12+ first."
fi
PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
ok "Python ${PYVER}"

if command -v brew &>/dev/null; then
    ok "Homebrew found"
    HAS_BREW=1
else
    warn "Homebrew not found (whisper-cpp STT won't be available)"
    HAS_BREW=0
fi

# 2. Create directory and venv
step 2 "Setting up virtual environment..."

mkdir -p "${VOICE_DIR}" "${MODELS_DIR}"

if [ ! -d "${VOICE_DIR}/venv" ]; then
    python3 -m venv "${VOICE_DIR}/venv"
    ok "Created venv"
else
    ok "Venv already exists"
fi

# 3. Install Python dependencies
step 3 "Installing Python packages..."

"${VOICE_DIR}/venv/bin/pip" install -q --upgrade pip
"${VOICE_DIR}/venv/bin/pip" install -q kokoro-onnx sounddevice numpy rich pynput
ok "Installed: kokoro-onnx, sounddevice, numpy, rich, pynput"

# 4. Download models (parallel)
step 4 "Downloading models (this may take a few minutes)..."

download() {
    local url="$1" dest="$2" label="$3"
    if [ -f "$dest" ] && [ -s "$dest" ]; then
        ok "${label} (cached)"
        return
    fi
    echo -e "  Downloading ${label}..."
    curl -sSL -o "$dest" "$url"
    local size=$(du -h "$dest" | cut -f1 | xargs)
    ok "${label} (${size})"
}

download "$KOKORO_MODEL"  "${MODELS_DIR}/kokoro-v1.0.onnx" "Kokoro TTS model" &
download "$KOKORO_VOICES" "${MODELS_DIR}/voices-v1.0.bin"   "Kokoro voices"    &
download "$WHISPER_MODEL" "${MODELS_DIR}/ggml-base.en.bin"  "Whisper STT model" &
wait
ok "All models ready"

# 5. Install whisper-cpp
step 5 "Setting up whisper-cpp for STT..."

if command -v whisper-cli &>/dev/null; then
    ok "whisper-cli already installed"
elif [ "$HAS_BREW" -eq 1 ]; then
    if brew list whisper-cpp &>/dev/null; then
        ok "whisper-cpp installed via brew"
    else
        echo "  Installing whisper-cpp via brew..."
        brew install whisper-cpp -q
        ok "whisper-cpp installed"
    fi
else
    warn "Skipping whisper-cpp (no Homebrew). Voice input won't work."
    warn "Install manually: brew install whisper-cpp"
fi

# 6. Configure Claude Code hook
step 6 "Configuring Claude Code hook..."

chmod +x "${VOICE_DIR}/hook_tts.sh"

if [ -f "$SETTINGS" ]; then
    if grep -q "hook_tts.sh" "$SETTINGS" 2>/dev/null; then
        ok "Hook already configured in settings.json"
    else
        # Use Python to safely merge the hook into existing settings
        "${VOICE_DIR}/venv/bin/python3" -c "
import json, sys

with open('${SETTINGS}') as f:
    settings = json.load(f)

hooks = settings.setdefault('hooks', {})
stop = hooks.setdefault('Stop', [])
stop.append({
    'matcher': '',
    'hooks': [{
        'type': 'command',
        'command': '${VOICE_DIR}/hook_tts.sh',
        'timeout': 120
    }]
})

with open('${SETTINGS}', 'w') as f:
    json.dump(settings, f, indent=2)
"
        ok "Added Stop hook to settings.json"
    fi
else
    mkdir -p "$(dirname "$SETTINGS")"
    cat > "$SETTINGS" << 'ENDJSON'
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/voice-mode/hook_tts.sh",
            "timeout": 120
          }
        ]
      }
    ]
  }
}
ENDJSON
    ok "Created settings.json with hook"
fi

# Done
echo ""
echo -e "${green}${bold}  ✓ Voice mode installed!${reset}"
echo ""
echo "  TTS is now active. Claude's responses will be spoken aloud."
echo ""
echo "  For voice input (STT), run in a separate terminal:"
echo -e "    ${cyan}~/.claude/voice-mode/venv/bin/python3 ~/.claude/voice-mode/voice_daemon.py${reset}"
echo ""
echo "  Config: ${VOICE_DIR}/config.json"
echo "  Test:   ${VOICE_DIR}/venv/bin/python3 ${VOICE_DIR}/test_tts.py"
echo ""
echo "  To disable TTS, set \"enabled\": false in config.json"
echo ""
