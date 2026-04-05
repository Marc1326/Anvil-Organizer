"""GroupManager: CRUD for groups.json (mod grouping within separators).

Groups are a purely visual feature — they have NO effect on deployment,
priority, or modlist.txt.  They are stored per-profile in a
``groups.json`` file next to ``active_mods.json``.

Format::

    {
      "version": 1,
      "groups": {
        "Armor Collection": {
          "color": "#4FC3F7",
          "collapsed": false,
          "members": ["Cool_Armor_Mod", "Cool_Armor_Patch"]
        }
      }
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_DEFAULT_GROUP_COLOR = "#4FC3F7"


class GroupManager:
    """Manage mod groups for a single profile.

    All mutations auto-save to disk so the caller does not need to remember
    to call ``save()`` explicitly.
    """

    def __init__(self) -> None:
        self._path: Path | None = None
        self._groups: dict[str, dict[str, Any]] = {}

    # ── I/O ────────────────────────────────────────────────────────

    def load(self, profile_path: Path) -> None:
        """Load groups.json from *profile_path*.

        If the file does not exist, starts with an empty group set.
        """
        self._path = profile_path / "groups.json"
        self._groups = {}
        if self._path.is_file():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                self._groups = raw.get("groups", {})
            except (json.JSONDecodeError, OSError):
                self._groups = {}

    def save(self) -> None:
        """Persist current groups to disk."""
        if self._path is None:
            return
        data = {
            "version": 1,
            "groups": self._groups,
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    # ── Queries ────────────────────────────────────────────────────

    def all_groups(self) -> dict[str, dict[str, Any]]:
        """Return the full groups dict (name -> info)."""
        return dict(self._groups)

    def group_names(self) -> list[str]:
        """Return sorted list of group names."""
        return sorted(self._groups.keys())

    def group_exists(self, name: str) -> bool:
        """Check if a group with *name* exists."""
        return name in self._groups

    def get_group(self, name: str) -> dict[str, Any] | None:
        """Return group info dict or None."""
        return self._groups.get(name)

    def get_group_for_mod(self, folder_name: str) -> str:
        """Return group name that contains *folder_name*, or empty string."""
        for gname, gdata in self._groups.items():
            if folder_name in gdata.get("members", []):
                return gname
        return ""

    def get_members(self, group_name: str) -> list[str]:
        """Return list of member folder names for *group_name*."""
        g = self._groups.get(group_name)
        if g is None:
            return []
        return list(g.get("members", []))

    def is_group_head(self, folder_name: str) -> bool:
        """Check if *folder_name* is the first member of any group."""
        for gdata in self._groups.values():
            members = gdata.get("members", [])
            if members and members[0] == folder_name:
                return True
        return False

    def get_group_color(self, group_name: str) -> str:
        """Return the color string for *group_name*, or default."""
        g = self._groups.get(group_name)
        if g is None:
            return _DEFAULT_GROUP_COLOR
        return g.get("color", _DEFAULT_GROUP_COLOR)

    def is_collapsed(self, group_name: str) -> bool:
        """Check if *group_name* is collapsed."""
        g = self._groups.get(group_name)
        if g is None:
            return False
        return bool(g.get("collapsed", False))

    # ── Mutations (all auto-save) ──────────────────────────────────

    def create_group(
        self,
        name: str,
        members: list[str],
        color: str = _DEFAULT_GROUP_COLOR,
    ) -> bool:
        """Create a new group.  Returns False if name already exists."""
        if name in self._groups:
            return False
        # Remove members from any existing groups first
        for m in members:
            self.remove_member(m, _auto_save=False)
        self._groups[name] = {
            "color": color,
            "collapsed": False,
            "members": list(members),
        }
        self.save()
        return True

    def dissolve_group(self, name: str) -> list[str]:
        """Remove a group but keep its members in place.

        Returns the list of member folder names that were in the group.
        """
        g = self._groups.pop(name, None)
        if g is None:
            return []
        members = g.get("members", [])
        self.save()
        return members

    def rename_group(self, old_name: str, new_name: str) -> bool:
        """Rename a group.  Returns False if old_name doesn't exist or new_name taken."""
        if old_name not in self._groups or new_name in self._groups:
            return False
        self._groups[new_name] = self._groups.pop(old_name)
        self.save()
        return True

    def set_color(self, group_name: str, color: str) -> None:
        """Change the color of *group_name*."""
        g = self._groups.get(group_name)
        if g is not None:
            g["color"] = color
            self.save()

    def toggle_collapsed(self, group_name: str) -> bool:
        """Toggle collapsed state.  Returns the new collapsed state."""
        g = self._groups.get(group_name)
        if g is None:
            return False
        new_state = not g.get("collapsed", False)
        g["collapsed"] = new_state
        self.save()
        return new_state

    def set_collapsed(self, group_name: str, collapsed: bool) -> None:
        """Set collapsed state explicitly."""
        g = self._groups.get(group_name)
        if g is not None:
            g["collapsed"] = collapsed
            self.save()

    def add_member(self, group_name: str, folder_name: str) -> bool:
        """Add *folder_name* to *group_name*.

        Removes from any other group first.
        Returns False if group doesn't exist or member already in this group.
        """
        g = self._groups.get(group_name)
        if g is None:
            return False
        members = g.get("members", [])
        if folder_name in members:
            return False
        # Remove from other groups
        self.remove_member(folder_name, _auto_save=False)
        members.append(folder_name)
        g["members"] = members
        self.save()
        return True

    def remove_member(self, folder_name: str, _auto_save: bool = True) -> str:
        """Remove *folder_name* from whatever group it belongs to.

        Returns the group name it was removed from, or empty string.
        Auto-dissolves the group if it was the last member.
        """
        for gname, gdata in list(self._groups.items()):
            members = gdata.get("members", [])
            if folder_name in members:
                members.remove(folder_name)
                gdata["members"] = members
                removed_from = gname
                # Auto-dissolve if no members left
                if not members:
                    del self._groups[gname]
                if _auto_save:
                    self.save()
                return removed_from
        return ""

    def cleanup_orphans(self, existing_mod_folders: set[str]) -> None:
        """Remove members that no longer exist on disk.

        Auto-dissolves groups that become empty.
        """
        changed = False
        for gname in list(self._groups.keys()):
            gdata = self._groups[gname]
            old_members = gdata.get("members", [])
            new_members = [m for m in old_members if m in existing_mod_folders]
            if len(new_members) != len(old_members):
                changed = True
                if not new_members:
                    del self._groups[gname]
                else:
                    gdata["members"] = new_members
        if changed:
            self.save()

    def update_member_order(self, group_name: str, ordered_members: list[str]) -> None:
        """Reorder members within a group to match a new order.

        Only members already in the group are kept (in the new order).
        """
        g = self._groups.get(group_name)
        if g is None:
            return
        current = set(g.get("members", []))
        new_order = [m for m in ordered_members if m in current]
        # Add any members missing from ordered_members (shouldn't happen, but be safe)
        for m in g.get("members", []):
            if m not in new_order:
                new_order.append(m)
        g["members"] = new_order
        self.save()
