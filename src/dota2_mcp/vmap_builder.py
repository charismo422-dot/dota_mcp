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

    # Prefer cloning a simple point entity ( without nested mesh children )
    donor = raw_ents[0]
    for e in raw_ents:
        if e["classname"].startswith("info_") or e["classname"].startswith("ent_dota_"):
            donor = e
            break

    new_ent_id = str(uuid.uuid4())
    new_props_id = str(uuid.uuid4())

    merged_props: dict[str, str] = {"classname": classname}
    if targetname:
        merged_props["targetname"] = targetname
    if properties:
        for k, v in properties.items():
            merged_props[str(k)] = str(v)

    # Detect indentation of donor
    donor_raw = donor["_raw"]
    new_block = donor_raw

    # Replace top-level entity id
    new_block = re.sub(
        r'("id"\s+"elementid"\s+")[^"]+(")',
        rf"\g<1>{new_ent_id}\2",
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

    # Rebuild the entity_properties inner block
    props_m = re.search(
        r'"entity_properties"\s+"(?:EditGameClassProps|CDmePropertyList|element)"\s*\{',
        new_block,
    )
    if props_m:
        p_open = new_block.find("{", props_m.start())
        p_close = _find_matching_brace(new_block, p_open)
        if p_close != -1:
            prop_lines = [f'\n\t\t\t\t\t"id" "elementid" "{new_props_id}"']
            for pk, pv in merged_props.items():
                safe_pv = str(pv).replace('"', '\\"')
                prop_lines.append(f'\t\t\t\t\t"{pk}" "string" "{safe_pv}"')
            prop_lines.append("\t\t\t\t")
            new_block = (
                new_block[: p_open + 1]
                + "\n".join(prop_lines)
                + new_block[p_close:]
            )

    # Insert right after the donor entity in the same element_array
    insert_pos = donor["_end"]
    updated_text = text[:insert_pos] + "\n\t\t\t" + new_block + text[insert_pos:]
    vmap_path.write_text(updated_text, encoding="utf-8")

    return {
        "ok": True,
        "added_entity_id": new_ent_id,
        "classname": classname,
        "targetname": targetname,
        "origin": origin,
        "map_path": str(vmap_path),
    }


def remove_map_entity(
    addon_name: str, map_name: str, targetname_or_id: str
) -> dict[str, Any]:
    """Remove CMapEntity matching targetname or element id from the .vmap."""
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

    start_idx = target["_start"]
    end_idx = target["_end"]
    # Also strip trailing newline/tabs if present
    while end_idx < len(text) and text[end_idx] in (" ", "\t", "\r", "\n"):
        end_idx += 1

    updated_text = text[:start_idx] + text[end_idx:]
    vmap_path.write_text(updated_text, encoding="utf-8")

    return {
        "ok": True,
        "removed_id": target["id"],
        "removed_classname": target["classname"],
        "removed_targetname": target["targetname"],
    }


def compile_addon_resource(addon_name: str, resource_rel_path: str) -> dict[str, Any]:
    """Compile a map (.vmap), Panorama layout, or material using resourcecompiler.exe."""
    if not CONFIG.content_addons_dir:
        return {"ok": False, "error": "Dota 2 content directory not found."}
    if not CONFIG.resourcecompiler_exe or not CONFIG.resourcecompiler_exe.exists():
        return {
            "ok": False,
            "error": f"resourcecompiler.exe not found at {CONFIG.resourcecompiler_exe}",
        }

    full_input = CONFIG.content_addons_dir / addon_name / resource_rel_path.lstrip("/\\")
    if not full_input.exists():
        return {"ok": False, "error": f"Resource file does not exist: {full_input}"}

    try:
        proc = subprocess.run(
            [
                str(CONFIG.resourcecompiler_exe),
                "-i",
                str(full_input),
                "-v",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
        lines = [line.strip() for line in combined.splitlines() if line.strip()]
        error_lines = [
            l for l in lines if any(w in l.lower() for w in ("error", "fail", "warning", "fatal"))
        ]
        return {
            "ok": proc.returncode == 0,
            "return_code": proc.returncode,
            "resource": str(full_input),
            "errors_and_warnings": error_lines[-40:],
            "tail_log": lines[-25:],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
