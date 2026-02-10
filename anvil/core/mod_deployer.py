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

from anvil.core.mod_list_io import read_modlist

# Files inside mod folders that are metadata, not game content.
_SKIP_FILES = {"meta.ini", "codes.txt"}


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
    ) -> None:
        self._instance_path = instance_path
        self._game_path = game_path
        self._mods_path = instance_path / ".mods"
        self._profile_path = instance_path / ".profiles" / "Default"
        self._manifest_path = instance_path / self.MANIFEST_NAME
        self._direct_patterns = [p.lower() for p in (direct_install_patterns or [])]

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

        # Read modlist for enabled mods in priority order
        modlist = read_modlist(self._profile_path)
        enabled_mods = [
            (name, idx) for idx, (name, enabled) in enumerate(modlist)
            if enabled
        ]

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

            # Skip separators
            if mod_name.endswith("_separator"):
                continue

            # Walk all files in this mod
            for src_file in mod_dir.rglob("*"):
                if not src_file.is_file():
                    continue

                # Skip metadata files
                if src_file.name in _SKIP_FILES:
                    continue

                # Compute relative path from mod root
                try:
                    rel = src_file.relative_to(mod_dir)
                except ValueError:
                    continue

                target = self._game_path / rel

                # Safety: never overwrite a real (non-symlink) game file
                if target.exists() and not target.is_symlink():
                    result.skipped_real_files.append(str(rel))
                    continue

                # Create parent directories if needed
                parent = target.parent
                if not parent.exists():
                    try:
                        parent.mkdir(parents=True, exist_ok=True)
                        # Track created directories (relative)
                        try:
                            rel_parent = parent.relative_to(self._game_path)
                            # Track each level of newly created dirs
                            parts = rel_parent.parts
                            for i in range(len(parts)):
                                d = self._game_path / Path(*parts[: i + 1])
                                if str(d.relative_to(self._game_path)) not in created_dirs:
                                    created_dirs.add(
                                        str(d.relative_to(self._game_path))
                                    )
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

                # Direct-install mods: COPY instead of symlink
                is_direct = self.is_direct_install(mod_name)

                if is_direct:
                    try:
                        shutil.copy2(src_file, target)
                        result.files_copied += 1
                        symlinks.append({
                            "link": str(rel),
                            "target": str(src_file),
                            "mod": mod_name,
                            "type": "copy",
                        })
                    except OSError as exc:
                        result.errors.append(
                            f"copy {rel}: {exc}"
                        )
                else:
                    try:
                        target.symlink_to(src_file)
                        result.links_created += 1
                        symlinks.append({
                            "link": str(rel),
                            "target": str(src_file),
                            "mod": mod_name,
                            "type": "symlink",
                        })
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
        }
        try:
            self._manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            result.errors.append(f"write manifest: {exc}")

        result.dirs_created = len(created_dirs)

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
            link_path = game_path / link_rel
            deploy_type = entry.get("type", "symlink")

            # Direct-install copies are intentionally left in place
            if deploy_type == "copy":
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

        # Clean up created directories (deepest first)
        for dir_rel in manifest.get("created_dirs", []):
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
