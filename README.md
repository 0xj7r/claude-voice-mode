# Claude Code Voice Mode

```
                        ⣠⣴⣶⣿⣿⣿⣷⣶⣦⣄
                      ⣰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡀
                     ⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄
                     ⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
                     ⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿
                     ⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏
                      ⠘⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠋
                        ⠙⠻⣿⣿⣿⣿⣿⣿⠿⠛⠁
```

Talk to Claude. Claude talks back.

Local TTS and STT for Claude Code. No APIs, no cloud, no cost. Just your voice and a pulsing orb.

## What It Does

**You speak** → hotkey records → faster-whisper transcribes (<1s) → auto-submits to Claude

**Claude responds** → Stop hook fires → Kokoro TTS speaks → orb pulses with audio

All local. All free. Apple Silicon optimized.

## Install

```bash
git clone https://github.com/0xj7r/claude-voice-mode.git ~/.claude/voice-mode
cd ~/.claude/voice-mode
bash install.sh
```

Downloads ~480 MB of models on first run. Takes a few minutes.

## Usage

**Terminal 1** (voice terminal):
```bash
~/.claude/voice-mode/daemon.sh
```

**Terminal 2** (Claude Code):
```bash
claude
```

Press `Ctrl+Shift+V` to speak. Claude's responses are spoken aloud with a pulsing orb in Terminal 1.

Toggle TTS from Claude Code:
```
! tts
```

## Requirements

- macOS with Apple Silicon
- Python 3.12+
- Claude Code CLI
- Accessibility permission for your terminal app (System Settings > Privacy & Security > Accessibility)

## How It Works

```
┌─────────────────────────────────┐     ┌──────────────────────────┐
│  Daemon Terminal                │     │  Claude Code Terminal     │
│                                 │     │                          │
│  Ctrl+Shift+V → record mic     │     │                          │
│  faster-whisper → transcribe    │────>│  Text typed + submitted  │
│                                 │     │                          │
│         ⣠⣴⣶⣿⣿⣿⣷⣶⣦⣄              │     │  Claude responds         │
│       ⣰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡀           │<────│  Stop hook fires         │
│       ⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿           │     │                          │
│       ⠘⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠋           │     │                          │
│  Kokoro TTS → audio playback   │     │                          │
│  Orb pulses with amplitude     │     │                          │
└─────────────────────────────────┘     └──────────────────────────┘
```

The daemon runs as a single process:
- **Socket listener** (background thread): receives text from Claude Code's Stop hook via Unix socket
- **Hotkey listener** (main thread): records mic, transcribes with faster-whisper, types into Claude Code
- **Orb renderer**: braille-character circle, amplitude-reactive, centered in terminal

## Configuration

Edit `~/.claude/voice-mode/config.json`:

```json
{
  "tts": {
    "voice": "af_heart",
    "speed": 1.1,
    "enabled": true
  },
  "stt": {
    "model": "base.en",
    "hotkey": "<ctrl>+<shift>+v",
    "enabled": true
  },
  "animation": {
    "radius": 8,
    "fps": 15,
    "color": "white"
  }
}
```

### Voices

Kokoro ships with ~50 voices:

| Voice | Description |
|-------|-------------|
| `af_heart` | Warm female (default) |
| `af_sky` | Clear female |
| `am_adam` | Male |
| `bf_emma` | British female |
| `bm_george` | British male |

### Controls

| Action | How |
|--------|-----|
| Toggle TTS | `! tts` in Claude Code |
| Record voice | `Ctrl+Shift+V` (press again to stop) |
| Stop TTS mid-speech | Press hotkey while speaking |
| Stop TTS from shell | `~/.claude/voice-mode/stop_tts.sh` |

## Stack

| Component | Library | Notes |
|-----------|---------|-------|
| TTS | [Kokoro ONNX](https://github.com/thewh1teagle/kokoro-onnx) | 82M params, ~310 MB |
| STT | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | tiny.en, <1s transcription |
| Audio | [sounddevice](https://python-sounddevice.readthedocs.io/) | PortAudio bindings |
| Animation | Custom braille renderer | Sub-character resolution circle |

## Uninstall

```bash
# Remove hook from settings
# (delete the hooks.Stop entry in ~/.claude/settings.json)

# Remove files
rm -rf ~/.claude/voice-mode
```

## License

MIT
