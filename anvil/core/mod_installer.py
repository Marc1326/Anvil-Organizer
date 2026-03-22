"""Extract archives and install them as mods.

Supported formats:

- ZIP  — ``zipfile`` (stdlib, always available)
- RAR  — ``unrar`` CLI tool
- 7-Zip — ``7z`` CLI tool (p7zip)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from anvil.core.mod_metadata import create_default_meta_ini

# Type hint only - avoid circular import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from anvil.plugins.framework_mod import FrameworkMod

SUPPORTED_EXTENSIONS = {".zip", ".rar", ".7z"}


class ModInstaller:
    """Extract archives and install them into an instance's ``.mods/`` folder."""

    def __init__(self, instance_path: Path, flatten: bool = True) -> None:
        self.instance_path = instance_path
        self.mods_path = instance_path / ".mods"
        self._flatten = flatten

    # ── Public API ─────────────────────────────────────────────────────

    # MO2-style regex for Nexus filenames (ported from nexusinterface.cpp:332)
    # Group 1: mod name, Group 2: optional version, Group 3: Nexus mod ID
    _NEXUS_RE = re.compile(
        r'^([a-zA-Z0-9_\'".\-() ]*?)'       # mod name
        r'(?:[-_ ][VvRr]+[0-9]+(?:[._\-][0-9]+){0,2}[ab]?)?'  # optional version
        r'-([1-9][0-9]+)?-.*'                 # Nexus ID + rest
        r'\.(zip|rar|7z)$',
        re.IGNORECASE,
    )
    _SIMPLE_RE = re.compile(r'^[^a-zA-Z]*([a-zA-Z_ ]+)')

    # Ordner die NICHT hochgezogen werden dürfen — sie sind selbst Game-Root-Ordner
    _GAME_FOLDERS = {
        "archive", "bin", "r6", "red4ext", "mods",
        "engine", "data", "pc", "dlc",
        "tools", "lml", "content",
    }

    @staticmethod
    def suggest_name(archive_path: Path) -> str:
        """Derive a clean mod name from a Nexus-style archive filename.

        Ported from MO2's ``NexusInterface::interpretNexusFileName()``.
        """
        filename = archive_path.name
        m = ModInstaller._NEXUS_RE.match(filename)
        if m:
            name = m.group(1)
        else:
            m2 = ModInstaller._SIMPLE_RE.match(archive_path.stem)
            name = m2.group(1) if m2 else archive_path.stem
        name = name.replace("_", " ").strip(" -.")
        return ModInstaller._sanitize_name(name) if name else "Unnamed Mod"

    def suggest_names(self, archive_path: Path) -> tuple[str, list[str]]:
        """Collect name variants for the Quick-Install combo box.

        Mirrors MO2's ``GuessedValue<QString>`` — collects multiple guesses
        at different quality levels, returns the best + all variants.

        Returns:
            ``(best_name, [variant, ...])`` — *best_name* is pre-selected,
            *variants* populates the combo box dropdown.
        """
        import configparser

        variants: list[str] = []
        seen: set[str] = set()

        def _add(name: str) -> None:
            if name and name not in seen:
                variants.append(name)
                seen.add(name)

        # GUESS_GOOD: cleaned Nexus name (highest auto-guess quality)
        best = self.suggest_name(archive_path)
        _add(best)

        # GUESS_META: name from .meta file if available
        meta_path = Path(str(archive_path) + ".meta")
        if meta_path.is_file():
            cp = configparser.ConfigParser()
            try:
                cp.read(str(meta_path), encoding="utf-8")
                meta_name = cp.get("General", "modName", fallback="")
                if meta_name.strip():
                    _add(meta_name.strip())
                # Also the HTML-stripped "name" field
                raw_name = cp.get("General", "name", fallback="")
                if raw_name.strip():
                    _add(raw_name.strip())
            except Exception:
                pass

        # Similar mods already installed (same base prefix)
        if self.mods_path.is_dir():
            # Extract base prefix: e.g. "Zenitex Core Dependency" from
            # "Zenitex Core Dependency - Verdant Set"
            base = best.split(" - ")[0].strip() if " - " in best else best
            for mod_dir in sorted(self.mods_path.iterdir()):
                if mod_dir.is_dir() and mod_dir.name.startswith(base):
                    _add(mod_dir.name)

        # GUESS_FALLBACK: full archive stem (with Nexus IDs)
        _add(archive_path.stem)

        return best, variants

    def install_from_archive(
        self,
        archive_path: Path,
        mod_name: str | None = None,
    ) -> Path | None:
        """Extract *archive_path* and install as a mod.

        Args:
            archive_path: Path to a ``.zip``, ``.rar``, or ``.7z`` file.
            mod_name: Display / folder name.  When given explicitly (from the
                      Quick-Install dialog), no auto-numbering is applied.
                      Derived from filename if *None*.

        Returns:
            Path to the installed mod folder, or *None* on failure.
        """
        if not archive_path.is_file():
            print(
                f"mod_installer: file not found: {archive_path}",
                file=sys.stderr,
            )
            return None

        # 1. Determine mod name
        if mod_name:
            folder_name = mod_name  # caller handled duplicates
        else:
            base = self._sanitize_name(archive_path.stem)
            folder_name = self._unique_name(base)

        # 2. Extract into a temporary directory
        tmp = Path(tempfile.mkdtemp(prefix="anvil_install_"))
        try:
            if not self._extract(archive_path, tmp):
                return None

            # 3. Flatten single-subfolder archives (skip for games like Witcher 3)
            if self._flatten:
                self._flatten_single_subfolder(tmp)

            # 4. Check that we actually got files
            if not any(tmp.iterdir()):
                print(
                    f"mod_installer: archive is empty: {archive_path}",
                    file=sys.stderr,
                )
                return None

            # 5. Move to .mods/<folder_name>
            self.mods_path.mkdir(parents=True, exist_ok=True)
            dest = self.mods_path / folder_name
            shutil.move(str(tmp), str(dest))

            # 6. Create meta.ini
            display = mod_name or folder_name
            create_default_meta_ini(dest, display)

            return dest

        except OSError as exc:
            print(
                f"mod_installer: failed to install {archive_path}: {exc}",
                file=sys.stderr,
            )
            return None
        finally:
            # Clean up temp dir if it still exists (move failed)
            if tmp.is_dir():
                shutil.rmtree(tmp, ignore_errors=True)

    def extract_to_temp(self, archive_path: Path) -> Path | None:
        """Extract archive to a temporary directory.

        Returns:
            Path to temp directory, or None on failure.
            Caller must clean up the temp directory!
        """
        if archive_path.is_dir():
            print(f"[extract_to_temp] input is DIRECTORY: {archive_path}", flush=True)
            tmp = Path(tempfile.mkdtemp(prefix="anvil_install_"))
            for item in archive_path.iterdir():
                dest = tmp / item.name
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            if not any(tmp.iterdir()):
                print(f"[extract_to_temp] dir is EMPTY → returning None", flush=True)
                shutil.rmtree(tmp, ignore_errors=True)
                return None
            print(f"[extract_to_temp] dir → temp={tmp}, items={[i.name for i in tmp.iterdir()]}", flush=True)
            return tmp

        if not archive_path.is_file():
            print(f"mod_installer: file not found: {archive_path}", file=sys.stderr)
            return None

        tmp = Path(tempfile.mkdtemp(prefix="anvil_install_"))
        if not self._extract(archive_path, tmp):
            shutil.rmtree(tmp, ignore_errors=True)
            return None

        if self._flatten:
            self._flatten_single_subfolder(tmp)

        if not any(tmp.iterdir()):
            print(f"mod_installer: archive is empty: {archive_path}", file=sys.stderr)
            shutil.rmtree(tmp, ignore_errors=True)
            return None

        return tmp

    def install_from_extracted(self, temp_dir: Path, mod_name: str) -> Path | None:
        """Install mod from an already-extracted temp directory.

        Args:
            temp_dir: Path to extracted files (will be moved, not copied).
            mod_name: Display / folder name for the mod.

        Returns:
            Path to the installed mod folder, or None on failure.
        """
        try:
            self.mods_path.mkdir(parents=True, exist_ok=True)
            dest = self.mods_path / mod_name
            shutil.move(str(temp_dir), str(dest))
            create_default_meta_ini(dest, mod_name)
            return dest
        except OSError as exc:
            print(f"mod_installer: failed to install: {exc}", file=sys.stderr)
            return None

    def install_framework(
        self,
        temp_dir: Path,
        framework: "FrameworkMod",
        game_path: Path,
    ) -> dict | None:
        """Install a framework mod into the game directory.

        Args:
            temp_dir: Path to extracted framework files.
            framework: FrameworkMod with pattern and target info.
            game_path: Path to the game installation directory.

        Returns:
            Dict with installation info, or None on failure.
        """
        target_dir = game_path / framework.target if framework.target else game_path
        target_dir.mkdir(parents=True, exist_ok=True)

        # Find the actual directory containing the framework files.
        # Archives often wrap files in subdirectories (e.g. bin/ or
        # ModLoader/) that must be stripped when installing.
        install_root = self._find_install_root(temp_dir, framework.pattern)
        print(f"DEBUG install_framework: install_root={install_root}")

        installed_files: list[str] = []
        for src_item in install_root.rglob("*"):
            rel = src_item.relative_to(install_root)
            dest = target_dir / rel
            if src_item.is_dir():
                # Create all directories — including empty ones like lml/
                dest.mkdir(parents=True, exist_ok=True)
            elif src_item.is_file():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_item, dest)
                installed_files.append(str(dest.relative_to(game_path)))
        print(f"DEBUG install_framework: files={installed_files}")

        # Clean up temp dir
        shutil.rmtree(temp_dir, ignore_errors=True)

        return {
            "name": framework.name,
            "type": "framework",
            "target": framework.target,
            "files": installed_files,
            "status": "installed",
        }

    @staticmethod
    def _find_install_root(temp_dir: Path, patterns: list[str]) -> Path:
        """Find the directory containing the framework files.

        Archives often wrap framework files in a subdirectory:

        - ``ScriptHookRDR2.zip``: ``bin/ScriptHookRDR2.dll``
        - ``LML``: ``ModLoader/vfs.asi``, ``ModLoader/lml/``

        This method locates where the pattern files actually live and
        returns their parent directory as the install root.  Files are
        then copied relative to this root, effectively stripping the
        wrapper directory.

        Falls back to *temp_dir* itself if patterns match at the root.
        """
        for pat in patterns:
            pat_lower = pat.lower().rstrip("/")
            if not pat_lower:
                continue
            for item in temp_dir.rglob("*"):
                rel = item.relative_to(temp_dir)
                rel_str = str(rel).replace("\\", "/")
                rel_lower = rel_str.lower()
                idx = rel_lower.find(pat_lower)
                if idx >= 0:
                    print(f"DEBUG _find_install_root: pat={pat}, rel={rel_str}, idx={idx}")
                if idx < 0:
                    continue
                # Pattern at root level — no wrapper to strip
                if idx == 0:
                    return temp_dir
                # Pattern nested in wrapper dir — strip it
                prefix_str = rel_str[:idx].rstrip("/")
                if prefix_str:
                    result = temp_dir / prefix_str
                    print(f"DEBUG _find_install_root: result={result}")
                    return result
                print(f"DEBUG _find_install_root: result={temp_dir} (no prefix)")
                return temp_dir
        return temp_dir

    # ── Extraction ─────────────────────────────────────────────────────

    def _extract(self, archive: Path, dest: Path) -> bool:
        """Dispatch extraction based on file extension."""
        ext = archive.suffix.lower()
        if ext == ".zip":
            return self._extract_zip(archive, dest)
        if ext == ".rar":
            return self._extract_rar(archive, dest)
        if ext == ".7z":
            return self._extract_7z(archive, dest)
        print(
            f"mod_installer: unsupported format: {ext}",
            file=sys.stderr,
        )
        return False

    @staticmethod
    def _extract_zip(archive: Path, dest: Path) -> bool:
        try:
            real_dest = os.path.realpath(dest)
            with zipfile.ZipFile(archive, "r") as zf:
                for member in zf.infolist():
                    resolved = os.path.realpath(
                        os.path.join(real_dest, member.filename)
                    )
                    if not resolved.startswith(real_dest + os.sep) and resolved != real_dest:
                        print(
                            f"mod_installer: SECURITY — skipping zip entry "
                            f"with path traversal: {member.filename!r}",
                            file=sys.stderr,
                        )
                        continue
                    zf.extract(member, dest)
            return True
        except (zipfile.BadZipFile, OSError) as exc:
            print(
                f"mod_installer: failed to extract ZIP {archive}: {exc}",
                file=sys.stderr,
            )
            return False

    @staticmethod
    def _extract_rar(archive: Path, dest: Path) -> bool:
        if not shutil.which("unrar"):
            print(
                "mod_installer: 'unrar' not found — install it to extract RAR files",
                file=sys.stderr,
            )
            return False
        try:
            subprocess.run(
                ["unrar", "x", "-o+", "-y", str(archive), str(dest) + "/"],
                check=True,
                capture_output=True,
            )
            ModInstaller._validate_extracted_paths(dest, "RAR")
            return True
        except subprocess.CalledProcessError as exc:
            print(
                f"mod_installer: unrar failed: {exc.stderr.decode(errors='replace')}",
                file=sys.stderr,
            )
            return False

    @staticmethod
    def _extract_7z(archive: Path, dest: Path) -> bool:
        if not shutil.which("7z"):
            print(
                "mod_installer: '7z' not found — install p7zip to extract 7z files",
                file=sys.stderr,
            )
            return False
        try:
            subprocess.run(
                ["7z", "x", str(archive), f"-o{dest}", "-y"],
                check=True,
                capture_output=True,
            )
            ModInstaller._validate_extracted_paths(dest, "7z")
            return True
        except subprocess.CalledProcessError as exc:
            print(
                f"mod_installer: 7z failed: {exc.stderr.decode(errors='replace')}",
                file=sys.stderr,
            )
            return False

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _validate_extracted_paths(dest: Path, fmt: str) -> None:
        """Post-extraction validation: remove files outside target dir."""
        real_dest = os.path.realpath(dest)
        for root, dirs, files in os.walk(real_dest):
            for fname in files:
                fpath = os.path.join(root, fname)
                resolved = os.path.realpath(fpath)
                if not resolved.startswith(real_dest + os.sep) and resolved != real_dest:
                    print(
                        f"mod_installer: SECURITY — removing {fmt} entry "
                        f"with path traversal: {resolved!r}",
                        file=sys.stderr,
                    )
                    try:
                        os.remove(resolved)
                    except OSError:
                        pass

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Remove characters that are problematic in folder names."""
        # Replace problematic chars with underscore
        cleaned = re.sub(r'[<>:"/\\|?*]', "_", name)
        # Collapse multiple underscores / strip
        cleaned = re.sub(r"_+", "_", cleaned).strip(" _.")
        return cleaned or "Unnamed Mod"

    def _unique_name(self, base: str) -> str:
        """Return *base* if available, otherwise ``base (2)``, ``(3)``, etc."""
        if not (self.mods_path / base).exists():
            return base
        n = 2
        while (self.mods_path / f"{base} ({n})").exists():
            n += 1
        return f"{base} ({n})"

    @staticmethod
    def _flatten_single_subfolder(extract_dir: Path) -> None:
        """Wenn *extract_dir* genau einen Unterordner enthält, dessen Inhalt
        eine Ebene hochziehen — AUSSER der Ordner ist ein bekannter
        Game-Root-Ordner (z.B. ``bin``, ``r6``, ``archive``).
        """
        children = list(extract_dir.iterdir())
        if len(children) == 1 and children[0].is_dir():
            single = children[0]
            # Bekannte Game-Ordner NICHT flatten — sie gehoeren zur Mod-Struktur
            if single.name.lower() in ModInstaller._GAME_FOLDERS:
                print(f"mod_installer: skip flatten — '{single.name}' is a known game folder")
                return
            # Move everything from single/ up to extract_dir/
            for item in single.iterdir():
                shutil.move(str(item), str(extract_dir / item.name))
            single.rmdir()

    @staticmethod
    def check_tools() -> dict[str, bool]:
        """Check availability of extraction tools."""
        return {
            "zip": True,
            "rar": shutil.which("unrar") is not None,
            "7z": shutil.which("7z") is not None,
        }
