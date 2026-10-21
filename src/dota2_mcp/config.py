"""Configuration and automatic path discovery for Steam, Dota 2, and Workshop Tools."""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Optional

try:
    import vdf
except ImportError:
    vdf = None


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BIN_DIR = REPO_ROOT / "bin"
CACHE_DIR = REPO_ROOT / ".cache"
BUG_LOG_PATH = REPO_ROOT / "docs" / "BUG_LOG.md"


def _find_steam_path_windows() -> Optional[Path]:
    """Locate Steam installation directory on Windows via Registry or common paths."""
    if platform.system() != "Windows":
        return None

    try:
        import winreg

        for reg_path in (
            r"SOFTWARE\WOW6432Node\Valve\Steam",
            r"SOFTWARE\Valve\Steam",
        ):
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(hive, reg_path) as key:
                        val, _ = winreg.QueryValueEx(key, "InstallPath")
                        if val and Path(val).exists():
                            return Path(val)
                        val, _ = winreg.QueryValueEx(key, "SteamPath")
                        if val and Path(val).exists():
                            return Path(val)
                except OSError:
                    continue
    except ImportError:
        pass

    common_steam_paths = [
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"C:\Program Files\Steam"),
        Path(r"D:\Steam"),
        Path(r"E:\Steam"),
    ]
    for p in common_steam_paths:
        if p.exists():
            return p
    return None


def find_dota2_root() -> Optional[Path]:
    """Auto-discover 'dota 2 beta' root folder via DOTA2_PATH env, Steam libraryfolders.vdf, or common paths."""
    env_path = os.environ.get("DOTA2_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    steam_dir = _find_steam_path_windows()
    candidate_libs: list[Path] = []

    if steam_dir:
        candidate_libs.append(steam_dir)
        lib_vdf = steam_dir / "steamapps" / "libraryfolders.vdf"
        if lib_vdf.exists() and vdf is not None:
            try:
                with open(lib_vdf, "r", encoding="utf-8", errors="replace") as f:
                    data = vdf.load(f)
                folders = data.get("libraryfolders", {})
                for _, entry in folders.items():
                    if isinstance(entry, dict) and "path" in entry:
                        candidate_libs.append(Path(entry["path"]))
                    elif isinstance(entry, str):
                        candidate_libs.append(Path(entry))
            except Exception:
                pass

    # Fallback drive scan on Windows
    if platform.system() == "Windows":
        for drive in ("C", "D", "E", "F", "G"):
            candidate_libs.extend(
                [
                    Path(f"{drive}:\\SteamLibrary"),
                    Path(f"{drive}:\\Steam"),
                    Path(f"{drive}:\\Program Files (x86)\\Steam"),
                    Path(f"{drive}:\\Games\\Steam"),
                ]
            )
    elif platform.system() == "Darwin":
        mac_steam = Path.home() / "Library/Application Support/Steam"
        if mac_steam.exists():
            candidate_libs.append(mac_steam)

    for lib in candidate_libs:
        dota_dir = lib / "steamapps" / "common" / "dota 2 beta"
        if dota_dir.exists() and (dota_dir / "game").exists():
            return dota_dir

    return None


class DotaConfig:
    """Resolved paths to Dota 2 files and Workshop Tools binaries."""

    def __init__(self, dota_root: Optional[Path] = None) -> None:
        self.dota_root: Optional[Path] = dota_root or find_dota2_root()

    @property
    def is_valid(self) -> bool:
        return self.dota_root is not None and self.dota_root.exists()

    @property
    def game_dir(self) -> Optional[Path]:
        return self.dota_root / "game" if self.dota_root else None

    @property
    def content_dir(self) -> Optional[Path]:
        return self.dota_root / "content" if self.dota_root else None

    @property
    def game_addons_dir(self) -> Optional[Path]:
        return self.game_dir / "dota_addons" if self.game_dir else None

    @property
    def content_addons_dir(self) -> Optional[Path]:
        return self.content_dir / "dota_addons" if self.content_dir else None

    @property
    def pak01_dir_vpk(self) -> Optional[Path]:
        return self.game_dir / "dota" / "pak01_dir.vpk" if self.game_dir else None

    @property
    def win64_bin_dir(self) -> Optional[Path]:
        return self.game_dir / "bin" / "win64" if self.game_dir else None

    @property
    def dmxconvert_exe(self) -> Optional[Path]:
        return self.win64_bin_dir / "dmxconvert.exe" if self.win64_bin_dir else None

    @property
    def resourcecompiler_exe(self) -> Optional[Path]:
        return self.win64_bin_dir / "resourcecompiler.exe" if self.win64_bin_dir else None

    @property
    def decompiler_exe(self) -> Path:
        exe_name = "Source2Viewer-CLI.exe" if (BIN_DIR / "Source2Viewer-CLI.exe").exists() else "Decompiler.exe"
        return BIN_DIR / exe_name

    def summary(self) -> dict:
        return {
            "os": platform.system(),
            "dota_root": str(self.dota_root) if self.dota_root else None,
            "pak01_dir_vpk_exists": bool(self.pak01_dir_vpk and self.pak01_dir_vpk.exists()),
            "dmxconvert_exists": bool(self.dmxconvert_exe and self.dmxconvert_exe.exists()),
            "resourcecompiler_exists": bool(
                self.resourcecompiler_exe and self.resourcecompiler_exe.exists()
            ),
            "decompiler_exists": self.decompiler_exe.exists(),
            "decompiler_path": str(self.decompiler_exe),
        }


CONFIG = DotaConfig()
