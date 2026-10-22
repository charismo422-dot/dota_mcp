"""Module 2: Deep inspection of compiled models (.vmdl_c) and particles (.vpcf_c) via Source2Viewer-CLI."""

from __future__ import annotations

import re
import subprocess
from typing import Any, Optional

from .config import CACHE_DIR, CONFIG
from .vpk_explorer import extract_vpk_file_to_cache


def _run_decompiler_block_dump(
    compiled_file_path: str, block_name: Optional[str] = None
) -> str:
    """Run Source2Viewer-CLI / Decompiler.exe to dump resource blocks as text."""
    exe = CONFIG.decompiler_exe
    if not exe.exists():
        raise FileNotFoundError(
            f"Decompiler binary not found at {exe}. "
            "Run: python -m src.dota2_mcp.diagnostics --bootstrap"
        )

    cmd = [str(exe), "-i", compiled_file_path]
    if block_name:
        cmd.extend(["-b", block_name])
    else:
        cmd.append("--all")

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0 and not proc.stdout:
        raise RuntimeError(f"Decompiler failed (exit {proc.returncode}): {output[:500]}")
    return output


def inspect_model(model_path: str) -> dict[str, Any]:
    """Extract .vmdl_c and parse animations, ACT_DOTA_* activities, and attach_* points with bones."""
    try:
        local_file = extract_vpk_file_to_cache(model_path, CACHE_DIR)
    except Exception as exc:
        return {"ok": False, "model_path": model_path, "error": str(exc)}

    try:
        dump = _run_decompiler_block_dump(str(local_file))
    except Exception:
        raw_bytes = local_file.read_bytes()
        dump = raw_bytes.decode("latin-1", errors="ignore")

    # Verified against Source2Viewer-CLI output on models/heroes/pudge/pudge.vmdl_c:
    # m_activityArray = [ { m_name = "ACT_DOTA_CAPTURE" ... } ]
    activities = sorted(set(re.findall(r"\bACT_DOTA_[A-Z0-9_]+\b", dump)))

    # m_attachments = [ { key = "attach_hook" value = { m_name = "attach_hook" m_influenceNames = [ "weapon_rt_1", ... ] } } ]
    attachments = sorted(set(re.findall(r"\battach_[a-zA-Z0-9_]+\b", dump)))
    attachment_bones: dict[str, str] = {}
    for att_match in re.finditer(
        r'm_name\s*=\s*"(attach_[a-zA-Z0-9_]+)"\s+m_influenceNames\s*=\s*\[\s*"([^"]*)"',
        dump,
    ):
        attachment_bones[att_match.group(1)] = att_match.group(2)

    anim_names = sorted(
        set(
            re.findall(
                r'"(@?[a-zA-Z0-9_]+(?:_anim|_attack|_idle|_run|_cast|_die|_flail|_stun)[a-zA-Z0-9_]*)"',
                dump,
            )
        )
    )
    cleaned_anims = [a for a in anim_names if not a.startswith("m_")][:60]

    return {
        "ok": True,
        "model_path": model_path.removesuffix("_c"),
        "activities": activities,
        "attachments": attachments,
        "attachment_bones": attachment_bones,
        "animation_identifiers_sample": cleaned_anims,
    }


def inspect_particle(particle_path: str) -> dict[str, Any]:
    """Extract .vpcf_c and inspect Control Points (CPs), child particles, and operators."""
    try:
        local_file = extract_vpk_file_to_cache(particle_path, CACHE_DIR)
    except Exception as exc:
        return {"ok": False, "particle_path": particle_path, "error": str(exc)}

    try:
        dump = _run_decompiler_block_dump(str(local_file))
    except Exception:
        raw_bytes = local_file.read_bytes()
        dump = raw_bytes.decode("latin-1", errors="ignore")

    # Verified against Source2Viewer-CLI KV3 DATA block in pudge_meathook_dragonclaw.vpcf_c:
    # Matches m_nControlPointNumber = 1, m_nOverrideCP = 2, m_nFirstControlPoint = 3, m_nScaleControlPoint = ...
    cp_matches = re.findall(
        r"\b(?:m_n[A-Za-z0-9_]*ControlPoint[A-Za-z0-9_]*|m_n[A-Za-z0-9_]*CP[A-Za-z0-9_]*|control_point)\s*=\s*(\d+)",
        dump,
    )
    control_points = sorted({int(cp) for cp in cp_matches})

    child_particles = sorted(
        set(re.findall(r"particles/[a-zA-Z0-9_/.-]+\.vpcf", dump))
    )
    operators = sorted(set(re.findall(r"\bC_OP_[A-Za-z0-9_]+\b", dump)))
    initializers = sorted(set(re.findall(r"\bC_INIT_[A-Za-z0-9_]+\b", dump)))

    return {
        "ok": True,
        "particle_path": particle_path.removesuffix("_c"),
        "control_points_used": control_points,
        "child_particles": child_particles,
        "initializers": initializers[:30],
        "operators": operators[:30],
    }
