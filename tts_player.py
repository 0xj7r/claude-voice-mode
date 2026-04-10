#!/usr/bin/env python3
"""
TTS Player: speaks text aloud via Kokoro with orb animation.

Two modes:
  1. Direct: pipe JSON on stdin (used by hook_tts.sh)
  2. Daemon: listens on a Unix socket for text to speak (shows orb in terminal)
"""

import json
import signal
import socket
import sys
import os
import re
import threading
import time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from orb_animator import OrbAnimator

VOICE_MODE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(VOICE_MODE_DIR, "config.json")
PID_PATH = os.path.join(VOICE_MODE_DIR, ".tts.pid")
SOCK_PATH = os.path.join(VOICE_MODE_DIR, ".tts.sock")

INTERRUPTED = threading.Event()


def _write_pid():
    with open(PID_PATH, "w") as f:
        f.write(str(os.getpid()))


def _clear_pid():
    try:
        os.unlink(PID_PATH)
    except FileNotFoundError:
        pass


def _on_interrupt(signum, frame):
    INTERRUPTED.set()


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def extract_last_assistant_message(transcript_path: str) -> str | None:
    """Extract the last assistant text message from Claude Code's transcript."""
    if not os.path.exists(transcript_path):
        return None

    with open(transcript_path) as f:
        content = f.read().strip()

    try:
        data = json.loads(content)
        if not isinstance(data, list):
            data = [data]
    except json.JSONDecodeError:
        data = []
        for line in content.splitlines():
            line = line.strip()
            if line:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    for entry in reversed(data):
        msg = entry.get("message", entry)
        role = msg.get("role", entry.get("type"))
        if role != "assistant":
            continue

        msg_content = msg.get("content", "")

        if isinstance(msg_content, str) and msg_content.strip():
            return msg_content

        if isinstance(msg_content, list):
            texts = []
            for block in msg_content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block["text"])
            if texts:
                return "\n".join(texts)

    return None


