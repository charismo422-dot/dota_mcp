"""Stage 6: dress the lab map — snowy tree ring with two gates, shopkeeper, purple rift crystals."""
import math, sys
sys.path.insert(0, r"D:\Antigravity\dota-mcp")
from src.dota2_mcp import vmap_builder as vb

A, M = "mcp_lab", "lab"
added, failed = 0, []

def add(**kw):
    global added
    r = vb.add_map_entity(A, M, **kw)
    if r.get("ok"):
        added += 1
    else:
        failed.append((kw.get("targetname"), r.get("error")))

# Ring of trees, radius 1150, with gates toward the wave spawners (angles ~23 and ~157 deg)
gates = [math.degrees(math.atan2(600, 1400)), math.degrees(math.atan2(600, -1400))]
n = 0
for step in range(24):
    ang = step * 15
    if any(min(abs(ang - g), 360 - abs(ang - g)) < 14 for g in gates):
        continue
    x, y = 1150 * math.cos(math.radians(ang)), 1150 * math.sin(math.radians(ang))
    add(classname="ent_dota_tree", origin=f"{x:.0f} {y:.0f} 128", targetname=f"lab_tree_{n:02d}",
        angles=f"0 {ang * 7 % 360} 0", properties={"model": "models/props_tree/tree_pine_01_heavysnow.vmdl"})
    n += 1

# Shopkeeper (visual building; purchase radius normally comes from a trigger_shop brush)
add(classname="ent_dota_shop", origin="450 -550 128", targetname="lab_shop", angles="0 135 0",
    properties={"model": "models/heroes/shopkeeper/shopkeeper.vmdl", "shoptype": "0", "teamnumber": "2"})

# Rift crystals tinted purple
for i, ang in enumerate((45, 135, 225, 315)):
    x, y = 700 * math.cos(math.radians(ang)), 700 * math.sin(math.radians(ang))
    add(classname="prop_dynamic", origin=f"{x:.0f} {y:.0f} 128", targetname=f"lab_crystal_{i}", angles=f"0 {ang} 0",
        scales="1.4 1.4 1.4", properties={"model": "maps/cavern_assets/models/crystals/crystal_cavern_01.vmdl", "rendercolor": "190 90 255"})

print("trees:", n, "added:", added, "failed:", failed)
