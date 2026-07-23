"""Diagnose-Datensammler für den Diagnose-Tab (#23).

GUI-frei und defensiv: jede Funktion fängt Fehler ab und wirft NIE, damit der
Diagnose-Tab auch bei fehlender Instanz, fehlenden Dateien oder kaputter Config
nutzbar bleibt. Greift nur lesend auf bestehende Datenquellen zu.
"""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path

from anvil.core.base_dir import anvil_base_paths

from anvil.version import APP_VERSION
from anvil.core.subprocess_env import is_flatpak, is_appimage
from anvil.core.translator import tr

# Pfad-Keys einer Instanz, die geprüft werden (echte .anvil.ini-Keys)
_PATH_KEYS = (
    "game_path",
    "path_mods_directory",
    "path_downloads_directory",
    "path_overwrite_directory",
    "path_profiles_directory",
)

_MANIFEST_NAME = ".deploy_manifest.json"


# ── Systeminfo ────────────────────────────────────────────────────────

def _distro_name() -> str:
    try:
        data: dict[str, str] = {}
        with open("/etc/os-release", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.rstrip("\n").split("=", 1)
                    data[k] = v.strip().strip('"')
        return data.get("PRETTY_NAME") or data.get("NAME") or ""
    except OSError:
        return ""


def _memory_info() -> str:
    try:
        total = avail = 0
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail = int(line.split()[1])
        if total:
            return f"{avail / 1024 / 1024:.1f} / {total / 1024 / 1024:.1f} GiB"
    except (OSError, ValueError, IndexError):
        pass
    return ""


def _run_mode() -> str:
    try:
        if is_flatpak():
            return "Flatpak"
        if is_appimage():
            return "AppImage"
    except OSError:
        pass
    if getattr(sys, "frozen", False):
        return "PyInstaller"
    return "Source"


def collect_system_info() -> dict:
    """Sammelt System-/Laufzeitinfo. Wirft nie."""
    info: dict[str, str] = {}
    try:
        info["os"] = platform.platform()
    except Exception:  # noqa: BLE001 — platform darf den Tab nicht killen
        info["os"] = ""
    info["distro"] = _distro_name()
    try:
        info["kernel"] = platform.release()
    except Exception:  # noqa: BLE001
        info["kernel"] = ""
    try:
        info["python"] = platform.python_version()
    except Exception:  # noqa: BLE001
        info["python"] = ""
    try:
        import PySide6
        from PySide6.QtCore import qVersion
        info["qt"] = f"PySide6 {PySide6.__version__} / Qt {qVersion()}"
    except Exception:  # noqa: BLE001
        info["qt"] = ""
    info["app_version"] = APP_VERSION
    info["run_mode"] = _run_mode()
    info["desktop"] = os.environ.get("XDG_CURRENT_DESKTOP", "")
    info["session"] = os.environ.get("XDG_SESSION_TYPE", "")
    info["memory"] = _memory_info()
    return info


# ── Pfad-Checks ───────────────────────────────────────────────────────

def collect_path_checks(idata: dict, instance_path) -> list[dict]:
    """Prüft die Instanz-Pfade. Liefert pro Pfad {key, path, exists, writable}."""
    checks: list[dict] = []
    if not idata:
        return checks
    ipath = str(instance_path) if instance_path else None

    def _resolve(val: str) -> str:
        if not val:
            return ""
        if "%INSTANCE_DIR%" in val:
            if ipath is None:
                return val  # nicht auflösbar
            return val.replace("%INSTANCE_DIR%", ipath)
        return val

    for key in _PATH_KEYS:
        path = _resolve(idata.get(key, ""))
        exists = writable = False
        if path:
            try:
                exists = Path(path).exists()
                writable = bool(exists and os.access(path, os.W_OK))
            except OSError:
                pass
        checks.append({"key": key, "path": path, "exists": exists, "writable": writable})
    return checks


# ── Problemerkennung ──────────────────────────────────────────────────

def detect_problems(idata: dict, sysinfo: dict, path_checks: list[dict]) -> list[dict]:
    """Heuristische Problemerkennung. Liefert {severity, message}. Wirft nie."""
    problems: list[dict] = []
    if not idata:
        problems.append({"severity": "info", "message": tr("label.diag_problem_no_instance")})
        return problems

    label_map = {
        "game_path": tr("settings.path_managed_game"),
        "path_mods_directory": tr("settings.path_mods"),
        "path_downloads_directory": tr("settings.path_downloads"),
        "path_overwrite_directory": tr("settings.path_overwrite"),
        "path_profiles_directory": tr("settings.path_profiles"),
    }
    for chk in path_checks:
        label = label_map.get(chk["key"], chk["key"])
        if not chk["path"]:
            continue
        if chk["key"] == "game_path" and not chk["exists"]:
            problems.append({"severity": "error",
                             "message": tr("label.diag_problem_game_path", path=chk["path"])})
        elif not chk["exists"]:
            problems.append({"severity": "warning",
                             "message": tr("label.diag_problem_dir_missing", label=label)})
        elif not chk["writable"]:
            problems.append({"severity": "warning",
                             "message": tr("label.diag_problem_dir_not_writable", label=label)})

    mode = sysinfo.get("run_mode", "")
    if mode in ("Flatpak", "AppImage"):
        problems.append({"severity": "info",
                         "message": tr("label.diag_problem_sandbox", mode=mode)})
    return problems


# ── Deploy-Status (Symlink-Prüfung aus dem Manifest) ──────────────────

def collect_deploy_status(instance_path) -> dict:
    """Liest das Deploy-Manifest und prüft die Symlinks. Wirft nie.

    Liefert {manifest: bool, total, broken, missing, deployed_at}.
    """
    if instance_path is None:
        return {"manifest": False}
    manifest_path = Path(instance_path) / _MANIFEST_NAME
    if not manifest_path.is_file():
        return {"manifest": False}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"manifest": False}

    game_path = data.get("game_path", "")
    entries = data.get("symlinks", []) or []
    broken = missing = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        base = entry.get("deploy_base") or game_path
        link = entry.get("link", "")
        if not base or not link:
            continue
        lp = Path(base) / link
        # Das Manifest enthält Symlinks (type "symlink"/"dir_symlink") UND kopierte
        # Dateien (type "copy"/"shim_copy"). Nur echte Symlinks können "broken" sein;
        # Kopien werden nur auf Existenz geprüft.
        try:
            if entry.get("type") in ("symlink", "dir_symlink"):
                if lp.is_symlink():
                    if not lp.exists():
                        broken += 1
                else:
                    missing += 1
            else:
                if not lp.exists():
                    missing += 1
        except OSError:
            broken += 1
    return {
        "manifest": True,
        "total": len(entries),
        "broken": broken,
        "missing": missing,
        "deployed_at": data.get("deployed_at", ""),
    }


