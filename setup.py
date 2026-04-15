#!/usr/bin/env python3
"""
Setup script: downloads Kokoro TTS and Whisper models.
"""

import os
import subprocess
import sys
import urllib.request

VOICE_MODE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(VOICE_MODE_DIR, "models")

KOKORO_MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
KOKORO_VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
WHISPER_MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"


def download_file(url: str, dest: str, label: str):
    if os.path.exists(dest):
        size_mb = os.path.getsize(dest) / (1024 * 1024)
        print(f"  [skip] {label} already exists ({size_mb:.1f} MB)")
        return

    print(f"  Downloading {label}...")
    print(f"    {url}")

    def progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(100, downloaded * 100 / total_size)
            mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            sys.stdout.write(f"\r    {mb:.1f}/{total_mb:.1f} MB ({pct:.0f}%)")
            sys.stdout.flush()

    urllib.request.urlretrieve(url, dest, reporthook=progress)
    size_mb = os.path.getsize(dest) / (1024 * 1024)
    print(f"\n    Done ({size_mb:.1f} MB)")


def install_pip_deps():
    print("\n1. Installing Python dependencies...")
    req_path = os.path.join(VOICE_MODE_DIR, "requirements.txt")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", req_path, "-q"],
        check=True,
    )
    print("  Done.")


def download_models():
    print("\n2. Downloading models...")
    os.makedirs(MODEL_DIR, exist_ok=True)

    download_file(
        KOKORO_MODEL_URL,
        os.path.join(MODEL_DIR, "kokoro-v1.0.onnx"),
        "Kokoro TTS model (~370 MB)",
    )
    download_file(
        KOKORO_VOICES_URL,
        os.path.join(MODEL_DIR, "voices-v1.0.bin"),
        "Kokoro voices (~42 MB)",
    )
    download_file(
        WHISPER_MODEL_URL,
        os.path.join(MODEL_DIR, "ggml-base.en.bin"),
        "Whisper base.en model (~142 MB)",
    )


def check_whisper_cpp():
    print("\n3. Checking whisper-cpp...")
    result = subprocess.run(["which", "whisper-cpp"], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Found: {result.stdout.strip()}")
    else:
        print("  Not found. Install with: brew install whisper-cpp")
        print("  (STT will not work without it, but TTS will still function)")


def setup_hook():
    print("\n4. Hook configuration...")
    hook_script = os.path.join(VOICE_MODE_DIR, "scripts", "hook_tts.sh")
    print(f"  Hook script: {hook_script}")
    print("  Add to ~/.claude/settings.json under hooks.Stop")
    print("  (run with --install-hook to auto-configure)")


def main():
    print("=" * 50)
    print("  Claude Code Voice Mode Setup")
    print("=" * 50)

    install_pip_deps()
    download_models()
    check_whisper_cpp()
    setup_hook()

    if "--install-hook" in sys.argv:
        install_hook_config()

    print("\n" + "=" * 50)
    print("  Setup complete!")
    print("=" * 50)
    print("\nUsage:")
    print("  TTS (auto):     responses are spoken via Stop hook")
    print("  STT (manual):   python src/voice_daemon.py")
    print(f"  Config:         {os.path.join(VOICE_MODE_DIR, 'config.json')}")


def install_hook_config():
    settings_path = os.path.expanduser("~/.claude/settings.json")

    if os.path.exists(settings_path):
        with open(settings_path) as f:
            settings = json.load(f)
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})
    stop_hooks = hooks.setdefault("Stop", [])

    hook_script = os.path.join(VOICE_MODE_DIR, "scripts", "hook_tts.sh")
    hook_entry = {
        "matcher": "",
        "hooks": [
            {
                "type": "command",
                "command": hook_script,
            }
        ],
    }

    already = any(
        hook_script in str(h.get("hooks", []))
        for h in stop_hooks
    )

    if not already:
        stop_hooks.append(hook_entry)
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)
        print("  Hook installed in settings.json")
    else:
        print("  Hook already configured")


import json

if __name__ == "__main__":
    main()
