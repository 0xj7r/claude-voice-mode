#!/usr/bin/env python3
"""Quick test: synthesize a short phrase and play it with orb animation."""

import os
import sys
import math
import time

VOICE_MODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, VOICE_MODE_DIR)

from tts_player import play_with_animation, load_config
from orb_animator import OrbAnimator


def test_orb_only():
    """Test just the orb animation for 5 seconds."""
    print("Orb animation demo (5 seconds)...\n")
    orb = OrbAnimator(radius=8, fps=15, color="cyan")
    orb.start()

    for i in range(75):
        amp = (math.sin(i * 0.15) + 1) / 2 * 0.8 + 0.1
        orb.set_amplitude(amp)
        time.sleep(1.0 / 15)

    orb.stop()
    print("Orb test complete.\n")


def test_tts():
    """Test Kokoro TTS with orb."""
    config = load_config()
    text = "Hello! I am Claude, your AI assistant. Voice mode is now active."
    print(f"Testing TTS: \"{text}\"\n")
    play_with_animation(text, config)
    print("\nTTS test complete.")


if __name__ == "__main__":
    if "--orb-only" in sys.argv:
        test_orb_only()
    else:
        test_orb_only()
        test_tts()
