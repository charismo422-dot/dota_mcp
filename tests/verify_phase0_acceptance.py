"""Phase 0 acceptance test for vmap_builder, dmxconvert, resourcecompiler, and asset inspectors."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.dota2_mcp.config import CONFIG
from src.dota2_mcp.addon_manager import create_or_configure_addon
from src.dota2_mcp.vmap_builder import (
    prepare_map_from_template,
    add_map_entity,
    remove_map_entity,
    compile_addon_resource,
    _find_matching_brace,
    _find_matching_bracket,
)
from src.dota2_mcp.vpk_explorer import search_sound_events
from src.dota2_mcp.asset_inspector import inspect_model, inspect_particle

TEST_ADDON = "mcp_phase0_test"
TEST_MAP = "test_arena"


def parse_vmap_integrity(vmap_path: Path) -> dict:
    text = vmap_path.read_text(encoding="utf-8")
    all_elementids = re.findall(r'"id"\s+"elementid"\s+"([^"]+)"', text)
    unique_elementids = set(all_elementids)

    all_node_ids = [int(x) for x in re.findall(r'"nodeID"\s+"int"\s+"(\d+)"', text)]

    group_m = re.search(r'"CMapGroup"\s*\{', text)
    group_children = []
    if group_m:
        g_open = text.find("{", group_m.start())
        g_close = _find_matching_brace(text, g_open)
        g_block = text[g_open : g_close + 1]
        ch_m = re.search(r'"children"\s+"element_array"\s*\[', g_block)
        if ch_m:
            b_open = g_block.find("[", ch_m.start())
            b_close = _find_matching_bracket(g_block, b_open)
            group_children = re.findall(
                r'"element"\s+"([^"]+)"', g_block[b_open + 1 : b_close]
            )

    vis_m = re.search(r'"visbility"\s+"CVisibilityMgr"\s*\{', text)
    vis_nodes = []
    vis_flags = []
    if vis_m:
        v_open = text.find("{", vis_m.start())
        v_close = _find_matching_brace(text, v_open)
        v_block = text[v_open : v_close + 1]
        n_m = re.search(r'"nodes"\s+"element_array"\s*\[', v_block)
        if n_m:
            b_open = v_block.find("[", n_m.start())
            b_close = _find_matching_bracket(v_block, b_open)
            vis_nodes = re.findall(
                r'"element"\s+"([^"]+)"', v_block[b_open + 1 : b_close]
            )
        f_m = re.search(r'"hiddenFlags"\s+"int_array"\s*\[', v_block)
        if f_m:
            f_open = v_block.find("[", f_m.start())
            f_close = _find_matching_bracket(v_block, f_open)
            vis_flags = re.findall(r'"(-?\d+)"', v_block[f_open + 1 : f_close])

    return {
        "total_elementids": len(all_elementids),
        "unique_elementids": len(unique_elementids),
        "all_elementids_unique": len(all_elementids) == len(unique_elementids),
        "max_node_id": max(all_node_ids) if all_node_ids else 0,
        "group_children": group_children,
        "vis_nodes": vis_nodes,
        "vis_flags": vis_flags,
        "nodes_len": len(vis_nodes),
        "flags_len": len(vis_flags),
        "nodes_eq_flags_len": len(vis_nodes) == len(vis_flags),
        "raw_text": text,
    }


def run_dmxconvert_to_binary(vmap_path: Path, out_bin_path: Path) -> int:
    proc = subprocess.run(
        [
            str(CONFIG.dmxconvert_exe),
            "-i",
            str(vmap_path),
            "-oe",
            "binary",
            "-of",
            "vmap",
            "-o",
            str(out_bin_path),
        ],
        capture_output=True,
        text=True,
    )
    print("  dmxconvert stdout/stderr:", (proc.stdout + proc.stderr).strip())
    return proc.returncode


def main() -> None:
    try:
        print("=== STEP A: Create temporary addon & prepare map from template ===")
        c_res = create_or_configure_addon(TEST_ADDON, maps=[TEST_MAP])
        assert c_res["ok"], f"create_or_configure_addon failed: {c_res}"
        p_res = prepare_map_from_template(TEST_ADDON, TEST_MAP)
        assert p_res["ok"], f"prepare_map_from_template failed: {p_res}"
        vmap_file = Path(p_res["map_path"])

        before = parse_vmap_integrity(vmap_file)
        print(
            f"BEFORE add_map_entity: max_node_id={before['max_node_id']}, "
            f"elementids={before['total_elementids']} (unique={before['unique_elementids']}), "
            f"children={len(before['group_children'])}, nodes={before['nodes_len']}, hiddenFlags={before['flags_len']}"
        )

        print("\n=== STEP B: Call add_map_entity ===")
        add_res = add_map_entity(
            TEST_ADDON,
            TEST_MAP,
            classname="info_target",
            origin="256 256 128",
            targetname="mcp_test_marker",
            properties={"vscripts": ""},
        )
        assert add_res["ok"], f"add_map_entity failed: {add_res}"
        new_id = add_res["added_entity_id"]

        after_add = parse_vmap_integrity(vmap_file)
        print(
            f"AFTER add_map_entity Check:\n"
            f"  1) all 'elementid' unique: {after_add['all_elementids_unique']} ({after_add['unique_elementids']}/{after_add['total_elementids']})\n"
            f"  2) new_id in CMapGroup.children: {new_id in after_add['group_children']}\n"
            f"  3) new_id in CVisibilityMgr.nodes: {new_id in after_add['vis_nodes']}\n"
            f"  4) len(nodes) == len(hiddenFlags): {after_add['nodes_eq_flags_len']} ({after_add['nodes_len']} == {after_add['flags_len']})\n"
            f"  5) new entity nodeID == old_max + 1: {add_res['nodeID']} == {before['max_node_id'] + 1} ({add_res['nodeID'] == before['max_node_id'] + 1})"
        )
        assert after_add["all_elementids_unique"]
        assert new_id in after_add["group_children"]
        assert new_id in after_add["vis_nodes"]
        assert after_add["nodes_eq_flags_len"]
        assert add_res["nodeID"] == before["max_node_id"] + 1

        bin_out_1 = vmap_file.with_suffix(".bin1.vmap")
        rc_dmx_1 = run_dmxconvert_to_binary(vmap_file, bin_out_1)
        print(
            f"  6) dmxconvert to binary return code: {rc_dmx_1} "
            f"(file size: {bin_out_1.stat().st_size if bin_out_1.exists() else 0} bytes)"
        )
        assert rc_dmx_1 == 0

        print("\n=== STEP C: Compile map with resourcecompiler.exe (after add_map_entity) ===")
        comp_1 = compile_addon_resource(TEST_ADDON, f"maps/{TEST_MAP}.vmap")
        print("  resourcecompiler return_code:", comp_1["return_code"])
        print("  compiled_outputs:", comp_1["compiled_outputs"])
        print(
            "  compiled_map_vpk_entries (.vmap_c, .gnv, etc.):",
            comp_1["compiled_map_vpk_entries"],
        )
        assert comp_1["return_code"] == 0
        assert f"maps/{TEST_MAP}.vmap_c" in comp_1["compiled_map_vpk_entries"]

        print("\n=== STEP D: Call remove_map_entity ===")
        rem_res = remove_map_entity(TEST_ADDON, TEST_MAP, "mcp_test_marker")
        assert rem_res["ok"], f"remove_map_entity failed: {rem_res}"

        after_rem = parse_vmap_integrity(vmap_file)
        uuid_occurrences = after_rem["raw_text"].count(new_id)
        print(
            f"AFTER remove_map_entity Check:\n"
            f"  1) removed UUID occurrences in entire .vmap: {uuid_occurrences}\n"
            f"  2) all 'elementid' unique: {after_rem['all_elementids_unique']} ({after_rem['unique_elementids']}/{after_rem['total_elementids']})\n"
            f"  3) len(nodes) == len(hiddenFlags): {after_rem['nodes_eq_flags_len']} ({after_rem['nodes_len']} == {after_rem['flags_len']})"
        )
        assert uuid_occurrences == 0
        assert after_rem["all_elementids_unique"]
        assert after_rem["nodes_eq_flags_len"]

        bin_out_2 = vmap_file.with_suffix(".bin2.vmap")
        rc_dmx_2 = run_dmxconvert_to_binary(vmap_file, bin_out_2)
        print(
            f"  4) dmxconvert to binary return code: {rc_dmx_2} "
            f"(file size: {bin_out_2.stat().st_size if bin_out_2.exists() else 0} bytes)"
        )
        assert rc_dmx_2 == 0

        print("\n=== STEP E: Compile map with resourcecompiler.exe (after remove_map_entity) ===")
        comp_2 = compile_addon_resource(TEST_ADDON, f"maps/{TEST_MAP}.vmap")
        print("  resourcecompiler return_code:", comp_2["return_code"])
        print("  compiled_outputs:", comp_2["compiled_outputs"])
        assert comp_2["return_code"] == 0

        print("\n=== STEP F: Verify item 7 (search_sound_events) & item 10 (inspect_particle / inspect_model) ===")
        snd = search_sound_events("Hero_Pudge.Attack", file_filter="pudge", limit=5)
        print("  search_sound_events:", snd)
        pt = inspect_particle(
            "particles/econ/items/pudge/pudge_dragonclaw/pudge_meathook_dragonclaw.vpcf"
        )
        print("  inspect_particle CPs:", pt["control_points_used"])
        md = inspect_model("models/heroes/pudge/pudge.vmdl")
        print(
            "  inspect_model attachment_bones sample:",
            dict(list(md["attachment_bones"].items())[:4]),
        )
    finally:
        for base in (CONFIG.game_addons_dir, CONFIG.content_addons_dir):
            if base and (base / TEST_ADDON).exists():
                shutil.rmtree(base / TEST_ADDON, ignore_errors=True)
        print("\nCleaned up temporary test addon:", TEST_ADDON)


if __name__ == "__main__":
    main()
