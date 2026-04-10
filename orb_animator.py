#!/usr/bin/env python3
"""
Orb Animator: renders a pulsing circle in the terminal that reacts to audio amplitude.
Inspired by ChatGPT's voice mode orb.
"""

import math
import sys
import threading
import time


BRAILLE_BASE = 0x2800

BRAILLE_DOT_MAP = [
    (0, 0, 0x01), (1, 0, 0x08),
    (0, 1, 0x02), (1, 1, 0x10),
    (0, 2, 0x04), (1, 2, 0x20),
    (0, 3, 0x40), (1, 3, 0x80),
]


class OrbAnimator:
    """Renders a pulsing orb in the terminal using braille characters."""

    def __init__(
        self,
        radius: int = 8,
        fps: int = 15,
        color: str = "cyan",
        output=None,
    ):
        self.base_radius = radius
        self.fps = fps
        self.running = False
        self._thread = None
        self._amplitude = 0.0
        self._lock = threading.Lock()
        self._out = output or sys.stdout

        self._colors = {
            "cyan":    ("\033[96m", "\033[36m", "\033[34m"),
            "green":   ("\033[92m", "\033[32m", "\033[34m"),
            "magenta": ("\033[95m", "\033[35m", "\033[34m"),
            "blue":    ("\033[94m", "\033[34m", "\033[90m"),
            "white":   ("\033[97m", "\033[37m", "\033[90m"),
            "warm":    ("\033[97m", "\033[93m", "\033[90m"),
        }
        self._color_set = self._colors.get(color, self._colors["cyan"])
        self._reset = "\033[0m"

        self._canvas_w = (radius * 2 + 6) * 2
        self._canvas_h = (radius * 2 + 6) * 4

    def set_amplitude(self, amp: float):
        with self._lock:
            self._amplitude = min(1.0, max(0.0, amp))

    def start(self):
        self.running = True
        self._out.write("\033[?25l")
        self._out.flush()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        rows = self._canvas_h // 4 + 2
        self._out.write(f"\033[{rows}A")
        for _ in range(rows):
            self._out.write("\033[2K\n")
        self._out.write(f"\033[{rows}A")
        self._out.write("\033[?25h")
        self._out.flush()

    def _render_orb(self, t: float, amplitude: float) -> list[str]:
        """Render the orb as lines of braille characters."""
        pulse = 1.0 + amplitude * 0.35 * math.sin(t * 4)
        radius = self.base_radius * pulse

        char_w = self._canvas_w // 2
        char_h = self._canvas_h // 4

        grid = [[0] * char_w for _ in range(char_h)]

        cx = self._canvas_w / 2
        cy = self._canvas_h / 2

        for char_y in range(char_h):
            for char_x in range(char_w):
                code = 0
                for dx, dy, bit in BRAILLE_DOT_MAP:
                    px = char_x * 2 + dx
                    py = char_y * 4 + dy

                    dist_x = (px - cx) / 1.8
                    dist_y = py - cy
                    dist = math.sqrt(dist_x**2 + dist_y**2)

                    wobble = amplitude * 0.15 * math.sin(
                        math.atan2(dist_y, dist_x) * 6 + t * 3
                    )

                    if dist <= radius + wobble:
                        code |= bit

                grid[char_y][char_x] = code

        bright, mid, dim = self._color_set
        lines = []

        for char_y in range(char_h):
            line_parts = []
            for char_x in range(char_w):
                code = grid[char_y][char_x]
                if code == 0:
                    line_parts.append(" ")
                    continue

                px = char_x * 2 + 1
                py = char_y * 4 + 2
                dist_x = (px - cx) / 2.0
                dist_y = py - cy
                dist = math.sqrt(dist_x**2 + dist_y**2)
                ratio = dist / max(radius, 0.1)

                if ratio < 0.4:
                    color = bright
                elif ratio < 0.75:
                    color = mid
                else:
                    color = dim

                line_parts.append(f"{color}{chr(BRAILLE_BASE + code)}{self._reset}")

            lines.append("".join(line_parts))

        return lines

    def _animate(self):
        t = 0.0
        first_frame = True

        while self.running:
            with self._lock:
                amp = self._amplitude

            lines = self._render_orb(t, amp)

            if not first_frame:
                self._out.write(f"\033[{len(lines)}A")
            first_frame = False

            for line in lines:
                self._out.write(f"\033[2K  {line}\n")
            self._out.flush()

            t += 0.12
            time.sleep(1.0 / self.fps)


def demo():
    """Run a standalone demo of the orb."""
    import numpy as np

    print("Orb animation demo (5 seconds)...\n")
    orb = OrbAnimator(radius=8, fps=15, color="cyan")
    orb.start()

    for i in range(75):
        amp = (math.sin(i * 0.15) + 1) / 2 * 0.8 + 0.1
        orb.set_amplitude(amp)
        time.sleep(1.0 / 15)

    orb.stop()
    print("Demo complete.")


if __name__ == "__main__":
    demo()
