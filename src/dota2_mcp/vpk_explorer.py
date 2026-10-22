"""Module 1: Search Dota 2 assets, sound events, and extract base KeyValues definitions from pak01_dir.vpk."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Optional

try:
    import vpk
except ImportError:
    vpk = None

try:
    import vdf
except ImportError:
    vdf = None

from .config import CACHE_DIR, CONFIG


_VPK_HANDLE: Optional[Any] = None
_VPK_FILE_LIST: Optional[list[str]] = None

ASSET_TYPE_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "model": (".vmdl_c", ".vmdl"),
    "particle": (".vpcf_c", ".vpcf"),
    "sound": (".vsnd_c", ".vsndevts_c", ".vsnd", ".vsndevts"),
    "material": (".vmat_c", ".vmat"),
    "panorama": (".vxml_c", ".vcss_c", ".vjs_c", ".png", ".vtex_c", ".vsvg_c"),
    "script": (".txt", ".kv", ".lua"),
    "all": (),
}

BASE_KV_FILES: dict[str, str] = {
    "hero": "scripts/npc/npc_heroes.txt",
    "ability": "scripts/npc/npc_abilities.txt",
    "unit": "scripts/npc/npc_units.txt",
    "item": "scripts/npc/items.txt",
}


def _get_vpk() -> Any:
    global _VPK_HANDLE, _VPK_FILE_LIST
    if vpk is None:
        raise RuntimeError("Python library 'vpk' is not installed. Run: pip install vpk")
    if not CONFIG.pak01_dir_vpk or not CONFIG.pak01_dir_vpk.exists():
        raise FileNotFoundError(
            f"Dota 2 pak01_dir.vpk not found at {CONFIG.pak01_dir_vpk}. "
            "Set DOTA2_PATH environment variable if Dota 2 is in a custom location."
        )
    if _VPK_HANDLE is None:
        _VPK_HANDLE = vpk.open(str(CONFIG.pak01_dir_vpk))
        _VPK_FILE_LIST = list(_VPK_HANDLE)
    return _VPK_HANDLE


def strip_compiled_suffix(path_str: str) -> str:
    """Convert compiled VPK path (e.g. models/heroes/pudge/pudge.vmdl_c) to engine path (.vmdl)."""
    if path_str.endswith("_c"):
        return path_str[:-2]
    return path_str


def search_dota_assets(query: str, asset_type: str = "all", limit: int = 25) -> dict[str, Any]:
    """Search pak01_dir.vpk for asset paths matching all tokens in query."""
    try:
        _get_vpk()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    assert _VPK_FILE_LIST is not None
    tokens = [t.lower() for t in query.strip().replace("\\", "/").split() if t]
    allowed_exts = ASSET_TYPE_EXTENSIONS.get(asset_type.lower(), ())

    matches: list[dict[str, str]] = []
    for raw_path in _VPK_FILE_LIST:
        lower_path = raw_path.lower()
        if allowed_exts and not lower_path.endswith(allowed_exts):
            continue
        if all(tok in lower_path for tok in tokens):
            matches.append(
                {
                    "engine_path": strip_compiled_suffix(raw_path),
                    "vpk_path": raw_path,
                }
            )
            if len(matches) >= max(1, min(limit, 100)):
                break

    return {
        "ok": True,
        "query": query,
        "asset_type": asset_type,
        "count": len(matches),
        "results": matches,
    }


def search_sound_events(
    query: str, file_filter: str = "", limit: int = 30
) -> dict[str, Any]:
    """Search inside Dota 2 .vsndevts_c files for exact Sound Event names (e.g. 'Hero_Pudge.Attack') to use in EmitSoundOn."""
    try:
        pak = _get_vpk()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    assert _VPK_FILE_LIST is not None
    tokens = [t.lower() for t in query.strip().split() if t]
    flt_lower = file_filter.strip().lower()

    vsndevts_files = [
        f
        for f in _VPK_FILE_LIST
        if f.startswith("soundevents/") and f.endswith(".vsndevts_c")
    ]
    if flt_lower:
        vsndevts_files = [f for f in vsndevts_files if flt_lower in f.lower()]
    else:
        # Prioritize files whose path matches any token in query
        vsndevts_files.sort(
            key=lambda p: 0 if any(tok in p.lower() for tok in tokens) else 1
        )

    # Verified against Source2Viewer-CLI KV3 DATA block in game_sounds_pudge.vsndevts_c:
    # Top-level entries inside DATA look like: Hero_Pudge.Attack = \n\t{
    event_header_re = re.compile(
        r"^\t([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)\s*=\s*$", re.MULTILINE
    )
    ascii_event_re = re.compile(r"\b([A-Za-z0-9_]{2,32}\.[A-Za-z0-9_.]{2,64})\b")

    results: list[dict[str, str]] = []
    seen_events: set[str] = set()
    max_results = max(1, min(limit, 100))

    for vpath in vsndevts_files[:60]:
        engine_vsndevts = strip_compiled_suffix(vpath)
        found_in_file: list[str] = []

        if CONFIG.decompiler_exe.exists():
            try:
                local_f = extract_vpk_file_to_cache(vpath, CACHE_DIR)
                proc = subprocess.run(
                    [str(CONFIG.decompiler_exe), "-i", str(local_f), "-b", "DATA"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=15,
                )
                if proc.stdout:
                    found_in_file = event_header_re.findall(proc.stdout)
            except Exception:
                pass

        if not found_in_file:
            try:
                raw_bytes = pak.get_file(vpath).read()
                text_latin = raw_bytes.decode("latin-1", errors="ignore")
                found_in_file = [
                    c
                    for c in ascii_event_re.findall(text_latin)
                    if not c.endswith((".vsnd", ".wav", ".mp3", ".vsndevts"))
                ]
            except Exception:
                continue

        for ev_name in found_in_file:
            if ev_name in seen_events:
                continue
            ev_lower = ev_name.lower()
            if all(
                tok in ev_lower or tok in engine_vsndevts.lower() for tok in tokens
            ):
                seen_events.add(ev_name)
                results.append(
                    {
                        "sound_event_name": ev_name,
                        "soundevents_file": engine_vsndevts,
                    }
                )
                if len(results) >= max_results:
                    break
        if len(results) >= max_results:
            break

    return {
        "ok": True,
        "query": query,
        "count": len(results),
        "results": results,
    }


def asset_exists_in_vpk_or_addon(engine_path: str, addon_name: Optional[str] = None) -> bool:
    """Verify whether an asset (.vmdl, .vpcf, .vsndevts, etc.) exists in VPK or addon folders."""
    norm = engine_path.strip().replace("\\", "/").lstrip("/")
    compiled_norm = norm if norm.endswith("_c") else f"{norm}_c"

    if addon_name and CONFIG.content_addons_dir and CONFIG.game_addons_dir:
        for base in (
            CONFIG.content_addons_dir / addon_name,
            CONFIG.game_addons_dir / addon_name,
        ):
            if (base / norm).exists() or (base / compiled_norm).exists():
                return True

    try:
        _get_vpk()
        assert _VPK_HANDLE is not None
        return (norm in _VPK_HANDLE) or (compiled_norm in _VPK_HANDLE)
    except Exception:
        return False


def extract_vpk_file_to_cache(vpk_or_engine_path: str, dest_dir: Path) -> Path:
    """Extract a single file from pak01_dir.vpk into a local cache folder."""
    pak = _get_vpk()
    norm = vpk_or_engine_path.strip().replace("\\", "/").lstrip("/")
    candidates = [norm]
    if not norm.endswith("_c"):
        candidates.insert(0, f"{norm}_c")

    for cand in candidates:
        if cand in pak:
            dest_path = dest_dir / cand
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            pak.get_file(cand).save(str(dest_path))
            return dest_path

    raise FileNotFoundError(f"Asset '{vpk_or_engine_path}' not found inside pak01_dir.vpk")


def _load_vpk_kv_dict(pak: Any, kv_rel_path: str) -> dict[str, Any]:
    """Read and parse a KeyValues file from pak01_dir.vpk or local game/dota fallback."""
    if kv_rel_path in pak:
        raw_bytes = pak.get_file(kv_rel_path).read()
        raw_text = raw_bytes.decode("utf-8", errors="replace")
    else:
        local_kv = CONFIG.game_dir / "dota" / kv_rel_path if CONFIG.game_dir else None
        if local_kv and local_kv.exists():
            raw_text = local_kv.read_text(encoding="utf-8", errors="replace")
        else:
            return {}

    # Valve KV files in Dota 7.41+ occasionally put a scalar value on the next line after its key
    # (e.g. "default_attack"\n\t"" in npc_abilities.txt or "ItemRequirements"\n\t\t"" in items.txt),
    # which python-vdf rejects with 'expected openning bracket'. Collapse multiline key-value scalars.
    # items.txt uses CRLF line endings: normalize first, otherwise '$' never matches before '\r'.
    cleaned_text = re.sub(
        r'^([ \t]*"[^"\r\n]*")[ \t]*\n[ \t]*("[^"\r\n]*")[ \t]*(?://.*)?$',
        r"\1\t\2",
        raw_text.replace("\r\n", "\n"),
        flags=re.MULTILINE,
    )
    try:
        parsed = vdf.loads(cleaned_text)
    except Exception:
        return {}
    root_dict = next(iter(parsed.values())) if parsed else {}
    return root_dict if isinstance(root_dict, dict) else {}


def _extract_abilities_from_hero_kv(hf_dict: dict[str, Any]) -> dict[str, Any]:
    """Extract ability definitions from a 7.41+ hero KV file (either top-level or nested under Hero.AbilityDefinitions)."""
    extracted: dict[str, Any] = {}
    for k, v in hf_dict.items():
        if not isinstance(v, dict):
            continue
        if k.startswith("npc_dota_hero_"):
            ab_defs = v.get("AbilityDefinitions")
            if isinstance(ab_defs, dict):
                for ab_name, ab_val in ab_defs.items():
                    if isinstance(ab_val, dict):
                        extracted[ab_name] = ab_val
        else:
            extracted[k] = v
    return extracted


def get_base_dota_definition(category: str, name: str) -> dict[str, Any]:
    """Read standard hero, ability, unit, or item definition from pak01_dir.vpk (supports 7.41+ split hero/ability files)."""
    cat = category.lower().strip()
    if cat not in BASE_KV_FILES:
        return {
            "ok": False,
            "error": f"Unknown category '{category}'. Valid: {list(BASE_KV_FILES.keys())}",
        }
    if vdf is None:
        return {"ok": False, "error": "Python library 'vdf' is not installed."}

    kv_rel_path = BASE_KV_FILES[cat]
    try:
        pak = _get_vpk()
        root_dict = _load_vpk_kv_dict(pak, kv_rel_path)

        # In modern Dota 2 (7.33 - 7.41+), both heroes and hero abilities live in scripts/npc/heroes/npc_dota_hero_*.txt
        if cat in ("ability", "hero") and name not in root_dict:
            assert _VPK_FILE_LIST is not None
            if cat == "hero":
                hero_token = name.removeprefix("npc_dota_hero_").lower()
            else:
                hero_token = name.split("_")[0].lower() if "_" in name else ""

            hero_files = [
                f
                for f in _VPK_FILE_LIST
                if f.startswith("scripts/npc/heroes/") and f.endswith(".txt")
            ]
            hero_files.sort(key=lambda p: 0 if hero_token and hero_token in p else 1)
            for hf in hero_files:
                hf_dict = _load_vpk_kv_dict(pak, hf)
                search_space = (
                    hf_dict
                    if cat == "hero"
                    else _extract_abilities_from_hero_kv(hf_dict)
                )
                if name in search_space:
                    return {
                        "ok": True,
                        "category": cat,
                        "source_file": hf,
                        "name": name,
                        "definition": search_space[name],
                    }
                root_dict.update(search_space)

        # Exact match
        if name in root_dict:
            return {
                "ok": True,
                "category": cat,
                "source_file": kv_rel_path,
                "name": name,
                "definition": root_dict[name],
            }

        # Case-insensitive or substring match
        name_lower = name.lower()
        similar_keys = [
            k
            for k in root_dict.keys()
            if isinstance(k, str) and name_lower in k.lower()
        ]
        if len(similar_keys) == 1:
            matched_key = similar_keys[0]
            return {
                "ok": True,
                "category": cat,
                "source_file": kv_rel_path,
                "name": matched_key,
                "definition": root_dict[matched_key],
            }

        return {
            "ok": False,
            "error": f"Entry '{name}' not found in {kv_rel_path} (or scripts/npc/heroes/*.txt).",
            "similar_names": similar_keys[:30],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
