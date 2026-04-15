#!/usr/bin/env python3
"""
Orb Animator: renders a pulsing circle centered in the terminal.
Uses braille characters for sub-character resolution.
"""

import math
import os
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
    """Renders a pulsing orb centered in the terminal using braille characters."""

    def __init__(self, radius: int = 8, fps: int = 15, color: str = "white", output=None):
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
        }
        self._color_set = self._colors.get(color, self._colors["white"])
        self._reset = "\033[0m"

        # Canvas size in braille dots
        # Each braille char = 2 dots wide, 4 dots tall
        # Terminal chars are ~2x taller than wide
        # So 1 braille char covers 2 horizontal dots and 4 vertical dots
        # but visually the char is ~1:2 (w:h), making each dot roughly square
        dot_span = radius * 2 + 4
        self._dot_w = dot_span * 2  # horizontal dots
        self._dot_h = dot_span * 2  # vertical dots
        self._char_w = self._dot_w // 2  # braille chars wide
        self._char_h = self._dot_h // 4  # braille chars tall

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
        rows = self._char_h + 1
        self._out.write(f"\033[{rows}A")
        for _ in range(rows):
            self._out.write("\033[2K\n")
        self._out.write(f"\033[{rows}A")
        self._out.write("\033[?25h")
        self._out.flush()

    def _render_orb(self, t: float, amplitude: float) -> list[str]:
        pulse = 1.0 + amplitude * 0.2 * math.sin(t * 4)
        radius = self.base_radius * pulse

        char_w = self._char_w
        char_h = self._char_h
        grid = [[0] * char_w for _ in range(char_h)]

        # Center of canvas in dot coordinates
        cx = self._dot_w / 2.0
        cy = self._dot_h / 2.0

        for cy_idx in range(char_h):
            for cx_idx in range(char_w):
                code = 0
                for dx, dy, bit in BRAILLE_DOT_MAP:
                    # Position of this dot in dot-space
                    dot_x = cx_idx * 2 + dx
                    dot_y = cy_idx * 4 + dy

                    # Distance from center
                    # Terminal chars are ~2:1 height:width
                    # Braille: 2 dots wide per char, 4 dots tall per char
                    # Visual aspect: each dot_x step = 0.5 char width
                    #                each dot_y step = 0.25 char height
                    # Since char height ~ 2 * char width:
                    #   dot_x visual size = 0.5 * char_width
                    #   dot_y visual size = 0.25 * 2 * char_width = 0.5 * char_width
                    # So dots are roughly square. Just use raw distance.
                    ndx = dot_x - cx
                    ndy = dot_y - cy
                    dist = math.sqrt(ndx * ndx + ndy * ndy)

                    if dist <= radius:
                        code |= bit

                grid[cy_idx][cx_idx] = code

        bright, mid, dim = self._color_set
        lines = []

        for cy_idx in range(char_h):
            parts = []
            for cx_idx in range(char_w):
                code = grid[cy_idx][cx_idx]
                if code == 0:
                    parts.append(" ")
                    continue

                # Color based on distance from center
                dot_x = cx_idx * 2 + 1
                dot_y = cy_idx * 4 + 2
                dist = math.sqrt((dot_x - cx) ** 2 + (dot_y - cy) ** 2)
                ratio = dist / max(radius, 0.1)

                if ratio < 0.45:
                    color = bright
                elif ratio < 0.8:
                    color = mid
                else:
                    color = dim

                parts.append(f"{color}{chr(BRAILLE_BASE + code)}{self._reset}")

            lines.append("".join(parts))

        return lines

    def _get_terminal_width(self) -> int:
        try:
            return os.get_terminal_size().columns
        except OSError:
            return 80

    def _animate(self):
        t = 0.0
        first_frame = True

        while self.running:
            with self._lock:
                amp = self._amplitude

            lines = self._render_orb(t, amp)
            term_w = self._get_terminal_width()

            if not first_frame:
                self._out.write(f"\033[{len(lines)}A")
            first_frame = False

            for line in lines:
                # Strip ANSI to measure visible width
                visible = ""
                i = 0
                raw = line
                while i < len(raw):
                    if raw[i] == "\033":
                        while i < len(raw) and raw[i] != "m":
                            i += 1
                        i += 1
                    else:
                        visible += raw[i]
                        i += 1

                pad = max(0, (term_w - len(visible)) // 2)
                self._out.write(f"\033[2K{' ' * pad}{line}\n")

            self._out.flush()
            t += 0.12
            time.sleep(1.0 / self.fps)


def demo():
    """Run a standalone demo of the orb."""
    print("Orb animation demo (5 seconds)...\n")
    orb = OrbAnimator(radius=8, fps=15, color="white")
    orb.start()

    for i in range(75):
        amp = (math.sin(i * 0.15) + 1) / 2 * 0.8 + 0.1
        orb.set_amplitude(amp)
        time.sleep(1.0 / 15)

    orb.stop()
    print("Demo complete.")


if __name__ == "__main__":
    demo()
