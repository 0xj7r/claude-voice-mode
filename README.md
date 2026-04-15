![Status: In Development](https://img.shields.io/badge/status-in%20development-yellow)

# Claude Code Voice Mode

Talk to Claude. Claude talks back. Local TTS and STT for Claude Code. No APIs, no cloud, no cost.

## What it does

You press a hotkey and speak. `faster-whisper` transcribes locally in under a second and auto-submits the text to Claude Code. When Claude responds, a Stop hook pipes the response into Kokoro TTS, which reads it aloud. A pulsing orb in your terminal reflects the audio amplitude while it speaks.

Everything runs on your machine. Apple Silicon is where it's tuned.

## Features

- Local STT via `faster-whisper` (fast, no API)
- Local TTS via Kokoro ONNX (natural voice, no API)
- Hotkey-driven capture (default: `Ctrl+Shift+V`)
- Auto-submit after transcription
- Stop hook integration: Claude responses speak automatically
- Amplitude-reactive orb animation in the daemon terminal
- Toggle TTS on/off from within a Claude Code session (`! tts`)
- Works fully offline after initial model download (~480 MB)

## Install

```bash
git clone https://github.com/0xj7r/claude-voice-mode.git ~/.claude/voice-mode
cd ~/.claude/voice-mode
bash scripts/install.sh
```

First run downloads Kokoro model (~370 MB), voices (~42 MB), and Whisper base.en (~142 MB). Takes a few minutes.

## Usage

Two terminals.

**Terminal 1** (voice daemon, shows the orb):
```bash
bash ~/.claude/voice-mode/scripts/daemon.sh
```

**Terminal 2** (Claude Code):
```bash
claude
```

Press `Ctrl+Shift+V` in the Claude Code terminal to speak. Your transcription is typed and submitted. Claude's replies are spoken aloud in terminal 1 with the orb pulsing to the audio.

Toggle TTS from inside Claude Code:
```
! tts
```

## How it works

```
Daemon terminal                    Claude Code terminal

Ctrl+Shift+V                       User types or pastes
    |                                     |
    v                                     v
Record microphone              Claude processes and responds
    |                                     |
    v                                     v
faster-whisper transcribes     Stop hook fires on response
    |                                     |
    +---- types into Claude ----+         |
                                          v
                            Kokoro TTS synthesizes
                                          |
                            Audio streams to daemon
                                          |
                                          v
                       Orb pulses with amplitude in daemon terminal
```

The daemon is a single Python process managing two loops: a hotkey listener for STT, and a Unix-socket server for receiving text from the Stop hook to play via TTS.

## Requirements

- macOS with Apple Silicon (Intel not tested)
- Python 3.12+
- Claude Code CLI
- Accessibility permission for your terminal app (System Settings, Privacy and Security, Accessibility)
- Homebrew for `whisper-cpp` (optional, improves STT)

## Project layout

```
src/          Python runtime: TTS player, voice daemon, orb animator
scripts/      Shell scripts: install, daemon, hook, toggle
tests/        Unit tests for TTS text cleaning and sentence splitting
config.json   User-facing config (TTS voice, rate, enabled)
setup.py      Python-only setup (alternative to scripts/install.sh)
```

## Roadmap

In active development. Planned:
- Intel Mac support
- Linux support (pulseaudio or pipewire)
- Alternative wake-word STT (continuous listening)
- Multi-voice selection per conversation context
- Streaming TTS (speak as Claude streams, not after)

See [ROADMAP.md](ROADMAP.md).

## License

MIT. See [LICENSE](LICENSE).
