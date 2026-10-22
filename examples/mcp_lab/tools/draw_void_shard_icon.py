"""Procedurally draws the 88x64 item icon for item_mcp_void_shard (no external dependencies).

Usage: python draw_void_shard_icon.py <output.png>
"""
import math
import struct
import sys
import zlib

W, H = 88, 64
CX, CY = W / 2, H / 2


def shade(x: float, y: float) -> tuple[int, int, int]:
    dx, dy = (x - CX) / (W / 2), (y - CY) / (H / 2)
    r = math.hypot(dx, dy)
    # Dark void background with a violet radial glow
    glow = max(0.0, 1.0 - r) ** 2
    bg = (int(18 + 90 * glow), int(6 + 20 * glow), int(32 + 150 * glow))

    # Diamond-shaped crystal: |dx|/a + |dy|/b <= 1
    d = abs(x - CX) / 18 + abs(y - CY) / 26
    if d <= 1.0:
        facet = 0.55 + 0.45 * (1 if (x - CX) * (y - CY) < 0 else 0.6)  # two lit facets
        core = (1.0 - d) ** 0.5
        return (int(min(255, 120 + 120 * core * facet)), int(min(255, 40 + 140 * core * facet)), int(min(255, 200 + 55 * core)))
    if d <= 1.15:  # bright rim
        return (230, 200, 255)

    # Swirling rift rings around the crystal
    ang = math.atan2(y - CY, x - CX)
    ring = math.sin(r * 18 - ang * 3)
    if ring > 0.85 and r < 0.95:
        return (min(255, bg[0] + 80), min(255, bg[1] + 30), min(255, bg[2] + 90))
    return bg


def write_png(path: str) -> None:
    rows = []
    for y in range(H):
        row = bytearray(b"\x00")
        for x in range(W):
            row += bytes(shade(x + 0.5, y + 0.5))
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)


if __name__ == "__main__":
    write_png(sys.argv[1])
