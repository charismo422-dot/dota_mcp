"""Module 4: Safe .vmap editing via dmxconvert (keyvalues2) and compiling via resourcecompiler."""

from __future__ import annotations

import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Optional

from .config import CONFIG


def _resolve_map_path(addon_name: str, map_name: str) -> Path:
    if not CONFIG.content_addons_dir:
        raise RuntimeError("Dota 2 content_addons_dir not found.")
    clean_name = map_name[:-5] if map_name.endswith(".vmap") else map_name
    return CONFIG.content_addons_dir / addon_name / "maps" / f"{clean_name}.vmap"


def _ensure_keyvalues2_vmap(vmap_path: Path) -> None:
    """If vmap_path is binary DMX, convert it in-place to keyvalues2 text via dmxconvert.exe."""
    if not vmap_path.exists():
        raise FileNotFoundError(f"Map file not found: {vmap_path}")

    with open(vmap_path, "rb") as f:
        header = f.read(128)

    if b"keyvalues2" in header:
        return

    if not CONFIG.dmxconvert_exe or not CONFIG.dmxconvert_exe.exists():
        raise FileNotFoundError(
            f"dmxconvert.exe not found at {CONFIG.dmxconvert_exe}. Cannot convert binary .vmap."
        )

    tmp_out = vmap_path.with_suffix(".kv2.vmap")
    proc = subprocess.run(
        [
            str(CONFIG.dmxconvert_exe),
            "-i",
            str(vmap_path),
            "-oe",
            "keyvalues2",
            "-of",
            "vmap",
            "-o",
            str(tmp_out),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if proc.returncode != 0 or not tmp_out.exists():
        raise RuntimeError(
            f"dmxconvert failed (exit {proc.returncode}): {proc.stdout} {proc.stderr}"
        )
    shutil.move(str(tmp_out), str(vmap_path))


def prepare_map_from_template(
    addon_name: str, map_name: str, source_template: str = "template_map"
) -> dict[str, Any]:
    """Copy a template .vmap into the addon's maps/ folder and convert it to editable keyvalues2 text."""
    if not CONFIG.content_addons_dir:
        return {"ok": False, "error": "Dota 2 content directory not found."}

    target_vmap = _resolve_map_path(addon_name, map_name)
    target_vmap.parent.mkdir(parents=True, exist_ok=True)

    tpl_clean = source_template[:-5] if source_template.endswith(".vmap") else source_template
    candidate_templates = [
        CONFIG.content_addons_dir / addon_name / "maps" / f"{tpl_clean}.vmap",
        CONFIG.content_addons_dir / "addon_template" / "maps" / f"{tpl_clean}.vmap",
        CONFIG.content_addons_dir / "addon_template" / "maps" / "template_map.vmap",
    ]

    if not target_vmap.exists():
        src_found: Optional[Path] = None
        for cand in candidate_templates:
            if cand.exists():
                src_found = cand
                break
        if not src_found:
            return {
                "ok": False,
                "error": f"Could not find template map '{source_template}' in {candidate_templates}",
            }
        shutil.copy2(src_found, target_vmap)

    try:
        _ensure_keyvalues2_vmap(target_vmap)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "addon_name": addon_name,
        "map_path": str(target_vmap),
        "encoding": "keyvalues2",
    }


def _find_matching_brace(text: str, open_brace_idx: int) -> int:
    """Return index of matching '}' for '{' at open_brace_idx, respecting quoted strings."""
    depth = 0
    in_quotes = False
    escape = False
    for i in range(open_brace_idx, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_quotes = not in_quotes
            continue
        if not in_quotes:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
    return -1


def _find_matching_bracket(text: str, open_bracket_idx: int) -> int:
    """Return index of matching ']' for '[' at open_bracket_idx, respecting quoted strings."""
    depth = 0
    in_quotes = False
    escape = False
    for i in range(open_bracket_idx, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_quotes = not in_quotes
            continue
        if not in_quotes:
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return i
    return -1


def _extract_cmap_entities(vmap_text: str) -> list[dict[str, Any]]:
    """Locate all CMapEntity blocks in a keyvalues2 .vmap text without loading mesh arrays."""
    entities: list[dict[str, Any]] = []
    pattern = re.compile(r'"CMapEntity"\s*\{')

    for match in pattern.finditer(vmap_text):
        start_idx = match.start()
        brace_open = match.end() - 1
        brace_close = _find_matching_brace(vmap_text, brace_open)
        if brace_close == -1:
            continue

        block = vmap_text[start_idx : brace_close + 1]

        ent_id_m = re.search(r'"id"\s+"elementid"\s+"([^"]+)"', block)
        node_id_m = re.search(r'"nodeID"\s+"int"\s+"(\d+)"', block)
        origin_m = re.search(r'"origin"\s+"vector3"\s+"([^"]+)"', block)
        angles_m = re.search(r'"angles"\s+"qangle"\s+"([^"]+)"', block)
        scales_m = re.search(r'"scales"\s+"vector3"\s+"([^"]+)"', block)

        # Parse entity_properties / EditGameClassProps block
        props: dict[str, str] = {}
        props_m = re.search(
            r'"entity_properties"\s+"(?:EditGameClassProps|CDmePropertyList|element)"\s*\{',
            block,
        )
        if props_m:
            p_open = block.find("{", props_m.start())
            p_close = _find_matching_brace(block, p_open)
            if p_close != -1:
                props_block = block[p_open + 1 : p_close]
                for kv_m in re.finditer(
                    r'"([^"]+)"\s+"string"\s+"([^"]*)"', props_block
                ):
                    key, val = kv_m.group(1), kv_m.group(2)
                    if key != "id":
                        props[key] = val

        entities.append(
            {
                "id": ent_id_m.group(1) if ent_id_m else "",
                "nodeID": int(node_id_m.group(1)) if node_id_m else 0,
                "classname": props.get("classname", ""),
                "targetname": props.get("targetname", ""),
                "origin": origin_m.group(1) if origin_m else "0 0 0",
                "angles": angles_m.group(1) if angles_m else "0 0 0",
                "scales": scales_m.group(1) if scales_m else "1 1 1",
                "properties": props,
                "_start": start_idx,
                "_end": brace_close + 1,
                "_raw": block,
            }
        )
    return entities


def list_map_entities(
    addon_name: str, map_name: str, classname_filter: str = ""
) -> dict[str, Any]:
    """List all CMapEntity objects in the map with their coordinates and properties."""
    try:
        vmap_path = _resolve_map_path(addon_name, map_name)
        _ensure_keyvalues2_vmap(vmap_path)
        text = vmap_path.read_text(encoding="utf-8", errors="replace")
        raw_ents = _extract_cmap_entities(text)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    flt = classname_filter.lower().strip()
    cleaned: list[dict[str, Any]] = []
    for e in raw_ents:
        if flt and flt not in e["classname"].lower() and flt not in e["targetname"].lower():
            continue
        cleaned.append(
            {
                "id": e["id"],
                "nodeID": e["nodeID"],
                "classname": e["classname"],
                "targetname": e["targetname"],
                "origin": e["origin"],
                "angles": e["angles"],
                "scales": e["scales"],
                "properties": e["properties"],
            }
        )

    return {
        "ok": True,
        "map_path": str(vmap_path),
        "total_entities": len(cleaned),
        "entities": cleaned,
    }


def _append_to_visibility_mgr(text: str, new_ent_id: str) -> str:
    """Append new_ent_id to CVisibilityMgr.nodes and '0' to CVisibilityMgr.hiddenFlags with valid comma syntax."""
    vis_m = re.search(r'"visbility"\s+"CVisibilityMgr"\s*\{', text)
    if not vis_m:
        return text

    vis_open = text.find("{", vis_m.start())
    vis_close = _find_matching_brace(text, vis_open)
    if vis_close == -1:
        return text

    vis_block = text[vis_open : vis_close + 1]

    # 1. Update "nodes" "element_array" [ ... ]
    nodes_m = re.search(r'"nodes"\s+"element_array"\s*\[', vis_block)
    if nodes_m:
        b_open = vis_block.find("[", nodes_m.start())
        b_close = _find_matching_bracket(vis_block, b_open)
        if b_close != -1:
            inner = vis_block[b_open + 1 : b_close]
            existing_items = re.findall(r'"element"\s+"([^"]+)"', inner)
            all_items = existing_items + [new_ent_id]
            new_inner = (
                "\n"
                + ",\n".join(f'\t\t\t"element" "{uid}"' for uid in all_items)
                + "\n\t\t"
            )
            vis_block = vis_block[: b_open + 1] + new_inner + vis_block[b_close:]

    # 2. Update "hiddenFlags" "int_array" [ ... ]
    flags_m = re.search(r'"hiddenFlags"\s+"int_array"\s*\[', vis_block)
    if flags_m:
        f_open = vis_block.find("[", flags_m.start())
        f_close = _find_matching_bracket(vis_block, f_open)
        if f_close != -1:
            inner_f = vis_block[f_open + 1 : f_close]
            existing_flags = re.findall(r'"(-?\d+)"', inner_f)
            all_flags = existing_flags + ["0"]
            new_inner_f = (
                "\n"
                + ",\n".join(f'\t\t\t"{fl}"' for fl in all_flags)
                + "\n\t\t"
            )
            vis_block = vis_block[: f_open + 1] + new_inner_f + vis_block[f_close:]

    return text[:vis_open] + vis_block + text[vis_close + 1 :]


def _remove_from_visibility_mgr(text: str, target_ent_id: str) -> str:
    """Remove target_ent_id from CVisibilityMgr.nodes and its matching index from CVisibilityMgr.hiddenFlags."""
    vis_m = re.search(r'"visbility"\s+"CVisibilityMgr"\s*\{', text)
    if not vis_m:
        return text

    vis_open = text.find("{", vis_m.start())
    vis_close = _find_matching_brace(text, vis_open)
    if vis_close == -1:
        return text

    vis_block = text[vis_open : vis_close + 1]
    removed_index: Optional[int] = None

    nodes_m = re.search(r'"nodes"\s+"element_array"\s*\[', vis_block)
    if nodes_m:
        b_open = vis_block.find("[", nodes_m.start())
        b_close = _find_matching_bracket(vis_block, b_open)
        if b_close != -1:
            inner = vis_block[b_open + 1 : b_close]
            existing_items = re.findall(r'"element"\s+"([^"]+)"', inner)
            if target_ent_id in existing_items:
                removed_index = existing_items.index(target_ent_id)
                new_items = [u for u in existing_items if u != target_ent_id]
                if new_items:
                    new_inner = (
                        "\n"
                        + ",\n".join(f'\t\t\t"element" "{uid}"' for uid in new_items)
                        + "\n\t\t"
                    )
                else:
                    new_inner = "\n\t\t"
                vis_block = vis_block[: b_open + 1] + new_inner + vis_block[b_close:]

    if removed_index is not None:
        flags_m = re.search(r'"hiddenFlags"\s+"int_array"\s*\[', vis_block)
        if flags_m:
            f_open = vis_block.find("[", flags_m.start())
            f_close = _find_matching_bracket(vis_block, f_open)
            if f_close != -1:
                inner_f = vis_block[f_open + 1 : f_close]
                existing_flags = re.findall(r'"(-?\d+)"', inner_f)
                if 0 <= removed_index < len(existing_flags):
                    existing_flags.pop(removed_index)
                if existing_flags:
                    new_inner_f = (
                        "\n"
                        + ",\n".join(f'\t\t\t"{fl}"' for fl in existing_flags)
                        + "\n\t\t"
                    )
                else:
                    new_inner_f = "\n\t\t"
                vis_block = vis_block[: f_open + 1] + new_inner_f + vis_block[f_close:]

    return text[:vis_open] + vis_block + text[vis_close + 1 :]


def _append_to_parent_children_array(
    text: str, donor_id: str, new_ent_id: str
) -> str:
    """Insert '"element" "<new_ent_id>"' right after '"element" "<donor_id>"' inside parent 'children' element_array."""
    # Search outside CVisibilityMgr (which uses 'nodes') for '"element" "<donor_id>"'
    pattern = re.compile(
        rf'([ \t]*"element"\s+"{re.escape(donor_id)}")(\s*,?)'
    )

    # Note: donor_id may appear in CVisibilityMgr.nodes AND in CMapGroup.children (or CMapWorld.children).
    # We only want to add it to 'children' element_array here because CVisibilityMgr is handled by _append_to_visibility_mgr.
    vis_m = re.search(r'"visbility"\s+"CVisibilityMgr"\s*\{', text)
    vis_range = (-1, -1)
    if vis_m:
        v_open = text.find("{", vis_m.start())
        v_close = _find_matching_brace(text, v_open)
        vis_range = (vis_m.start(), v_close + 1 if v_close != -1 else -1)

    for m in pattern.finditer(text):
        if vis_range[0] <= m.start() <= vis_range[1]:
            continue
        indent_match = re.match(r"^([ \t]*)", m.group(1))
        indent = indent_match.group(1) if indent_match else "\t\t"
        has_comma = "," in m.group(2)
        if has_comma:
            replacement = f'{m.group(1)},\n{indent}"element" "{new_ent_id}",'
        else:
            replacement = f'{m.group(1)},\n{indent}"element" "{new_ent_id}"'
        return text[: m.start()] + replacement + text[m.end() :]

    return text


def _remove_from_parent_children_arrays(text: str, target_ent_id: str) -> str:
    """Remove '"element" "<target_ent_id>"' from any 'children' element_array while keeping comma syntax valid."""
    # Rebuild any '"children" "element_array" [ ... ]' block that contains '"element" "<target_ent_id>"'
    pattern = re.compile(r'"children"\s+"element_array"\s*\[')
    pos = 0
    while True:
        m = pattern.search(text, pos)
        if not m:
            break
        b_open = text.find("[", m.start())
        b_close = _find_matching_bracket(text, b_open)
        if b_close == -1:
            pos = m.end()
            continue

        inner = text[b_open + 1 : b_close]
        if f'"{target_ent_id}"' in inner:
            # Remove either:
            # 1) Leading comma + whitespace + "element" "target_ent_id" (when it's the last or middle item)
            # 2) "element" "target_ent_id" + trailing comma + whitespace (when it's the first item)
            # 3) "element" "target_ent_id" (when it's the only item)
            new_inner, count = re.subn(
                rf',\s*"element"\s+"{re.escape(target_ent_id)}"',
                "",
                inner,
                count=1,
            )
            if count == 0:
                new_inner, count = re.subn(
                    rf'"element"\s+"{re.escape(target_ent_id)}"\s*,\s*',
                    "",
                    inner,
                    count=1,
                )
            if count == 0:
                new_inner = re.sub(
                    rf'"element"\s+"{re.escape(target_ent_id)}"\s*',
                    "",
                    inner,
                    count=1,
                )
            text = text[: b_open + 1] + new_inner + text[b_close:]
            pos = b_open + 1 + len(new_inner)
        else:
            pos = m.end()
    return text


OVERLAP_WARN_RADIUS = 250.0  # units; model entities closer than this to a new model entity are reported


def add_map_entity(
    addon_name: str,
    map_name: str,
    classname: str,
    origin: str,
    targetname: str = "",
    angles: str = "0 0 0",
    scales: str = "1 1 1",
    properties: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Add a new CMapEntity to the .vmap by cloning the exact schema of existing point entities."""
    try:
        vmap_path = _resolve_map_path(addon_name, map_name)
        _ensure_keyvalues2_vmap(vmap_path)
        text = vmap_path.read_text(encoding="utf-8", errors="replace")
        raw_ents = _extract_cmap_entities(text)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    if not raw_ents:
        return {
            "ok": False,
            "error": "No existing CMapEntity found in map to clone schema from.",
        }

    # Prefer cloning 'info_player_start_goodguys' or another clean point entity without children
    donor = raw_ents[0]
    for e in raw_ents:
        if e["classname"] == "info_player_start_goodguys":
            donor = e
            break
    else:
        for e in raw_ents:
            if e["classname"].startswith("info_") or e["classname"].startswith("ent_dota_"):
                donor = e
                break

    # Compute max nodeID across the entire .vmap file
    all_node_ids = [int(x) for x in re.findall(r'"nodeID"\s+"int"\s+"(\d+)"', text)]
    new_node_id = (max(all_node_ids) + 1) if all_node_ids else 1

    merged_props: dict[str, str] = {"classname": classname}
    if targetname:
        merged_props["targetname"] = targetname
    if properties:
        for k, v in properties.items():
            merged_props[str(k)] = str(v)

    donor_raw = donor["_raw"]

    # Replace EVERY "id" "elementid" "..." inside the cloned block with a fresh UUID
    generated_uuids: list[str] = []

    def _replace_uuid(match: re.Match) -> str:
        fresh = str(uuid.uuid4())
        generated_uuids.append(fresh)
        return f'{match.group(1)}{fresh}{match.group(2)}'

    new_block = re.sub(
        r'("id"\s+"elementid"\s+")[^"]+(")',
        _replace_uuid,
        donor_raw,
    )
    new_ent_id = generated_uuids[0] if generated_uuids else str(uuid.uuid4())

    # Replace nodeID with max + 1
    new_block = re.sub(
        r'("nodeID"\s+"int"\s+")\d+(")',
        rf"\g<1>{new_node_id}\2",
        new_block,
        count=1,
    )

    # Replace origin, angles, scales
    new_block = re.sub(
        r'("origin"\s+"vector3"\s+")[^"]+(")',
        rf"\g<1>{origin}\2",
        new_block,
        count=1,
    )
    new_block = re.sub(
        r'("angles"\s+"qangle"\s+")[^"]+(")',
        rf"\g<1>{angles}\2",
        new_block,
        count=1,
    )
    new_block = re.sub(
        r'("scales"\s+"vector3"\s+")[^"]+(")',
        rf"\g<1>{scales}\2",
        new_block,
        count=1,
    )

    # Rebuild the entity_properties inner block with its own fresh UUID
    new_props_id = str(uuid.uuid4())
    props_m = re.search(
        r'"entity_properties"\s+"(?:EditGameClassProps|CDmePropertyList|element)"\s*\{',
        new_block,
    )
    if props_m:
        p_open = new_block.find("{", props_m.start())
        p_close = _find_matching_brace(new_block, p_open)
        if p_close != -1:
            prop_lines = [f'\n\t\t"id" "elementid" "{new_props_id}"']
            for pk, pv in merged_props.items():
                safe_pv = str(pv).replace('"', '\\"')
                prop_lines.append(f'\t\t"{pk}" "string" "{safe_pv}"')
            prop_lines.append("\t")
            new_block = (
                new_block[: p_open + 1]
                + "\n".join(prop_lines)
                + new_block[p_close:]
            )

    # 1. Insert the new top-level CMapEntity block right after donor block (separated by \n\n, no comma)
    insert_pos = donor["_end"]
    updated_text = text[:insert_pos] + "\n\n" + new_block + text[insert_pos:]

    # 2. Register '"element" "<new_ent_id>"' in parent's children element_array (CMapGroup / CMapWorld)
    updated_text = _append_to_parent_children_array(
        updated_text, donor_id=donor["id"], new_ent_id=new_ent_id
    )

    # 3. Register '"element" "<new_ent_id>"' in CVisibilityMgr.nodes and "0" in CVisibilityMgr.hiddenFlags
    updated_text = _append_to_visibility_mgr(updated_text, new_ent_id=new_ent_id)

    vmap_path.write_text(updated_text, encoding="utf-8")

    result: dict[str, Any] = {
        "ok": True,
        "added_entity_id": new_ent_id,
        "nodeID": new_node_id,
        "classname": classname,
        "targetname": targetname,
        "origin": origin,
        "map_path": str(vmap_path),
    }
    # Overlap guard: warn about visible entities (with a model) too close to the new one, e.g. a shopkeeper
    # placed inside a crystal. Obstructions/markers without models are ignored.
    if properties and properties.get("model"):
        try:
            nx, ny = (float(v) for v in origin.split()[:2])
            close = []
            for e in raw_ents:
                if not e.get("properties", {}).get("model"):
                    continue
                ex, ey = (float(v) for v in str(e.get("origin", "0 0 0")).split()[:2])
                dist = ((ex - nx) ** 2 + (ey - ny) ** 2) ** 0.5
                if dist < OVERLAP_WARN_RADIUS:
                    close.append(f'{e.get("classname")} "{e.get("targetname", "")}" at {dist:.0f} units')
            if close:
                result["overlap_warning"] = close
        except (ValueError, TypeError):
            pass
    return result


def remove_map_entity(
    addon_name: str, map_name: str, targetname_or_id: str
) -> dict[str, Any]:
    """Remove CMapEntity matching targetname or element id from the .vmap along with all references."""
    try:
        vmap_path = _resolve_map_path(addon_name, map_name)
        _ensure_keyvalues2_vmap(vmap_path)
        text = vmap_path.read_text(encoding="utf-8", errors="replace")
        raw_ents = _extract_cmap_entities(text)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    target = None
    for e in raw_ents:
        if e["id"] == targetname_or_id or (
            e["targetname"] and e["targetname"] == targetname_or_id
        ):
            target = e
            break

    if not target:
        return {
            "ok": False,
            "error": f"Entity '{targetname_or_id}' not found in {vmap_path.name}",
        }

    removed_id = target["id"]
    start_idx = target["_start"]
    end_idx = target["_end"]
    # Strip trailing blank lines after the removed top-level CMapEntity block
    while end_idx < len(text) and text[end_idx] in (" ", "\t", "\r", "\n"):
        end_idx += 1

    updated_text = text[:start_idx] + text[end_idx:]

    # Remove reference from parent children element_array (CMapGroup / CMapWorld)
    updated_text = _remove_from_parent_children_arrays(updated_text, removed_id)

    # Remove reference from CVisibilityMgr.nodes and corresponding flag from CVisibilityMgr.hiddenFlags
    updated_text = _remove_from_visibility_mgr(updated_text, removed_id)

    vmap_path.write_text(updated_text, encoding="utf-8")

    return {
        "ok": True,
        "removed_id": removed_id,
        "removed_classname": target["classname"],
        "removed_targetname": target["targetname"],
    }


def compile_addon_resource(addon_name: str, resource_rel_path: str) -> dict[str, Any]:
    """Compile a map (.vmap), Panorama layout, or material using resourcecompiler.exe."""
    if not CONFIG.content_addons_dir or not CONFIG.game_addons_dir:
        return {"ok": False, "error": "Dota 2 content/game directory not found."}
    if not CONFIG.resourcecompiler_exe or not CONFIG.resourcecompiler_exe.exists():
        return {
            "ok": False,
            "error": f"resourcecompiler.exe not found at {CONFIG.resourcecompiler_exe}",
        }

    clean_rel = resource_rel_path.lstrip("/\\")
    full_input = CONFIG.content_addons_dir / addon_name / clean_rel
    if not full_input.exists():
        return {"ok": False, "error": f"Resource file does not exist: {full_input}"}

    is_map = full_input.suffix.lower() == ".vmap"
    cmd = [
        str(CONFIG.resourcecompiler_exe),
        "-i",
        str(full_input),
    ]
    if is_map:
        # Verified Hammer Fast Compile flags from tools/hammer.dll and resourcecompiler.dll:
        # Builds world geometry, physics, gridnav, and entities into game/dota_addons/<addon>/maps/<map>.vpk
        # (containing maps/<map>.vmap_c, maps/<map>.gnv, world.vwrld_c, entities/default_ents.vents_c)
        # without slow GPU raytraced lightmap baking.
        cmd.extend(
            [
                "-fshallow",
                "-v",
                "-world",
                "-phys",
                "-gridnav",
                "-entities",
                "-nolightmaps",
            ]
        )
    else:
        cmd.append("-v")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        lines = [line.strip() for line in combined.splitlines() if line.strip()]
        error_lines = [
            l
            for l in lines
            if any(w in l.lower() for w in ("error", "fail", "warning", "fatal"))
        ]

        compiled_outputs: list[str] = []
        compiled_vpk_entries: list[str] = []
        if is_map:
            game_maps_dir = CONFIG.game_addons_dir / addon_name / "maps"
            if game_maps_dir.exists():
                for out_f in game_maps_dir.glob(f"{full_input.stem}*"):
                    compiled_outputs.append(str(out_f))
                    if out_f.suffix.lower() == ".vpk":
                        try:
                            import vpk as _vpk

                            if _vpk is not None:
                                pak = _vpk.open(str(out_f))
                                compiled_vpk_entries = sorted(list(pak))
                        except Exception:
                            pass

        # resourcecompiler exits 0 even when it cannot write the output (e.g. lab.vpk locked by a running game)
        write_failures = [l for l in lines if l.strip().startswith("Write ") and l.rstrip().endswith("Failed!")]

        # Compact output (context cost): drop known-benign SDK noise, de-duplicate, keep the log tail only on failure
        benign = re.compile(
            r"Error creating shader generic\.vfx|soundevents_test\.vsndevts_c|surfaceproperties_steamaudio\.txt|"
            r"nav_hulls\.vdata_c|Aggregate Rejections|Couldn't load public key|Not signing"
        )
        meaningful_errors = list(dict.fromkeys(l for l in error_lines if not benign.search(l)))
        ok = proc.returncode == 0 and not write_failures
        summary = next((l for l in reversed(lines) if re.match(r"(OK|ERROR):\s+\d+ compiled", l)), "")
        result: dict[str, Any] = {
            "ok": ok,
            "return_code": proc.returncode,
            "resource": str(full_input),
            "summary": summary,
            "compiled_outputs": compiled_outputs,
            "compiled_map_entries_count": len(compiled_vpk_entries),
            "compiled_map_has_vmap_c": any(e.endswith(".vmap_c") for e in compiled_vpk_entries),
            "errors_and_warnings": meaningful_errors[-20:],
            "benign_lines_hidden": len(error_lines) - len(meaningful_errors),
        }
        if not ok:
            result["command"] = cmd
            result["tail_log"] = lines[-25:]
        if write_failures:
            result["write_failures"] = write_failures
            result["hint"] = (
                "Output file is locked, most likely by Dota 2 with this map loaded. "
                "Run 'disconnect' via run_console_command, then compile again."
            )
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
