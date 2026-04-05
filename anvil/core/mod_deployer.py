"""Symlink-based mod deployment for Linux.

Deploys mods from ``.mods/`` into the game directory by creating
symbolic links.  A JSON manifest tracks all created links so they
can be cleanly removed (purged) afterwards.

Workflow::

    deployer = ModDeployer(instance_path, game_path)
    result   = deployer.deploy()   # before game start
    ...                             # play game
    result   = deployer.purge()    # after game ends

Safety rules:

- Real (non-symlink) game files are NEVER overwritten.
- Only symlinks pointing into ``.mods/`` are removed during purge.
- Empty directories created during deploy are tracked and cleaned up.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from anvil.core.mod_list_io import read_global_modlist, read_active_mods

if TYPE_CHECKING:
    from anvil.core.modindex import ModIndex

# Files inside mod folders that are metadata, not game content.
_SKIP_FILES = {"meta.ini", "codes.txt", "fomod_choices.json"}

# Directories inside mod folders that are installer metadata.
_SKIP_DIRS = {"fomod"}

# Extensions skipped ONLY in the mod root directory (not in subdirectories).
# Files in subdirectories (textures/, meshes/, etc.) are game content.
_SKIP_ROOT_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",  # Bilder
    ".txt", ".md", ".pdf", ".log", ".readme",           # Dokumentation
    ".db",                                               # Thumbs.db
}

# Extensions always deployed as symlinks even when BA2-packing is active.
_BA2_SYMLINK_EXTENSIONS = {
    ".esp", ".esm", ".esl",   # plugins
    ".dll", ".exe",            # script extenders / binaries
    ".ini", ".cfg", ".toml",   # config files
    ".ba2", ".bsa",            # existing archives
}


@dataclass
class DeployResult:
    """Result of a deploy or purge operation."""

    success: bool = True
    links_created: int = 0
    links_removed: int = 0
    files_copied: int = 0
    dirs_created: int = 0
    dirs_removed: int = 0
    skipped_real_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class ModDeployer:
    """Symlink-based mod deployer.

    Args:
        instance_path: Root of the game instance
            (e.g. ``~/.anvil-organizer/instances/Cyberpunk 2077/``).
        game_path: Path to the game installation directory
            (e.g. ``~/.local/share/Steam/steamapps/common/Cyberpunk 2077``).
    """

    MANIFEST_NAME = ".deploy_manifest.json"

    def __init__(
        self,
        instance_path: Path,
        game_path: Path,
        direct_install_patterns: list[str] | None = None,
        profile_name: str = "Default",
        data_path: str = "",
        nest_under_mod_name: bool = False,
        lml_path: str = "",
        multi_folder_routes: dict[str, str] | None = None,
        needs_ba2_packing: bool = False,
        copy_deploy_paths: list[str] | None = None,
        mod_index: ModIndex | None = None,
        redmod_path: str = "",
        separator_deploy_paths: dict[str, str] | None = None,
    ) -> None:
        self._instance_path = instance_path
        self._game_path = game_path
        self._data_path = data_path
        self._nest_under_mod_name = nest_under_mod_name
        self._lml_path = lml_path
        self._redmod_path = redmod_path
        self._multi_folder_routes = multi_folder_routes or {}
        self._mods_path = instance_path / ".mods"
        self._profiles_dir = instance_path / ".profiles"
        self._profile_path = self._profiles_dir / profile_name
        self._manifest_path = instance_path / self.MANIFEST_NAME
        self._direct_patterns = [p.lower() for p in (direct_install_patterns or [])]
        self._needs_ba2_packing = needs_ba2_packing
        self._copy_deploy_paths = [p.replace("\\", "/") for p in (copy_deploy_paths or [])]
        self._mod_index = mod_index
        self._separator_deploy_paths = separator_deploy_paths or {}

    def is_direct_install(self, mod_name: str) -> bool:
        """Return True if *mod_name* matches a direct-install pattern.

        Matching is case-insensitive and uses 'contains' logic.
        """
        lower = mod_name.lower()
        return any(pat in lower for pat in self._direct_patterns)

    # ── Public API ─────────────────────────────────────────────────────

    def is_deployed(self) -> bool:
        """Return True if a deploy manifest exists."""
        return self._manifest_path.is_file()

    def deploy(self) -> DeployResult:
        """Deploy all enabled mods as symlinks into the game directory.

        - Reads modlist.txt for enabled mods and priority order.
        - Iterates mods from lowest to highest priority (higher wins).
        - Creates symlinks for each mod file.
        - Skips real game files (never overwrites originals).
        - Saves a manifest for later cleanup.

        Returns:
            DeployResult with statistics and any errors.
        """
        result = DeployResult()

        # Purge old deployment first (clean slate)
        if self.is_deployed():
            purge_result = self.purge()
            if not purge_result.success:
                result.success = False
                result.errors.append(
                    "Failed to purge previous deployment: "
                    + "; ".join(purge_result.errors)
                )
                return result

        # Read global modlist for order + profile's active mods
        print(f"[DEPLOY] Profile: {self._profile_path}", flush=True)
        global_order = read_global_modlist(self._profiles_dir)
        active_mods = read_active_mods(self._profile_path)
        enabled_mods = [
            (name, idx) for idx, name in enumerate(global_order)
            if name in active_mods
        ]

        # Direct-install mods (frameworks) are ALWAYS deployed,
        # regardless of active_mods state — they live in the game root.
        print(f"[DEPLOY] direct_patterns: {self._direct_patterns}", flush=True)
        if self._direct_patterns:
            seen = {name for name, _ in enabled_mods}
            for idx, name in enumerate(global_order):
                if name not in seen and self.is_direct_install(name):
                    mod_dir = self._mods_path / name
                    if mod_dir.is_dir():
                        enabled_mods.append((name, idx))
                        seen.add(name)
                        print(f"[DEPLOY] +framework: {name}", flush=True)

        # Build mod → separator mapping using FULL global order
        # (not just enabled mods — inactive separators must be recognized)
        mod_to_separator: dict[str, str] = {}
        if self._separator_deploy_paths:
            current_sep = ""
            for name in global_order:
                if name.endswith("_separator"):
                    current_sep = name
                else:
                    mod_to_separator[name] = current_sep

        enabled_mods.reverse()
        print(f"[DEPLOY] Enabled mods: {len(enabled_mods)}", flush=True)
        print(f"[DEPLOY] Data path: {self._data_path or '(root)'}", flush=True)

        if not enabled_mods:
            result.errors.append("No enabled mods found.")
            return result

        # Track what we create
        symlinks: list[dict[str, str]] = []
        created_dirs: set[str] = set()

        # Process mods from lowest to highest priority.
        # Higher priority mods overwrite lower ones (replace symlink).
        for mod_name, _priority in enabled_mods:
            mod_dir = self._mods_path / mod_name

            if not mod_dir.is_dir():
                continue

            # Skip separators (they are organizational, not deployable)
            if mod_name.endswith("_separator"):
                continue

            # LML-Mod? (hat install.xml im Mod-Root) → Ordner-Symlink
            if self._lml_path and (mod_dir / "install.xml").is_file():
                lml_target = self._game_path / self._lml_path / mod_name
                lml_target.parent.mkdir(parents=True, exist_ok=True)

                if lml_target.is_symlink():
                    lml_target.unlink()
                elif lml_target.exists():
                    result.skipped_real_files.append(
                        str(lml_target.relative_to(self._game_path))
                    )
                    continue

                try:
                    lml_target.symlink_to(mod_dir)
                    result.links_created += 1
                    symlinks.append({
                        "link": str(Path(self._lml_path) / mod_name),
                        "target": str(mod_dir),
                        "mod": mod_name,
                        "type": "dir_symlink",
                    })
                except OSError as exc:
                    result.errors.append(f"lml symlink {mod_name}: {exc}")
                continue  # Keine Einzel-Dateien symlinken

            # REDmod-Erkennung (Pattern A + C):
            # Mods mit info.json werden als Ordner-Symlinks nach
            # game_root/<redmod_path>/<name>/ deployed.
            # Pattern B (mods/<name>/info.json) wird vom normalen
            # Einzel-Symlink-Code behandelt (mods/ Prefix ist im Mod).
            redmod_handled = False
            if self._redmod_path:
                # Pattern A: info.json direkt im Mod-Root
                # → gesamter Mod ist ein REDmod-Ordner
                if (mod_dir / "info.json").is_file():
                    redmod_target = (
                        self._game_path / self._redmod_path / mod_name
                    )
                    redmod_target.parent.mkdir(parents=True, exist_ok=True)

                    if redmod_target.is_symlink():
                        redmod_target.unlink()
                    elif redmod_target.exists():
                        result.skipped_real_files.append(
                            str(redmod_target.relative_to(self._game_path))
                        )
                        redmod_handled = True
                        continue

                    try:
                        redmod_target.symlink_to(mod_dir)
                        result.links_created += 1
                        symlinks.append({
                            "link": str(
                                Path(self._redmod_path) / mod_name
                            ),
                            "target": str(mod_dir),
                            "mod": mod_name,
                            "type": "dir_symlink",
                        })
                        print(
                            f"[DEPLOY] REDmod Pattern A: "
                            f"{mod_name} -> {redmod_target}",
                            flush=True,
                        )
                    except OSError as exc:
                        result.errors.append(
                            f"redmod symlink {mod_name}: {exc}"
                        )
                    redmod_handled = True

                # Pattern C: Subfolder mit info.json, OHNE mods/ Prefix
                # Der Subfolder wird als Ordner-Symlink deployed.
                # Gesamter Mod wird danach übersprungen (continue).
                if not redmod_handled and not (mod_dir / "mods").is_dir():
                    for child in mod_dir.iterdir():
                        if (
                            child.is_dir()
                            and child.name.lower() not in _SKIP_DIRS
                            and (child / "info.json").is_file()
                        ):
                            redmod_target = (
                                self._game_path
                                / self._redmod_path
                                / child.name
                            )
                            redmod_target.parent.mkdir(
                                parents=True, exist_ok=True
                            )

                            if redmod_target.is_symlink():
                                redmod_target.unlink()
                            elif redmod_target.exists():
                                result.skipped_real_files.append(
                                    str(
                                        redmod_target.relative_to(
                                            self._game_path
                                        )
                                    )
                                )
                                continue

                            try:
                                redmod_target.symlink_to(child)
                                result.links_created += 1
                                symlinks.append({
                                    "link": str(
                                        Path(self._redmod_path)
                                        / child.name
                                    ),
                                    "target": str(child),
                                    "mod": mod_name,
                                    "type": "dir_symlink",
                                })
                                print(
                                    f"[DEPLOY] REDmod Pattern C: "
                                    f"{mod_name}/{child.name} "
                                    f"-> {redmod_target}",
                                    flush=True,
                                )
                            except OSError as exc:
                                result.errors.append(
                                    f"redmod symlink "
                                    f"{mod_name}/{child.name}: {exc}"
                                )
                            redmod_handled = True

            if redmod_handled:
                continue  # Keine Einzel-Dateien symlinken

            # Walk all files in this mod (use cache when available)
            if self._mod_index is not None:
                cached_files = self._mod_index.get_file_list(mod_name)
                file_iter = (mod_dir / finfo["rel"] for finfo in cached_files)
            else:
                file_iter = (f for f in mod_dir.rglob("*") if f.is_file())
            for src_file in file_iter:
                if not src_file.is_file():
                    continue

                # Skip metadata files
                if src_file.name in _SKIP_FILES:
                    continue

                # Skip installer directories (fomod/ etc.)
                try:
                    rel_check = src_file.relative_to(mod_dir)
                    if rel_check.parts and rel_check.parts[0].lower() in _SKIP_DIRS:
                        continue
                except ValueError:
                    pass

                # Skip non-game files in mod root directory only
                # (images, readmes, etc. — subdirectory files are game content)
                if src_file.parent == mod_dir and src_file.suffix.lower() in _SKIP_ROOT_EXTENSIONS:
                    continue

                # BA2-Packing: skip files that will be packed into BA2
                if self._needs_ba2_packing:
                    ext = src_file.suffix.lower()
                    if ext not in _BA2_SYMLINK_EXTENSIONS:
                        continue

                # Compute relative path from mod root
                try:
                    rel = src_file.relative_to(mod_dir)
                except ValueError:
                    continue

                # Strip "root/" prefix (RootBuilder pattern)
                if rel.parts and rel.parts[0].lower() == "root":
                    rel = Path(*rel.parts[1:]) if len(rel.parts) > 1 else rel

                # Direct-install mods skip data_path (frameworks go into game root)
                is_direct = self.is_direct_install(mod_name)

                # Prepend data_path (e.g. "Data" for Bethesda games)
                # Skip for direct-install mods — they deploy into game root
                if self._data_path and not is_direct:
                    data_prefix = Path(self._data_path)

                    # Multi-folder routing (e.g. Witcher 3: mods/ → Mods/, dlc/ → DLC/)
                    routed = False
                    if self._multi_folder_routes and len(rel.parts) > 1:
                        first_part = rel.parts[0]
                        if first_part in self._multi_folder_routes:
                            target_prefix = self._multi_folder_routes[first_part]
                            rel = Path(target_prefix) / Path(*rel.parts[1:])
                            routed = True

                    if not routed:
                        try:
                            rel.relative_to(data_prefix)
                            # rel beginnt bereits mit Data/ → nicht nochmal
                        except ValueError:
                            if self._nest_under_mod_name:
                                rel = data_prefix / mod_name / rel
                            else:
                                rel = data_prefix / rel

                # Determine deploy base: custom separator path or global game path
                mod_separator = mod_to_separator.get(mod_name, "")
                sep_path = self._separator_deploy_paths.get(mod_separator, "")
                deploy_base = Path(sep_path) if sep_path else self._game_path

                target = deploy_base / rel

                # Safety: never overwrite a real (non-symlink) game file
                # Exception: direct-install (framework) mods MUST overwrite
                if target.exists() and not target.is_symlink():
                    if is_direct:
                        pass  # frameworks are allowed to overwrite real files
                    else:
                        result.skipped_real_files.append(str(rel))
                        continue

                # Create parent directories if needed
                parent = target.parent
                if not parent.exists():
                    try:
                        parent.mkdir(parents=True, exist_ok=True)
                        # Track created directories (relative to deploy_base)
                        try:
                            rel_parent = parent.relative_to(deploy_base)
                            # Track each level of newly created dirs
                            # Use deploy_base:rel_dir format for custom paths
                            parts = rel_parent.parts
                            for i in range(len(parts)):
                                d = deploy_base / Path(*parts[: i + 1])
                                dir_key = str(d.relative_to(deploy_base))
                                if sep_path:
                                    dir_key = f"{deploy_base}:{dir_key}"
                                if dir_key not in created_dirs:
                                    created_dirs.add(dir_key)
                        except ValueError:
                            pass
                    except OSError as exc:
                        result.errors.append(
                            f"mkdir {parent}: {exc}"
                        )
                        continue

                # Remove existing symlink (lower priority mod)
                if target.is_symlink():
                    try:
                        target.unlink()
                    except OSError as exc:
                        result.errors.append(
                            f"unlink {target}: {exc}"
                        )
                        continue

                # Decide: copy or symlink?
                # 1) Frameworks (direct-install) → always copy
                # 2) Files under GameCopyDeployPaths → copy (shim_copy)
                # 3) Everything else → symlink
                needs_copy = is_direct
                if not needs_copy and self._copy_deploy_paths:
                    rel_posix = str(rel).replace("\\", "/")
                    for cp in self._copy_deploy_paths:
                        if rel_posix.startswith(cp + "/") or rel_posix == cp:
                            needs_copy = True
                            break

                if needs_copy:
                    deploy_type = "copy" if is_direct else "shim_copy"

                    # Framework reverse-sync: wenn die Datei im Game-Verzeichnis
                    # neuer ist als in .mods/, wurde sie extern aktualisiert.
                    # → .mods/ mit der neueren Version aktualisieren.
                    if is_direct and target.is_file() and not target.is_symlink():
                        try:
                            src_mtime = src_file.stat().st_mtime
                            tgt_mtime = target.stat().st_mtime
                            if tgt_mtime > src_mtime + 1:  # +1s Toleranz
                                print(
                                    f"[DEPLOY] REVERSE-SYNC: {rel} — "
                                    f"Game-Version ist neuer, aktualisiere .mods/",
                                    flush=True,
                                )
                                shutil.copy2(target, src_file)
                                # Bereits aktuell im Game-Dir → kein erneutes Kopieren nötig
                                entry_data = {
                                    "link": str(rel),
                                    "target": str(src_file),
                                    "mod": mod_name,
                                    "type": deploy_type,
                                }
                                if sep_path:
                                    entry_data["deploy_base"] = sep_path
                                symlinks.append(entry_data)
                                result.files_copied += 1
                                continue
                        except OSError:
                            pass

                    print(f"[DEPLOY] COPY ({deploy_type}): {rel} -> {target}", flush=True)
                    try:
                        shutil.copy2(src_file, target)
                        result.files_copied += 1
                        entry_data = {
                            "link": str(rel),
                            "target": str(src_file),
                            "mod": mod_name,
                            "type": deploy_type,
                        }
                        if sep_path:
                            entry_data["deploy_base"] = sep_path
                        symlinks.append(entry_data)
                    except OSError as exc:
                        result.errors.append(
                            f"copy {rel}: {exc}"
                        )
                else:
                    try:
                        target.symlink_to(src_file)
                        result.links_created += 1
                        entry_data = {
                            "link": str(rel),
                            "target": str(src_file),
                            "mod": mod_name,
                            "type": "symlink",
                        }
                        if sep_path:
                            entry_data["deploy_base"] = sep_path
                        symlinks.append(entry_data)
                    except OSError as exc:
                        result.errors.append(
                            f"symlink {rel} -> {src_file}: {exc}"
                        )

        # Save manifest
        manifest = {
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "game_path": str(self._game_path),
            "instance_path": str(self._instance_path),
            "symlinks": symlinks,
            "created_dirs": sorted(created_dirs, reverse=True),
            "ba2_archives": [],
            "ini_backup": None,
        }
        try:
            self._manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            result.errors.append(f"write manifest: {exc}")

        result.dirs_created = len(created_dirs)

        print(
            f"[DEPLOY] Result: {result.links_created} symlinks, "
            f"{result.files_copied} copies, {len(result.errors)} errors",
            flush=True,
        )

        if result.errors:
            result.success = False

        return result

    def purge(self) -> DeployResult:
        """Remove all deployed symlinks and clean up empty directories.

        Reads the manifest to know exactly which symlinks to remove.
        Only removes symlinks whose targets point into ``.mods/``.

        Returns:
            DeployResult with statistics and any errors.
        """
        result = DeployResult()

        if not self._manifest_path.is_file():
            result.errors.append("No deploy manifest found.")
            return result

        try:
            text = self._manifest_path.read_text(encoding="utf-8")
            manifest = json.loads(text)
        except (OSError, json.JSONDecodeError) as exc:
            result.success = False
            result.errors.append(f"read manifest: {exc}")
            return result

        game_path = Path(manifest.get("game_path", str(self._game_path)))

        # Remove symlinks (but NOT copied files from direct-install mods)
        for entry in manifest.get("symlinks", []):
            link_rel = entry.get("link", "")
            # Use per-entry deploy_base if present (custom separator path)
            entry_deploy_base = entry.get("deploy_base", "")
            base_path = Path(entry_deploy_base) if entry_deploy_base else game_path
            link_path = base_path / link_rel
            deploy_type = entry.get("type", "symlink")

            # Direct-install copies are intentionally left in place
            if deploy_type == "copy":
                continue

            # Shim copies are removed during purge (unlike framework copies)
            if deploy_type == "shim_copy":
                try:
                    link_path.unlink(missing_ok=True)
                    result.links_removed += 1
                except OSError as exc:
                    result.errors.append(f"unlink shim {link_rel}: {exc}")
                continue

            # Directory symlinks (LML mods)
            if deploy_type == "dir_symlink":
                if link_path.is_symlink():
                    try:
                        link_path.unlink()
                        result.links_removed += 1
                    except OSError as exc:
                        result.errors.append(f"unlink dir_symlink {link_rel}: {exc}")
                continue

            if not link_path.is_symlink():
                # Already gone or replaced by a real file — skip
                continue

            # Safety: only remove if target points into .mods/
            try:
                real_target = link_path.resolve()
                mods_str = str(self._mods_path)
                if not str(real_target).startswith(mods_str):
                    result.errors.append(
                        f"skip {link_rel}: target {real_target} "
                        f"not inside {mods_str}"
                    )
                    continue
            except OSError:
                pass  # broken symlink is fine to remove

            try:
                link_path.unlink()
                result.links_removed += 1
            except OSError as exc:
                result.errors.append(f"unlink {link_rel}: {exc}")

        # NOTE: BA2 archive cleanup and INI restore are handled by
        # game_panel.py (the orchestrator) via BA2Packer.cleanup_ba2s()
        # and BA2Packer.restore_ini().  We skip them here to avoid
        # double-cleanup and race conditions with manifest updates.

        # Clean up created directories (deepest first)
        # Format: "rel/path" for game_path or "/abs/path:rel/path" for custom deploy
        for dir_rel in manifest.get("created_dirs", []):
            if ":" in dir_rel and dir_rel[0] == "/":
                # Custom deploy path format: /abs/base:rel/dir
                colon_idx = dir_rel.index(":", 1)  # Skip first char (/)
                custom_base = Path(dir_rel[:colon_idx])
                rel_part = dir_rel[colon_idx + 1:]
                dir_path = custom_base / rel_part
            else:
                dir_path = game_path / dir_rel

            if not dir_path.is_dir():
                continue

            # Only remove if empty
            try:
                if not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    result.dirs_removed += 1
            except OSError:
                pass  # Not empty or permission issue — leave it

        # Remove manifest
        try:
            self._manifest_path.unlink()
        except OSError:
            pass

        return result

    def deployed_mod_count(self) -> int:
        """Return the number of mods in the current deployment."""
        if not self._manifest_path.is_file():
            return 0
        try:
            text = self._manifest_path.read_text(encoding="utf-8")
            manifest = json.loads(text)
            mod_names = {
                entry.get("mod", "")
                for entry in manifest.get("symlinks", [])
            }
            mod_names.discard("")
            return len(mod_names)
        except (OSError, json.JSONDecodeError):
            return 0

    def deployed_link_count(self) -> int:
        """Return the number of symlinks in the current deployment."""
        if not self._manifest_path.is_file():
            return 0
        try:
            text = self._manifest_path.read_text(encoding="utf-8")
            manifest = json.loads(text)
            return len(manifest.get("symlinks", []))
        except (OSError, json.JSONDecodeError):
            return 0
