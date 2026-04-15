#!/usr/bin/env python3
"""
Voice Daemon: listens for a hotkey, records audio, transcribes via whisper.cpp,
and types the result into the active terminal.
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time

import numpy as np
import sounddevice as sd

VOICE_MODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(VOICE_MODE_DIR, "config.json")

SAMPLE_RATE = 16000
CHANNELS = 1
RECORDING = False
AUDIO_CHUNKS: list[np.ndarray] = []


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def find_whisper_cpp() -> str | None:
    """Find whisper-cpp binary."""
    for name in ["whisper-cli", "whisper-cpp", "whisper", "main"]:
        result = subprocess.run(["which", name], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()

    for name in ["whisper-cli", "whisper-cpp"]:
        brew_path = f"/opt/homebrew/bin/{name}"
        if os.path.exists(brew_path):
            return brew_path

    return None


def find_whisper_model(model_name: str = "base.en") -> str | None:
    """Find the whisper model file."""
    model_dir = os.path.join(VOICE_MODE_DIR, "models")
    model_file = f"ggml-{model_name}.bin"

    local_path = os.path.join(model_dir, model_file)
    if os.path.exists(local_path):
        return local_path

    brew_model = f"/opt/homebrew/share/whisper-cpp/models/{model_file}"
    if os.path.exists(brew_model):
        return brew_model

    return None


def record_audio() -> np.ndarray | None:
    """Record audio until RECORDING is set to False."""
    global RECORDING, AUDIO_CHUNKS
    AUDIO_CHUNKS = []
    RECORDING = True

    def callback(indata, frames, time_info, status):
        if RECORDING:
            AUDIO_CHUNKS.append(indata.copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="float32", callback=callback
    ):
        indicator_chars = ["🔴", "⚫"]
        i = 0
        while RECORDING:
            sys.stderr.write(f"\r  {indicator_chars[i % 2]} Recording... (press hotkey to stop)")
            sys.stderr.flush()
            i += 1
            time.sleep(0.5)

    sys.stderr.write("\r" + " " * 60 + "\r")
    sys.stderr.flush()

    if not AUDIO_CHUNKS:
        return None

    return np.concatenate(AUDIO_CHUNKS, axis=0)


def transcribe(audio: np.ndarray, whisper_bin: str, model_path: str) -> str:
    """Transcribe audio using whisper.cpp."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name

    try:
        import wave

        audio_int16 = (audio * 32767).astype(np.int16)
        with wave.open(wav_path, "w") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())

        sys.stderr.write("\r  Transcribing...\r")
        sys.stderr.flush()

        result = subprocess.run(
            [whisper_bin, "-m", model_path, "-f", wav_path, "--no-timestamps", "-nt"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        sys.stderr.write("\r" + " " * 40 + "\r")
        sys.stderr.flush()

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            sys.stderr.write(f"[voice-mode] whisper error: {result.stderr}\n")
            return ""
    finally:
        os.unlink(wav_path)


def stop_active_tts():
    """Kill any active TTS playback."""
    pid_path = os.path.join(VOICE_MODE_DIR, ".tts.pid")
    if not os.path.exists(pid_path):
        return False

    try:
        with open(pid_path) as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGUSR1)
        sys.stderr.write("\r  [TTS interrupted]\n")
        return True
    except (ProcessLookupError, ValueError, FileNotFoundError):
        return False


def type_text(text: str):
    """Type text into the active terminal using osascript."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
    tell application "System Events"
        keystroke "{escaped}"
    end tell
    '''
    subprocess.run(["osascript", "-e", script], capture_output=True)


def main():
    import signal as sig
    from pynput import keyboard

    config = load_config()
    stt_config = config.get("stt", {})

    if not stt_config.get("enabled", True):
        print("[voice-mode] STT disabled in config")
        sys.exit(0)

    whisper_bin = find_whisper_cpp()
    if not whisper_bin:
        print("[voice-mode] whisper-cpp not found. Run: brew install whisper-cpp")
        sys.exit(1)

    model_name = stt_config.get("model", "base.en")
    model_path = find_whisper_model(model_name)
    if not model_path:
        print(f"[voice-mode] Whisper model '{model_name}' not found. Run: python setup.py")
        sys.exit(1)

    hotkey_str = stt_config.get("hotkey", "<ctrl>+<shift>+v")
    print(f"[voice-mode] Voice daemon running. Press {hotkey_str} to talk.")
    print("[voice-mode] Pressing hotkey while TTS is playing stops it first.")
    print("[voice-mode] Press Ctrl+C to quit.\n")

    recording_thread = None

    def toggle_recording():
        global RECORDING
        nonlocal recording_thread

        # Always stop TTS first when hotkey is pressed
        stop_active_tts()

        if RECORDING:
            RECORDING = False
            return

        def do_record():
            audio = record_audio()
            if audio is None or len(audio) < SAMPLE_RATE * 0.5:
                sys.stderr.write("[voice-mode] Recording too short, skipped\n")
                return

            text = transcribe(audio, whisper_bin, model_path)
            if text:
                sys.stderr.write(f"\n  Transcribed: {text}\n")
                type_text(text)

        recording_thread = threading.Thread(target=do_record, daemon=True)
        recording_thread.start()

    hotkey = keyboard.HotKey(
        keyboard.HotKey.parse(hotkey_str),
        toggle_recording,
    )

    def on_press(key):
        hotkey.press(key)

    def on_release(key):
        hotkey.release(key)

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        try:
            listener.join()
        except KeyboardInterrupt:
            print("\n[voice-mode] Shutting down.")


if __name__ == "__main__":
    main()
