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
    """Synthesize and play text. Optionally drive an orb animator."""
    import sounddevice as sd
    from kokoro_onnx import Kokoro
    from queue import Queue

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

    # Pre-synthesize in background thread
    audio_queue: Queue[np.ndarray | None] = Queue(maxsize=3)
    target_sr = [0]

    def synth_worker():
        for sentence in sentences:
            if INTERRUPTED.is_set():
                break
            samples, sr = kokoro.create(sentence, voice=voice, speed=speed)
            target_sr[0] = sr
            audio_queue.put(samples.astype(np.float32))
        audio_queue.put(None)

    synth_thread = threading.Thread(target=synth_worker, daemon=True)
    synth_thread.start()

    # Wait for first chunk to get sample rate
    first = audio_queue.get()
    if first is None:
        return

    sr = target_sr[0]

    if animator:
        animator.start()

    try:
        samples = first
        while samples is not None and not INTERRUPTED.is_set():
            block_size = 1024
            pos = 0
            total = len(samples)
            finished = threading.Event()
            current_rms = [0.0]

            # Use a class to avoid closure issues
            class PlayState:
                p = 0
                s = samples
                f = finished

            state = PlayState()

            def callback(outdata, frames, time_info, status):
                if INTERRUPTED.is_set():
                    outdata[:] = 0
                    state.f.set()
                    return

                start = state.p
                end = start + frames
                if end >= len(state.s):
                    chunk = state.s[start:]
                    outdata[:len(chunk), 0] = chunk
                    outdata[len(chunk):] = 0
                    state.f.set()
                else:
                    outdata[:, 0] = state.s[start:end]

                current_rms[0] = float(np.sqrt(np.mean(outdata[:, 0] ** 2)))
                state.p = end

            with sd.OutputStream(
                samplerate=sr, channels=1, blocksize=block_size, callback=callback
            ):
                while not state.f.is_set() and not INTERRUPTED.is_set():
                    if animator:
                        animator.set_amplitude(min(1.0, current_rms[0] * 5))
                    time.sleep(1.0 / 30)

            samples = audio_queue.get()
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


def run_daemon():
    """Run as a foreground daemon: listens on a socket, shows orb in terminal."""
    signal.signal(signal.SIGUSR1, _on_interrupt)
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    _write_pid()

    config = load_config()
    anim_config = config.get("animation", {})

    # Clean up stale socket
    try:
        os.unlink(SOCK_PATH)
    except FileNotFoundError:
        pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCK_PATH)
    server.listen(1)
    server.settimeout(1.0)

    print("[voice-mode] TTS daemon running. Waiting for text...")
    print(f"[voice-mode] Socket: {SOCK_PATH}")
    print("[voice-mode] Press Ctrl+C to quit.\n")

    try:
        while True:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue

            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            conn.close()

            text = data.decode("utf-8").strip()
            if not text:
                continue

            cleaned = clean_for_speech(text)
            if not cleaned:
                continue

            config = load_config()
            if not config.get("tts", {}).get("enabled", True):
                continue

            animator = OrbAnimator(
                radius=anim_config.get("radius", 8),
                fps=anim_config.get("fps", 15),
                color=anim_config.get("color", "cyan"),
            )

            INTERRUPTED.clear()
            play_audio(cleaned, config, animator=animator)
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        _clear_pid()
        try:
            os.unlink(SOCK_PATH)
        except FileNotFoundError:
            pass
        print("\n[voice-mode] Daemon stopped.")


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
