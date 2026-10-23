"""Synthesize the two custom test sounds of mcp_lab (stage 7) as 16-bit mono .wav files.

Usage: python make_lab_sounds.py <content/dota_addons/mcp_lab>
Writes sounds/mcp_lab/rift_chime.wav (rising 8-bit arpeggio) and sounds/mcp_lab/rift_zap.wav (laser sweep).
Pure standard library, deterministic output.
"""

import math
import struct
import sys
import wave
from pathlib import Path

RATE = 44100


def write_wav(path: Path, samples: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 30000)) for s in samples))


def chime() -> list[float]:
    """C-E-G-C' arpeggio, square + sine mix with tremolo: clearly synthetic, ~1.1 s."""
    out: list[float] = []
    notes = [523.25, 659.25, 783.99, 1046.5]
    for i, freq in enumerate(notes):
        length = 0.16 if i < 3 else 0.6
        n = int(RATE * length)
        for k in range(n):
            t = k / RATE
            env = min(1.0, k / 200) * math.exp(-t * (6 if i < 3 else 3.5))
            square = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
            sine = math.sin(2 * math.pi * freq * 2 * t)
            trem = 0.75 + 0.25 * math.sin(2 * math.pi * 9 * t)
            out.append(0.55 * env * trem * (0.45 * square + 0.55 * sine))
    return out


def zap() -> list[float]:
    """Downward frequency sweep 1800 -> 120 Hz with a little noise-free buzz, ~0.45 s."""
    out: list[float] = []
    n = int(RATE * 0.45)
    phase = 0.0
    for k in range(n):
        t = k / RATE
        freq = 120 + 1680 * math.exp(-t * 9)
        phase += 2 * math.pi * freq / RATE
        env = min(1.0, k / 100) * math.exp(-t * 5)
        out.append(0.6 * env * (math.sin(phase) + 0.3 * math.sin(3 * phase)))
    return out


if __name__ == "__main__":
    base = Path(sys.argv[1]) / "sounds" / "mcp_lab"
    write_wav(base / "rift_chime.wav", chime())
    write_wav(base / "rift_zap.wav", zap())
    print("written:", base)
