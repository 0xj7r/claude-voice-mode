#!/usr/bin/env python3
"""
TTS Player: reads Claude's last response from transcript and speaks it aloud
with a pulsing orb animation during playback.
"""

import json
import signal
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
        data = json.load(f)

    last_text = None

    for msg in reversed(data):
        if msg.get("role") != "assistant":
            continue

        content = msg.get("content", "")

        if isinstance(content, str):
            last_text = content
            break

        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block["text"])
            if texts:
                last_text = "\n".join(texts)
                break

    return last_text


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


def play_with_animation(text: str, config: dict):
    """Stream TTS through Kokoro with orb animation."""
    import sounddevice as sd

    try:
        from kokoro_onnx import Kokoro
    except ImportError:
        sys.stderr.write("\n[voice-mode] kokoro-onnx not installed. Run: pip install kokoro-onnx\n")
        return

    model_dir = os.path.join(VOICE_MODE_DIR, "models")
    model_path = os.path.join(model_dir, "kokoro-v1.0.onnx")
    voices_path = os.path.join(model_dir, "voices-v1.0.bin")

    if not os.path.exists(model_path) or not os.path.exists(voices_path):
        sys.stderr.write(
            "\n[voice-mode] Models not found. Run: python setup.py\n"
        )
        return

    tts_config = config.get("tts", {})
    anim_config = config.get("animation", {})
    voice = tts_config.get("voice", "af_heart")
    speed = tts_config.get("speed", 1.1)

    kokoro = Kokoro(model_path, voices_path)
    animator = OrbAnimator(
        radius=anim_config.get("radius", 8),
        fps=anim_config.get("fps", 15),
        color=anim_config.get("color", "cyan"),
    )

    sentences = split_sentences(text)
    if not sentences:
        return

    animator.start()

    try:
        for sentence in sentences:
            if INTERRUPTED.is_set():
                break

            samples, sr = kokoro.create(sentence, voice=voice, speed=speed)
            samples = samples.astype(np.float32)

            block_size = 1024
            pos = [0]
            finished = threading.Event()
            rms_val = [0.0]
            rms_lock = threading.Lock()

            def callback(outdata, frames, time_info, status):
                if INTERRUPTED.is_set():
                    outdata[:] = 0
                    finished.set()
                    return

                start = pos[0]
                end = start + frames
                if end >= len(samples):
                    chunk = samples[start:]
                    outdata[:len(chunk), 0] = chunk
                    outdata[len(chunk):] = 0
                    finished.set()
                else:
                    outdata[:, 0] = samples[start:end]

                chunk = outdata[:, 0]
                with rms_lock:
                    rms_val[0] = float(np.sqrt(np.mean(chunk**2)))

                pos[0] = end

            with sd.OutputStream(
                samplerate=sr,
                channels=1,
                blocksize=block_size,
                callback=callback,
            ):
                while not finished.is_set() and not INTERRUPTED.is_set():
                    with rms_lock:
                        rms = rms_val[0]
                    animator.set_amplitude(min(1.0, rms * 5))
                    time.sleep(1.0 / animator.fps)

            animator.set_amplitude(0.0)
    finally:
        animator.stop()
        _clear_pid()


def main():
    signal.signal(signal.SIGUSR1, _on_interrupt)
    signal.signal(signal.SIGINT, _on_interrupt)
    _write_pid()

    try:
        hook_input = json.loads(sys.stdin.read())
        transcript_path = hook_input.get("transcript_path")

        if not transcript_path:
            sys.stderr.write("[voice-mode] No transcript_path in hook input\n")
            sys.exit(1)

        config = load_config()
        if not config.get("tts", {}).get("enabled", True):
            sys.exit(0)

        text = extract_last_assistant_message(transcript_path)
        if not text:
            sys.exit(0)

        cleaned = clean_for_speech(text)
        if not cleaned:
            sys.exit(0)

        play_with_animation(cleaned, config)
    finally:
        _clear_pid()


if __name__ == "__main__":
    main()
