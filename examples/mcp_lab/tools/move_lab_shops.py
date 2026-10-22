"""Move both shopkeepers to free spots (the home shopkeeper stood inside a crystal) and give the secret shop
an animated model (secretshopkeeper_dire.vmdl has no animations at all)."""
import sys

sys.path.insert(0, r"D:\Antigravity\dota-mcp")
from src.dota2_mcp import vmap_builder as vb

A, M = "mcp_lab", "lab"
for name in ("lab_shop", "lab_secret_shop"):
    print(name, "removed:", vb.remove_map_entity(A, M, name).get("ok"))

for name, origin, angles, model, shoptype in (
    ("lab_shop", "250 -800 128", "0 110 0", "models/heroes/shopkeeper/shopkeeper.vmdl", "0"),
    ("lab_secret_shop", "850 -150 128", "0 160 0", "models/heroes/shopkeeper_dire/shopkeeper_dire.vmdl", "2"),
):
    r = vb.add_map_entity(A, M, classname="ent_dota_shop", origin=origin, targetname=name, angles=angles,
                          properties={"model": model, "shoptype": shoptype, "teamnumber": "2"})
    print(name, "added:", r.get("ok"), "overlap:", r.get("overlap_warning", "none"))
