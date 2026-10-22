"""Make the lab crystals solid: prop_dynamic does not block Dota pathing, so place point_simple_obstruction
entities (dota.fgd) around each crystal — the center plus four neighbours one GridNav cell (64 units) away."""
import math
import sys

sys.path.insert(0, r"D:\Antigravity\dota-mcp")
from src.dota2_mcp import vmap_builder as vb

A, M = "mcp_lab", "lab"
ok = 0
for i, ang in enumerate((45, 135, 225, 315)):
    cx, cy = 700 * math.cos(math.radians(ang)), 700 * math.sin(math.radians(ang))
    for j, (dx, dy) in enumerate(((0, 0), (64, 0), (-64, 0), (0, 64), (0, -64))):
        r = vb.add_map_entity(A, M, classname="point_simple_obstruction",
                              origin=f"{cx + dx:.0f} {cy + dy:.0f} 128", targetname=f"lab_crystal_block_{i}_{j}")
        ok += bool(r.get("ok"))
print("obstructions added:", ok)