def clean_for_speech(text: str) -> str:
    """Strip markdown, code blocks, and other non-speech content."""
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#*_~>|]", "", text)
    text = re.sub(r"^\s*[-+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    """Split text into sentence-sized chunks for streaming TTS."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def play_audio(text: str, config: dict, animator: OrbAnimator | None = None):
    """Synthesize all sentences into one buffer, play with a single stream."""
    import sounddevice as sd
    from kokoro_onnx import Kokoro

    model_dir = os.path.join(VOICE_MODE_DIR, "models")
    model_path = os.path.join(model_dir, "kokoro-v1.0.onnx")
    voices_path = os.path.join(model_dir, "voices-v1.0.bin")

    if not os.path.exists(model_path) or not os.path.exists(voices_path):
        sys.stderr.write("[voice-mode] Models not found. Run: bash install.sh\n")
        return

    tts_config = config.get("tts", {})
    voice = tts_config.get("voice", "af_heart")
    speed = tts_config.get("speed", 1.1)

    kokoro = Kokoro(model_path, voices_path)

    sentences = split_sentences(text)
    if not sentences:
        return

    # Synthesize everything upfront into one contiguous buffer
    chunks = []
    sr = 0
    for sentence in sentences:
        if INTERRUPTED.is_set():
            return
        samples, sr = kokoro.create(sentence, voice=voice, speed=speed)
        chunks.append(samples.astype(np.float32))

    if not chunks or sr == 0:
        return

    audio = np.concatenate(chunks)
    pos = [0]
    finished = threading.Event()
    current_rms = [0.0]

    def callback(outdata, frames, time_info, status):
        if INTERRUPTED.is_set():
            outdata[:] = 0
            finished.set()
            return

        start = pos[0]
        end = start + frames
        if end >= len(audio):
            remaining = len(audio) - start
            if remaining > 0:
                outdata[:remaining, 0] = audio[start:]
            outdata[remaining:] = 0
            finished.set()
        else:
            outdata[:, 0] = audio[start:end]

        current_rms[0] = float(np.sqrt(np.mean(outdata[:, 0] ** 2)))
        pos[0] = end

    if animator:
        animator.start()

    try:
        with sd.OutputStream(
            samplerate=sr, channels=1, blocksize=2048, callback=callback
        ):
            while not finished.is_set() and not INTERRUPTED.is_set():
                if animator:
                    animator.set_amplitude(min(1.0, current_rms[0] * 5))
                time.sleep(1.0 / 30)
    finally:
        INTERRUPTED.clear()
        if animator:
            animator.set_amplitude(0.0)
            animator.stop()


def send_to_daemon(text: str) -> bool:
    """Send text to a running TTS daemon via Unix socket. Returns True if sent."""
    if not os.path.exists(SOCK_PATH):
        return False
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(SOCK_PATH)
        sock.sendall(text.encode("utf-8"))
        sock.close()
        return True
    except (ConnectionRefusedError, FileNotFoundError, OSError):
        return False


def _find_whisper_cpp() -> str | None:
    """Find whisper-cpp binary."""
    import subprocess as sp
    for name in ["whisper-cli", "whisper-cpp", "whisper"]:
        result = sp.run(["which", name], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    for name in ["whisper-cli", "whisper-cpp"]:
        brew_path = f"/opt/homebrew/bin/{name}"
        if os.path.exists(brew_path):
            return brew_path
    return None


def _find_whisper_model(model_name: str = "base.en") -> str | None:
    """Find the whisper model file."""
    model_dir = os.path.join(VOICE_MODE_DIR, "models")
    local = os.path.join(model_dir, f"ggml-{model_name}.bin")
    if os.path.exists(local):
        return local
    brew = f"/opt/homebrew/share/whisper-cpp/models/ggml-{model_name}.bin"
    if os.path.exists(brew):
        return brew
    return None


def _transcribe(audio: np.ndarray, whisper_bin: str, model_path: str) -> str:
    """Record numpy audio to wav, transcribe with whisper.cpp."""
    import subprocess as sp
    import tempfile
    import wave

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name

    try:
        audio_int16 = (audio * 32767).astype(np.int16)
        with wave.open(wav_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(audio_int16.tobytes())

        result = sp.run(
            [whisper_bin, "-m", model_path, "-f", wav_path, "--no-timestamps", "-nt"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return ""
    finally:
        os.unlink(wav_path)


def _type_text(text: str):
    """Type text into the focused application using osascript."""
    import subprocess as sp
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    sp.run(["osascript", "-e", f'tell application "System Events" to keystroke "{escaped}"'],
           capture_output=True)


def run_daemon():
    """Unified daemon: TTS (socket listener + orb) and STT (hotkey + whisper)."""
    import sounddevice as sd

    signal.signal(signal.SIGUSR1, _on_interrupt)
    _write_pid()

    config = load_config()
    anim_config = config.get("animation", {})
    stt_config = config.get("stt", {})

    # STT setup
    whisper_bin = _find_whisper_cpp()
    whisper_model = _find_whisper_model(stt_config.get("model", "base.en"))
    stt_available = whisper_bin and whisper_model
    hotkey_str = stt_config.get("hotkey", "<ctrl>+<shift>+v")

    # TTS socket setup
    try:
        os.unlink(SOCK_PATH)
    except FileNotFoundError:
        pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCK_PATH)
    server.listen(1)
    server.settimeout(0.5)

    out = sys.stdout
    out.write("[voice-mode] Daemon running\n")
    out.write(f"  TTS: listening on socket\n")
    if stt_available:
        out.write(f"  STT: press {hotkey_str} to talk\n")
    else:
        out.write(f"  STT: unavailable (whisper-cpp not found)\n")
    out.write(f"  Press Ctrl+C to quit.\n\n")
    out.flush()

    # Recording state
    recording = [False]
    audio_chunks: list[np.ndarray] = []
    tts_playing = [False]

    def handle_tts(text: str):
        """Play TTS with orb animation."""
        cleaned = clean_for_speech(text)
        if not cleaned:
            return

        cfg = load_config()
        if not cfg.get("tts", {}).get("enabled", True):
            return

        animator = OrbAnimator(
            radius=anim_config.get("radius", 8),
            fps=anim_config.get("fps", 15),
            color=anim_config.get("color", "white"),
        )

        tts_playing[0] = True
        INTERRUPTED.clear()
        try:
            play_audio(cleaned, cfg, animator=animator)
        finally:
            tts_playing[0] = False

    def socket_listener():
        """Background thread: accept TTS text from Claude Code hook."""
        while True:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            conn.close()

            text = data.decode("utf-8").strip()
            if text:
                handle_tts(text)

    sock_thread = threading.Thread(target=socket_listener, daemon=True)
    sock_thread.start()

    def toggle_recording():
        """Hotkey handler: stop TTS if playing, then toggle recording."""
        if tts_playing[0]:
            INTERRUPTED.set()
            time.sleep(0.1)

        if recording[0]:
            recording[0] = False
            return

        def do_record():
            audio_chunks.clear()
            recording[0] = True

            def mic_callback(indata, frames, time_info, status):
                if recording[0]:
                    audio_chunks.append(indata.copy())

            with sd.InputStream(samplerate=16000, channels=1, dtype="float32",
                                callback=mic_callback):
                indicator = ["⬤ ", "  "]
                i = 0
                while recording[0]:
                    out.write(f"\r  \033[91m{indicator[i % 2]}\033[0mRecording... (press hotkey to stop)")
                    out.flush()
                    i += 1
                    time.sleep(0.4)

            out.write("\r" + " " * 60 + "\r")
            out.flush()

            if not audio_chunks or len(audio_chunks) < 2:
                out.write("  Recording too short\n")
                out.flush()
                return

            audio = np.concatenate(audio_chunks, axis=0)
            out.write("  Transcribing...\r")
            out.flush()

            text = _transcribe(audio, whisper_bin, whisper_model)

            out.write("\r" + " " * 40 + "\r")
            if text:
                out.write(f"  You: {text}\n")
                out.flush()
                _type_text(text)
            else:
                out.write("  (no speech detected)\n")
                out.flush()

        threading.Thread(target=do_record, daemon=True).start()

    # Keyboard listener (main thread)
    if stt_available and stt_config.get("enabled", True):
        from pynput import keyboard

        hotkey = keyboard.HotKey(keyboard.HotKey.parse(hotkey_str), toggle_recording)

        with keyboard.Listener(
            on_press=lambda k: hotkey.press(k),
            on_release=lambda k: hotkey.release(k),
        ) as listener:
            try:
                listener.join()
            except KeyboardInterrupt:
                pass
    else:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    server.close()
    _clear_pid()
    try:
        os.unlink(SOCK_PATH)
    except FileNotFoundError:
        pass
    out.write("\n[voice-mode] Stopped.\n")
    out.flush()


def main():
    """Hook entry point: receives JSON on stdin, sends text to daemon or plays directly."""
    hook_input = json.loads(sys.stdin.read())

    config = load_config()
    if not config.get("tts", {}).get("enabled", True):
        sys.exit(0)

    text = hook_input.get("last_assistant_message")

    if not text:
        transcript_path = hook_input.get("transcript_path")
        if transcript_path:
            text = extract_last_assistant_message(transcript_path)

    if not text:
        sys.exit(0)

    cleaned = clean_for_speech(text)
    if not cleaned:
        sys.exit(0)

    # Try to send to daemon (gets orb animation in the daemon terminal)
    if send_to_daemon(cleaned):
        sys.exit(0)

    # No daemon running: play directly (no orb, just audio)
    signal.signal(signal.SIGUSR1, _on_interrupt)
    signal.signal(signal.SIGINT, _on_interrupt)
    _write_pid()
    try:
        play_audio(cleaned, config, animator=None)
    finally:
        _clear_pid()


if __name__ == "__main__":
    if "--daemon" in sys.argv:
        run_daemon()
    else:
        main()
