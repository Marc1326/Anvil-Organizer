"""Game settings files that travel with the profile ("local INIs").

The game only reads its settings from one place, so a profile switch
copies the live files into the profile that owns them and puts the new
profile's copies back.  A profile without copies yet starts from
whatever is live.  A marker next to the live files remembers the owner,
so a skipped swap (game running, failed purge) never files one
profile's settings under another.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

SETTINGS_DIR = "game_settings"
OWNER_MARKER = ".anvil_settings_owner"
# Written while the live files belong to no profile (option off)
NO_OWNER = "-"


def local_inis_enabled(idata: dict | None) -> bool:
    # Same default as the settings dialog shows
    value = (idata or {}).get("local_inis", "true")
    return str(value).lower() in ("true", "1")


def _marker(files: list[Path]) -> Path:
    return files[0].parent / OWNER_MARKER


def _read_marker(files: list[Path]) -> str | None:
    """Marker text, or None when there is no marker at all."""
    try:
        return _marker(files).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError:
        return NO_OWNER


def read_owner(files: list[Path]) -> Path | None:
    text = _read_marker(files)
    if not text or text == NO_OWNER:
        return None
    return Path(text)


def _write_marker(files: list[Path], text: str) -> None:
    marker = _marker(files)
    if not marker.parent.is_dir():
        return
    tmp = marker.with_name(marker.name + ".anvil_tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, marker)
    finally:
        tmp.unlink(missing_ok=True)


def _write_owner(files: list[Path], profile: Path) -> None:
    _write_marker(files, str(profile.resolve()))


def rename_owner(files: list[Path], old: Path, new: Path) -> None:
    """Follow a profile rename, or the next swap would lose its changes."""
    if not files:
        return
    try:
        owner = read_owner(files)
        if owner is not None and _same(owner, old):
            _write_owner(files, new)
    except OSError:
        pass


def clear_owner(files: list[Path]) -> None:
    """The live files belong to no profile while the option is off."""
    if not files:
        return
    try:
        _write_marker(files, NO_OWNER)
    except OSError:
        pass


def save_to_owner(files: list[Path]) -> list[str]:
    """Store the live files with their owner, e.g. after the game closed."""
    if not files:
        return []
    try:
        owner = read_owner(files)
        if owner is None or not owner.is_dir():
            return []
        return save_to_profile(files, owner, prune=True)
    except OSError as exc:
        return [str(exc)]


def _same(a: Path, b: Path) -> bool:
    return a.resolve() == b.resolve()


def _atomic_copy(src: Path, dst: Path) -> None:
    tmp = dst.with_name(dst.name + ".anvil_tmp")
    try:
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
    finally:
        tmp.unlink(missing_ok=True)


def _live_target(live: Path) -> Path:
    # Users sometimes link their INIs elsewhere — keep the link
    return live.resolve() if live.is_symlink() else live


def save_to_profile(files: list[Path], profile_dir: Path,
                    prune: bool = False) -> list[str]:
    # A deleted profile must not come back just to hold the settings
    if not profile_dir.is_dir():
        return []
    store = profile_dir / SETTINGS_DIR
    errors: list[str] = []
    for live in files:
        try:
            if not live.is_file():
                # Deleted by the user (e.g. to reset key bindings): the
                # profile must not bring the old copy back later.  Only
                # with a known owner — a fresh prefix looks the same.
                if prune and live.parent.is_dir() and not live.is_symlink():
                    (store / live.name).unlink(missing_ok=True)
                continue
            store.mkdir(exist_ok=True)
            _atomic_copy(live, store / live.name)
        except OSError as exc:
            errors.append(f"{live.name}: {exc}")
    return errors


def restore_from_profile(files: list[Path], profile_dir: Path) -> list[str]:
    store = profile_dir / SETTINGS_DIR
    if not store.is_dir():
        # First visit: the profile starts with the current settings
        return save_to_profile(files, profile_dir)
    # Keep the current set so a failure halfway leaves no mixed state
    before: dict[Path, bytes | None] = {}
    errors: list[str] = []
    for live in files:
        saved = store / live.name
        if not live.parent.is_dir():
            continue
        target = _live_target(live)
        try:
            if saved.is_file():
                before[target] = target.read_bytes() if target.is_file() else None
                _atomic_copy(saved, target)
            elif target.is_file() and not live.is_symlink():
                # The profile never had this file — the previous owner's
                # copy must not stay behind and end up in this profile
                before[target] = target.read_bytes()
                target.unlink()
        except OSError as exc:
            errors.append(f"{live.name}: {exc}")
            break
    if errors:
        for target, data in before.items():
            try:
                if data is None:
                    target.unlink(missing_ok=True)
                else:
                    tmp = target.with_name(target.name + ".anvil_tmp")
                    try:
                        tmp.write_bytes(data)
                        os.replace(tmp, target)
                    finally:
                        tmp.unlink(missing_ok=True)
            except OSError as exc:
                errors.append(f"{target.name}: {exc}")
    return errors


def switch_profile_settings(
    files: list[Path], old_profile: Path | None, new_profile: Path,
) -> list[str]:
    """Hand the live settings to *new_profile*.

    The live files are saved to their recorded owner first; without a
    record, *old_profile* is taken as the owner.
    """
    if not files:
        return []
    try:
        return _switch(files, old_profile, new_profile)
    except OSError as exc:
        return [str(exc)]


def _switch(files: list[Path], old_profile: Path | None,
            new_profile: Path) -> list[str]:
    text = _read_marker(files)
    prune = False
    if text is None:
        # Never swapped before: the live files are the current profile's
        owner = old_profile
    elif not text or text == NO_OWNER:
        # Option off, or a marker cut short — load only, save nothing
        owner = None
    else:
        owner = Path(text)
        prune = True
        if not owner.is_dir():
            # Deleted profile or instance: its settings go with it
            # instead of landing in someone else's copy
            owner = None
    if owner is not None and _same(owner, new_profile):
        return []
    errors: list[str] = []
    if owner is not None:
        errors += save_to_profile(files, owner, prune=prune)
        if errors:
            # Loading the new set now would lose the unsaved changes
            return errors
    errors += restore_from_profile(files, new_profile)
    if errors:
        return errors
    try:
        _write_owner(files, new_profile)
    except OSError as exc:
        errors.append(f"{OWNER_MARKER}: {exc}")
        # A stale owner would get the new profile's settings next time;
        # without a marker the caller's current profile is assumed
        try:
            _marker(files).unlink(missing_ok=True)
        except OSError:
            pass
    return errors