# ── Log-Quellen + Tail ────────────────────────────────────────────────

def log_sources() -> list[dict]:
    """Verfügbare Logdateien: activity.log (+ Backups) und ggf. debug.log."""
    sources: list[dict] = []
    log_dir = anvil_base_paths().logs
    active = log_dir / "activity.log"
    if active.is_file():
        sources.append({"label": "activity.log", "path": str(active)})
    for i in range(1, 5):
        bak = log_dir / f"activity.log.{i}"
        if bak.is_file():
            sources.append({"label": f"activity.log.{i}", "path": str(bak)})
    # debug.log liegt am Projektroot (nur Quellcode-Start über restart.sh)
    try:
        project_root = Path(__file__).resolve().parents[2]
        dbg = project_root / "debug.log"
        if dbg.is_file():
            sources.append({"label": "debug.log", "path": str(dbg)})
    except (OSError, IndexError):
        pass
    return sources


def read_log_tail(path, max_lines: int = 2000) -> list[str]:
    """Letzte max_lines Zeilen einer Logdatei. Wirft nie, liefert [] bei Fehler."""
    if not path:
        return []
    try:
        p = Path(path)
        if not p.is_file():
            return []
        with p.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return [ln.rstrip("\n") for ln in lines[-max_lines:]]
    except (OSError, ValueError, TypeError):
        return []


# ── Report ────────────────────────────────────────────────────────────

def build_report(sysinfo: dict, path_checks: list[dict], problems: list[dict],
                 deploy_status: dict | None = None,
                 conflicts: list[dict] | None = None) -> str:
    """Baut einen Klartext-Support-Report (ohne Credentials/API-Keys)."""
    lines: list[str] = ["=== Anvil Organizer — Diagnose-Report ===", ""]

    lines.append("[System]")
    for k in ("app_version", "os", "distro", "kernel", "python", "qt",
              "run_mode", "desktop", "session", "memory"):
        v = sysinfo.get(k, "")
        if v:
            lines.append(f"{k}: {v}")
    lines.append("")

    lines.append("[Pfade]")
    for chk in path_checks:
        if chk["exists"] and chk["writable"]:
            status = "OK"
        elif chk["exists"]:
            status = "nicht beschreibbar"
        else:
            status = "fehlt"
        lines.append(f"{chk['key']}: {chk['path'] or '—'} [{status}]")
    lines.append("")

    if deploy_status is not None:
        lines.append("[Deploy]")
        if deploy_status.get("manifest"):
            lines.append(
                f"{deploy_status.get('total', 0)} Links, "
                f"{deploy_status.get('broken', 0)} defekt, "
                f"{deploy_status.get('missing', 0)} fehlend"
            )
        else:
            lines.append("kein Deploy-Manifest")
        lines.append("")

    lines.append("[Probleme]")
    if problems:
        for p in problems:
            lines.append(f"[{p['severity']}] {p['message']}")
    else:
        lines.append("keine")
    lines.append("")

    if conflicts is not None:
        lines.append(f"[Konflikte] {len(conflicts)}")
        for c in conflicts[:50]:
            lines.append(f"  {c.get('file', '')}  -> {c.get('winner', '')}")

    return "\n".join(lines)
