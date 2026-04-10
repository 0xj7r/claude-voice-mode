# Roadmap

## Done

- [x] Kokoro TTS: local text-to-speech (82M param model, near-commercial quality)
- [x] Braille orb animation: white, round, centered, amplitude-reactive
- [x] Stop hook: fires after every Claude response, sends text to daemon
- [x] Daemon architecture: single process handles TTS + STT + orb display
- [x] Socket IPC: hook sends text to daemon via Unix socket
- [x] faster-whisper STT: sub-1s transcription (model stays warm in memory)
- [x] Hotkey recording: Ctrl+Shift+V to start/stop recording
- [x] Auto-submit: transcribed text typed + Enter pressed into Claude Code
- [x] Interrupt: hotkey stops TTS mid-playback, starts recording
- [x] Toggle: `! tts` to enable/disable from Claude Code
- [x] One-command installer: `bash install.sh`
- [x] 25 unit tests for text processing, transcript parsing, socket comms

## In Progress

- [ ] Hook piping fix: `echo | exec` breaks pipe, needs `echo | python` (fix committed, needs verification)
- [ ] Verify full voice loop end-to-end: speak -> transcribe -> submit -> Claude responds -> TTS + orb

## Known Issues

- macOS Accessibility permission required for hotkey listener (System Settings > Privacy & Security > Accessibility)
- First daemon start takes ~20s to load whisper model (subsequent transcriptions are <1s)
- Orb only visible in daemon terminal (Claude Code terminal shows text only)

## Future

- [ ] Configurable auto-submit (some users may want to review before sending)
- [ ] Voice activity detection (VAD) for hands-free recording start/stop
- [ ] Wake word detection ("Hey Claude") for fully conversational mode
- [ ] Streaming TTS: start speaking first sentence while synthesizing the rest
- [ ] Multiple voice presets (switch between voices via config or command)
- [ ] Volume normalization across different response lengths
- [ ] Linux support (currently macOS-only due to osascript for keystroke injection)
- [ ] Publish as installable package (pip or brew)
