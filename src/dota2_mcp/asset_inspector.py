"""Module 2: Deep inspection of compiled models (.vmdl_c) and particles (.vpcf_c) via Decompiler CLI."""

from __future__ import annotations

import re
import subprocess
from typing import Any

from .config import CACHE_DIR, CONFIG
from .vpk_explorer import extract_vpk_file_to_cache


def _run_decompiler_block_dump(compiled_file_path: str) -> str:
    """Run Source2Viewer-CLI / Decompiler.exe with --all to dump resource blocks as text."""
    exe = CONFIG.decompiler_exe
    if not exe.exists():
        raise FileNotFoundError(
            f"Decompiler binary not found at {exe}. "
            "Run: python -m src.dota2_mcp.diagnostics --bootstrap"
        )

    proc = subprocess.run(
        [str(exe), "-i", compiled_file_path, "--all"],
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
    """Extract .vmdl_c and parse animations, ACT_DOTA_* activities, and attach_* points."""
    try:
        local_file = extract_vpk_file_to_cache(model_path, CACHE_DIR)
    except Exception as exc:
        return {"ok": False, "model_path": model_path, "error": str(exc)}

    try:
        dump = _run_decompiler_block_dump(str(local_file))
    except Exception as exc:
        # Fallback: extract ASCII strings directly from the binary .vmdl_c if Decompiler is unavailable
        raw_bytes = local_file.read_bytes()
        dump = raw_bytes.decode("latin-1", errors="ignore")

    activities = sorted(set(re.findall(r"\bACT_DOTA_[A-Z0-9_]+\b", dump)))
    attachments = sorted(set(re.findall(r"\battach_[a-zA-Z0-9_]+\b", dump)))
    anim_names = sorted(
        set(
            re.findall(
                r'(?:m_sActivityName|m_name|m_activity|"@?[a-zA-Z0-9_]+(?:_anim|_attack|_idle|_run|_cast|_die)[a-zA-Z0-9_]*")',
                dump,
            )
        )
    )
    cleaned_anims = [a.strip('"') for a in anim_names if not a.startswith("m_")][:60]

    return {
        "ok": True,
        "model_path": model_path.removesuffix("_c"),
        "activities": activities,
        "attachments": attachments,
        "animation_Identifiers_sample": cleaned_anims,
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

    # Find control point numbers referenced in operators/initializers
    cp_matches = re.findall(
        r"(?:m_nControlPointNumber|m_nControlPoint|m_nFirstControlPoint|m_nScaleControlPoint|"
        r"m_nCP|control_point)\s*=\s*(\d+)",
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
