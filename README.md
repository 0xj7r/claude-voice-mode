# Claude Code Voice Mode

Local TTS/STT voice interface for Claude Code. Speaks Claude's responses aloud with a pulsing terminal orb animation, and lets you talk back via hotkey.

All processing runs locally on your machine. No API calls, no cloud services, no cost.

## Demo

When Claude responds, you'll see a pulsing braille-character orb in your terminal and hear the response spoken aloud via Kokoro TTS:

```
       ⣀⣤⣴⣶⣶⣶⣷⣶⣶⣶⣤⣄⡀
     ⢠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦
     ⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠁
      ⠈⠛⠿⢿⣿⣿⣿⣿⣿⣿⣿⠿⠟⠋
```

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.12+
- Homebrew (for whisper-cpp STT)
- Claude Code CLI

## Install

```bash
git clone https://github.com/0xj7r/claude-voice-mode.git ~/.claude/voice-mode
cd ~/.claude/voice-mode
bash install.sh
```

The installer handles everything:
1. Creates a Python venv and installs dependencies
2. Downloads Kokoro TTS model (~310 MB), voices (~27 MB), and Whisper STT model (~141 MB)
3. Installs whisper-cpp via Homebrew
4. Configures the Claude Code Stop hook in `~/.claude/settings.json`

## How It Works

### TTS (Claude speaks to you)

A Claude Code [Stop hook](https://docs.anthropic.com/en/docs/claude-code/hooks) fires after every response. It reads the transcript, extracts Claude's last message, strips markdown, and streams it through [Kokoro TTS](https://github.com/thewh1teagle/kokoro-onnx) (82M parameter model, near-commercial quality). A pulsing orb animates in your terminal during playback, driven by real-time audio amplitude.

### STT (you speak to Claude)

Run the voice daemon in a separate terminal. Press `Ctrl+Shift+V` to start recording, press again to stop. Your speech is transcribed locally via [whisper.cpp](https://github.com/ggerganov/whisper.cpp) and typed into the Claude Code prompt.

### Interrupt

Press the hotkey while TTS is playing to stop it immediately and start recording. The interrupt is instant (mid-sentence).

You can also stop TTS from any terminal:

```bash
~/.claude/voice-mode/stop_tts.sh
```

## Usage

TTS activates automatically after install (via the Stop hook).

For voice input, run the daemon in a separate terminal:

```bash
~/.claude/voice-mode/venv/bin/python3 ~/.claude/voice-mode/voice_daemon.py
```

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
    "color": "cyan"
  }
}
```

### TTS voices

Kokoro includes ~50 voices. Some good ones:
- `af_heart` (default, warm female)
- `af_sky` (clear female)
- `am_adam` (male)
- `bf_emma` (British female)
- `bm_george` (British male)

### Animation colors

`cyan`, `green`, `magenta`, `blue`, `white`

## Architecture

```
hook_tts.sh          Stop hook entry point (called by Claude Code)
  └─ tts_player.py   Reads transcript, cleans text, streams TTS
       └─ orb_animator.py   Braille-character pulsing orb

voice_daemon.py      Hotkey listener + mic recording + whisper.cpp STT
stop_tts.sh          Kill active TTS via SIGUSR1
install.sh           One-command installer
```

## Stack

| Component | Library | Size |
|-----------|---------|------|
| TTS | [Kokoro ONNX](https://github.com/thewh1teagle/kokoro-onnx) | 310 MB model |
| STT | [whisper.cpp](https://github.com/ggerganov/whisper.cpp) | 141 MB model |
| Audio | [sounddevice](https://python-sounddevice.readthedocs.io/) | via PortAudio |
| Animation | Custom braille renderer | ~5 KB |

## Uninstall

Remove the hook from `~/.claude/settings.json` (delete the `hooks.Stop` entry), then:

```bash
rm -rf ~/.claude/voice-mode
```

## License

MIT
