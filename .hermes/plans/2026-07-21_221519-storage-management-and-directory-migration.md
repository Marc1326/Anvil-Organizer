# Anvil Storage Management and Directory Migration Implementation Plan

> **For Hermes:** Use subagent-driven-development and strict TDD to implement this plan task-by-task. Follow the repository review workflow. Do not touch BG3 code. Ask Marc before every commit.

**Goal:** Make Anvil's existing custom instance paths work end-to-end, then add a safe guided storage migration system for mods, downloads, complete instances, and eventually the global Anvil base directory.

**Architecture:** Introduce one resolved instance-path object as the source of truth for all per-instance storage. Installer, scanner, index, deployer, collection, backup, and UI receive those resolved paths instead of rebuilding `<instance>/.mods` and related defaults. Build a separate journaled migration engine that copies, verifies, atomically switches configuration, reloads indexes, and redeploys. A later global `base_dir.py` layer centralizes `~/.anvil-organizer` and reuses the same migration engine.

**Tech Stack:** Python 3, PySide6/QSettings, pathlib, shutil/os, JSON migration journals, unittest, existing Anvil deploy/purge lifecycle.

---

## Scope and delivery order

### Delivery A — Fix #97 first

Make the already visible settings for custom Mods, Downloads, Profiles, and Overwrite directories work everywhere. This is a bug fix and provides immediate relief for users with a small system disk.

### Delivery B — Storage Management UI

Add a guided **Move Directories** assistant for selected components or a complete instance. Copy first, verify, switch paths only after success, retain the source until explicit cleanup.

### Delivery C — #80 global base directory

Centralize the global Anvil data root, offer a first-run location chooser, then support safe migration of an existing root.

### Delivery D — Full instance export/import

Reuse the migration inventory and verification engine for a portable full-instance transfer format. Existing CSV, `.anvilpack`, and metadata backup remain separate.

---

## Hard constraints

- Do not modify BG3 files or behavior.
- Do not mix this work with the current uncommitted GRB implementation. Finish, test, review, and obtain Marc's approval to commit GRB first.
- Never delete source data automatically after migration.
- Never create an empty fallback directory when a configured drive is missing.
- Never change persisted paths before target verification succeeds.
- Never migrate while a game, download, extraction, installation, deployment, purge, or profile mutation is active.
- Purge managed deployment links before moving their source library; redeploy after switching.
- Preserve symlinks as symlinks and do not dereference arbitrary links while copying.
- Existing default instances without custom paths must behave byte-for-byte as before.
- All user-facing strings must exist in all seven locales: `de`, `en`, `es`, `fr`, `it`, `pt`, `ru`.

---

# Storage topology and selection model

The migration UI must not assume that every managed game moves at once or that all games share one physical drive.

## Required first release: per-game component placement

- Display every managed game as a selectable row/card with current Mods, Downloads, Backups, and Overwrite paths plus sizes.
- Support selection modes: one game, several selected games, or all games.
- Let each selected game choose its own destination. Do not force a single destination for the whole batch.
- Queue migrations sequentially by default so one failed/missing drive does not invalidate already verified games.
- Show per-game and total bytes/files, per-game status, completed/remaining games, and a resumable batch journal.
- Allow the user to stop after the current game. Completed games remain switched; unstarted games retain their original configuration.
- A nearly full source drive is not a blocker if the destination has enough capacity, because migration copies to the destination and retains source data until explicit cleanup. Warn that cross-drive transfer time is physically unavoidable.
- When source and destination are on the same filesystem, allow an optimized rename/reflink path only after capability and rollback checks; cross-device moves always use verified copy.

Example supported layout:

```text
Cyberpunk Mods     → /mnt/NVMe1/Anvil/Cyberpunk/Mods
Cyberpunk Downloads→ /mnt/HDD1/Anvil/Downloads/Cyberpunk
Skyrim Mods        → /mnt/SSD2/Anvil/Skyrim/Mods
GRB Mods           → /mnt/NVMe2/Anvil/GRB/Mods
Profiles/metadata  → instance/default location
```

## Later optional release: multiple mod-library roots inside one game

This is not part of the first #97 fix. It requires a storage-pool/registry architecture because the current model assumes one Mods directory per instance.

Proposed model:

```python
@dataclass(frozen=True)
class ModLocation:
    mod_name: str
    root_id: str
    path: Path

@dataclass(frozen=True)
class StorageRoot:
    root_id: str
    path: Path
    mount_identity: str
    writable: bool
    priority: int
```

Required capabilities:

- Register multiple trusted storage roots per instance.
- Choose a default install root and optionally choose a root during each installation.
- Store a stable mapping from mod identity/name to physical root; profiles and priority remain independent of physical location.
- Scan/index all online roots as one logical mod library.
- Detect duplicate mod names across roots and block ambiguous deployment.
- Make Installer, ModIndex, conflict scanner, collection/backup, and every game-specific deployer consume the logical mod-location registry rather than concatenate `mods_root / mod_name`.
- Permit moving one selected mod or multiple selected mods between registered roots using the same copy/verify/switch journal.
- Track mounts by stable identity where practical, not only a path that could be reused by a different device.
- Mark mods on missing drives offline. Never silently treat them as disabled, deleted, or replace them with empty folders.
- Deployment must fail clearly if an active mod's storage root is offline.
- Purge safety must accept only targets inside registered online roots; arbitrary external symlink targets remain forbidden.

Do not implement multi-root support as an untracked forest of symlinks. A compatibility symlink hub may be evaluated in a spike, but the authoritative state must be a validated registry so missing drives, duplicates, purge safety, and per-mod movement are deterministic.

---

# Delivery A: Fix custom instance paths (#97)

## Task A1: Define a single resolved instance-path contract

**Objective:** Resolve `%INSTANCE_DIR%` and absolute custom paths once and pass one typed object through Anvil.

**Files:**
- Create: `anvil/core/instance_paths.py`
- Test: `tests/test_instance_paths.py`
- Modify: `anvil/core/instance_manager.py`

**Proposed API:**

```python
@dataclass(frozen=True)
class InstancePaths:
    instance: Path
    mods: Path
    downloads: Path
    profiles: Path
    overwrite: Path
    backups: Path
    cache: Path


def resolve_instance_paths(instance_path: Path, instance_data: Mapping[str, str]) -> InstancePaths:
    ...
```

**Validation rules:**

- Expand `%INSTANCE_DIR%` only at the beginning of a configured path.
- Expand `~`, then produce an absolute normalized path.
- Reject NUL and empty custom values; use the documented default instead.
- Do not silently create configured external directories during resolution.
- Keep path existence/writability checks separate from resolution.

**TDD cycle:**

1. Test default `%INSTANCE_DIR%/.mods`, `.downloads`, `.profiles`, `.overwrite`.
2. Test absolute external Mods and Downloads paths.
3. Test paths containing spaces and Unicode.
4. Test a missing external mount remains missing and is not created.
5. Run: `PYTHONPATH=. .venv/bin/python tests/test_instance_paths.py`.
6. Implement minimal resolver.
7. Re-run and expect all tests GREEN.

**Commit boundary:** Ask Marc before committing. Suggested message: `Fix instance path resolution`.

## Task A2: Make installer honor the resolved Mods directory

**Objective:** New installations must land in the configured Mods path rather than `<instance>/.mods`.

**Files:**
- Modify: `anvil/core/mod_installer.py`
- Modify: `anvil/mainwindow.py`
- Test: extend existing installer tests or create `tests/test_custom_mods_path.py`

**Required behavior:**

- `ModInstaller` accepts an explicit `mods_path`.
- Existing callers that omit it retain `<instance>/.mods` for backward compatibility.
- MainWindow passes `InstancePaths.mods` for normal installs, framework checks, FOMOD installs, downloads installs, and drag/drop installs.
- Failed installs leave no partial target outside the configured directory.

**Tests:**

1. Configure external Mods path in a temporary directory.
2. Install a real test ZIP.
3. Assert the mod exists only under the external target.
4. Assert `<instance>/.mods/<name>` was not created.
5. Test a non-writable/missing mount fails visibly instead of falling back.

## Task A3: Make scanner, ModIndex, groups, and collection logic honor custom Mods/Profile paths

**Objective:** Every read-side feature must see the same files the installer wrote.

**Files likely to change:**
- `anvil/core/mod_entry.py`
- `anvil/core/mod_index.py`
- `anvil/core/collection_io.py`
- `anvil/mainwindow.py`
- profile/group helpers that currently use `<instance>/.profiles` or `<instance>/.mods`
- Tests: `tests/test_custom_instance_paths.py`

**Required behavior:**

- Mod list scan reads `InstancePaths.mods`.
- Mod index stores/reads file lists from the configured Mods path.
- Group orphan cleanup reads configured Mods path.
- Current profile is `InstancePaths.profiles / profile_name`.
- Collection export/import reads configured Mods and Profiles paths.
- Backup/restore reads configured Mods and Profiles paths.
- No BG3 code changes.

**Verification:**

- Search after implementation for remaining operational `instance_path / ".mods"` and `instance_path / ".profiles"` usages.
- Classify each remaining hit as intentional or a bug.
- Test collection analysis and profile switching with external paths.

## Task A4: Make normal deployment honor custom Mods/Profile paths

**Objective:** Deployment must consume the same external library shown in the UI.

**Files:**
- Modify: `anvil/core/mod_deployer.py`
- Modify: `anvil/widgets/game_panel.py`
- Modify plugin custom-deployer factory contract only where required
- Test: `tests/test_custom_deployer_paths.py`

**Required behavior:**

- `ModDeployer` accepts explicit `mods_path` and `profiles_path`.
- Manifest remains tied to the instance, unless storage design explicitly moves it later.
- Purge validates links against the configured Mods root, not `<instance>/.mods`.
- Standard games remain unchanged under default paths.
- GRB custom deployer receives resolved Mods/Profile paths without changing GRB archive semantics.
- BG3 remains untouched.

**Tests:**

- Deploy an enabled mod from an external temporary Mods path.
- Verify game link target resolves inside that external path.
- Purge removes only links into the configured Mods root.
- A link to an unrelated external path must not be removed.

## Task A5: Missing-drive/offline handling

**Objective:** A missing configured drive must never become a new empty directory on the system partition.

**Files:**
- Create or modify a storage-status helper in `anvil/core/instance_paths.py`
- Modify instance loading in `anvil/mainwindow.py`
- Modify status display only through existing themed widgets
- Tests: `tests/test_instance_storage_offline.py`

**Behavior:**

- If a configured external path is absent, mark the instance/component offline.
- Show the exact missing path.
- Offer: Retry, Locate directory, Keep instance offline.
- Do not call `mkdir(parents=True)` on the missing mount path during ordinary loading.
- Do not deploy, install, scan as empty, or rewrite the configured path.

## Delivery A acceptance criteria

- The #97 reproduction with Skyrim/AppImage works using an external Mods path.
- Install, list scan, index, conflicts, collection, backup, deploy, and purge all use the same configured path.
- Default paths behave unchanged.
- Missing drive is visible and fail-closed.
- Full tests, syntax checks, restart, and four required independent reviews pass.

---

# Delivery B: Guided Move Directories assistant

## Task B1: Storage inventory service

**Objective:** Calculate component size, file count, symlink count, current path, mount, and free space without freezing the GUI.

**Files:**
- Create: `anvil/core/storage_inventory.py`
- Test: `tests/test_storage_inventory.py`

**Components:**

- Mods
- Downloads
- Profiles
- Overwrite
- Backups
- Cache
- Whole instance

**Rules:**

- Do not follow symlinks while calculating size.
- Detect unreadable files and report them before migration.
- Report source device and destination device.
- Support cancellation.

## Task B2: Journaled copy engine

**Objective:** Copy selected data safely with resume, cancellation, and crash recovery.

**Files:**
- Create: `anvil/core/storage_migration.py`
- Test: `tests/test_storage_migration.py`

**Journal state machine:**

```text
planned
preflight_ok
purged
copying
copied
verified
paths_switched
reindexed
redeployed
complete
rollback_required
```

**Journal location:** Keep it outside the directory currently being moved, under the unchanged global config/state location.

**Preflight:**

- Source and target differ.
- Target not inside source.
- Target empty by default.
- Destination writable.
- Free space >= source size plus safety margin.
- No active game or Anvil operation.
- No unresolved previous migration.

**Copy semantics:**

- Use direct filesystem copies, not ZIP recompression.
- Preserve file permissions, timestamps, and symlinks.
- Copy regular files through bounded buffers/copy APIs.
- For same-filesystem moves, optionally use reflinks only after capability testing; never rely on them.
- Never delete source in the engine's successful default path.

**Verification levels:**

- Fast: relative path set, file type, size, selected critical hashes.
- Full: SHA-256 of all regular files plus symlink target equality.
- Store the selected level in the journal.

**Interruption tests:**

- Cancel during file copy.
- ENOSPC midway.
- Permission failure.
- Process interruption after copy but before path switch.
- Interruption after path switch but before redeploy.
- Resume must not duplicate or corrupt data.

## Task B3: Atomic path switch and rollback

**Objective:** Change instance configuration only after copy verification.

**Files:**
- Modify: `anvil/core/instance_manager.py`
- Use: `anvil/core/instance_paths.py`
- Test: extend `tests/test_storage_migration.py`

**Behavior:**

- Write new `.anvil.ini` values through a temporary file or equivalent safe QSettings strategy.
- Persist old values in the migration journal.
- Re-resolve paths and verify they point at the target.
- On failure, restore old config and continue using source.
- Rebuild ModIndex and reload UI after switch.
- Redeploy active mods.
- Mark complete only after successful redeploy.

## Task B4: Move Directories wizard

**Objective:** Add the user-facing workflow under Settings → Storage & Directories and make it visually indistinguishable from Anvil's existing GUI.

**Mandatory GUI integration:**

- Inspect the current modern Settings pages, card-based dialogs, headers, footers, progress displays, spacing, typography, button hierarchy, and object-name conventions before designing the wizard.
- Support both the modern and classic themes. Modern widgets use the existing object names/design tokens; classic mode inherits the established application QSS.
- Do not add `setStyleSheet()` to new widgets. Do not introduce one-off colors, fonts, radii, shadows, or spacing values that conflict with Anvil's design system.
- Reuse existing themed controls and dialog layout patterns wherever practical instead of creating a separate visual language.
- Keep the wizard usable at Anvil's supported minimum window size and with long translated strings in all seven locales.
- The progress view must remain responsive for hundreds of mods and thousands of files. Show overall bytes, file count, current component, current file, speed, elapsed time, and estimated remaining time without visually flooding the dialog.
- Error, offline-drive, resume, verification, and completion states must use the same warning/status/toast conventions as the rest of Anvil.
- Before implementation, create a read-only GUI impact inventory naming the existing Settings and dialog components that will be reused. If screenshots/mockups are produced, show and describe them to Marc and wait for confirmation before coding the GUI.

**Files:**
- Create: `anvil/dialogs/storage_migration_dialog.py`
- Modify: `anvil/widgets/settings_dialog.py`
- Add locale keys in all seven `anvil/locales/*.json`
- Test logic separately from Qt where possible; add Qt signal tests for button wiring.

**Wizard pages:**

1. Choose instance or all instances.
2. Choose components: Mods, Downloads, Profiles, Overwrite, Backups, Cache, whole instance.
3. Choose target.
4. Display source size, file count, target free space, and safety warnings.
5. Confirm purge/copy/verify/switch/redeploy flow.
6. Progress by bytes and files, current file, speed, elapsed time, estimated remaining time.
7. Result page with source-retention choice.

**Buttons:** Pause if implementation supports it safely; Cancel; Continue in background; Open source; Open target.

**Deletion policy:**

- Default: retain source.
- Offer delete only after complete verification and successful redeploy.
- Require a separate confirmation naming the exact source path and size.

## Task B5: Locate manually moved data

**Objective:** Recover when a user moved a directory outside Anvil.

**Files:**
- Extend `anvil/core/instance_paths.py`
- Add a small locate dialog or integrate with the storage wizard
- Tests: `tests/test_storage_markers.py`

**Marker:** `.anvil-location.json` with a stable instance ID, component type, and format version.

**Behavior:**

- Do not scan entire disks automatically.
- On missing configured path, offer Locate.
- User selects candidate directory.
- Verify marker and expected structure before updating config.
- If no marker exists, allow explicit adoption only after a detailed structural preview and confirmation.

## Delivery B acceptance criteria

- Move a 500-mod synthetic corpus with thousands of files without GUI lockup.
- Cancel and resume safely.
- Simulated ENOSPC leaves source and config unchanged.
- Missing target mount never creates fallback content.
- Config switches only after verification.
- Active deployment works from new location.
- Old data remains until explicit deletion.

---

# Delivery C: Global base directory (#80)

## Task C1: Central base directory source of truth

**Objective:** Eliminate operational hardcoding of `~/.anvil-organizer`.

**Files:**
- Create: `anvil/core/base_dir.py`
- Modify the exact files listed in `docs/anvil-feature-base-directory.md`
- Test: `tests/test_base_dir.py`

**Configuration:**

```ini
# ~/.config/AnvilOrganizer/AnvilOrganizer.conf
[General]
base_dir=/mnt/Gaming/Anvil
```

**Resolution:**

1. Valid absolute configured path.
2. Otherwise backward-compatible fallback `~/.anvil-organizer`.

**Derived getters:** instances, logs, plugins, credentials, current-instance file, socket.

## Task C2: First-run base-directory chooser

**Objective:** Let new users select storage before any Anvil data directory is created.

**Files:**
- Create: `anvil/widgets/base_dir_setup_dialog.py`
- Modify: `anvil/main.py`
- Locales and tests

**Bootstrap order:**

```text
read top-level config
show first-run chooser if appropriate
persist base_dir
create base directory
create single-instance socket
construct MainWindow/InstanceManager
```

## Task C3: Existing base-directory migration

**Objective:** Reuse Delivery B's journaled engine to migrate all global data.

**Data included:** instances, `.current`, logs, user plugins, credentials. Exclude runtime socket. Preserve external per-instance component paths without copying them.

**Flow:**

- Purge all managed instances that have deployment manifests.
- Copy and verify global data.
- Persist new base path in top-level config.
- Require application restart.
- Reopen and verify all instances before offering source deletion.
- Redeploy previously active instances only when their game/storage is available.

## Delivery C acceptance criteria

- Fresh install chooses custom base.
- Existing default users remain unchanged.
- Migration across filesystems succeeds and restarts cleanly.
- Missing new drive presents offline/recovery UI, not a new empty base.
- Credentials retain secure permissions.
- User plugins load from the new base.

---

# Delivery D: Full instance export/import

## Task D1: Define a new format separate from `.anvilpack`

**Objective:** Keep collection metadata sharing distinct from full data transfer.

**Suggested extension:** `.anvilinstance`.

**Options:** include Mods, Downloads, Profiles, Overwrite, Backups. Exclude credentials. Store a versioned manifest and strong hashes.

## Task D2: Reuse inventory and verification engine

For same-machine migration, use direct copy. For portable export, use a tar-like stream that preserves symlinks and permissions, with safe extraction and path traversal rejection. Do not recompress already-compressed mod payloads by default.

## Task D3: Import into configured storage

Import only after the target base/instance root is configured. Verify game identity, instance name collisions, destination free space, and all hashes before registering the instance.

---

# Testing and review matrix

## Unit tests

- Path resolution/defaults/custom paths.
- Missing mounts and permissions.
- Installer/deployer custom paths.
- Copy journal state transitions.
- Resume/cancel/ENOSPC.
- Symlink preservation and traversal rejection.
- Config rollback.
- Marker verification.
- Base-dir fallback and first-run persistence.

## Integration tests

- Skyrim custom Mods path, matching #97.
- Cyberpunk corpus with hundreds of synthetic mod directories.
- External Downloads path and active Nexus downloads.
- Cross-filesystem migration `/home` → mounted test filesystem.
- Default paths regression for multiple non-BG3 plugins.
- GRB custom deployer uses configured library paths without changing Forge semantics.
- No BG3 diffs.

## Manual GUI acceptance

- Settings displays sizes and paths correctly.
- Browse button signal signatures handle Qt's `checked` argument.
- Progress remains responsive.
- Cancel is safe.
- Restart after global base migration loads the new process and new path.
- Missing drive shows offline status.

## Required final commands

```bash
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python -m py_compile <all changed Python files>
git diff --check
./restart.sh
```

Inspect `debug.log`, `/tmp/anvil-deploy.log`, and service/process state for tracebacks, import errors, signal errors, and stale-process startup.

## Mandatory independent review

Run the repository's four-reviewer workflow after each delivery, with reviewers explicitly checking:

1. Data-loss and rollback risks.
2. Path traversal, symlink, and missing-mount behavior.
3. Signal/slot flow and settings persistence.
4. Architecture consistency and no BG3 changes.
5. Default-path regressions for all existing games.

All findings must be fixed and all four reviewers rerun until zero findings.

---

# Risks and decisions still requiring Marc

1. Whether Delivery A (#97) should ship before global base support — recommended: yes.
2. Whether Profiles should be independently movable or always travel with the instance — recommended: keep with instance initially.
3. Whether Downloads are included by default — recommended: user-selectable, off for whole-base migration if already external.
4. Fast versus full hash verification default — recommended: full for migration, fast optional for very large libraries.
5. Whether Anvil ever deletes source automatically — recommended: never; separate explicit cleanup action.
6. Whether pause is required in v1 — recommended: cancellation/resume first; pause only if state machine supports it cleanly.
7. Full export format timing — recommended: after Move Directories and global base migration are stable.

# Recommended implementation sequence

```text
Finish/review/commit current GRB work
→ Delivery A (#97 path plumbing)
→ release/test #97
→ Delivery B migration engine + wizard
→ release/test per-instance moves
→ Delivery C base-dir first-run
→ Delivery C existing-base migration
→ Delivery D full export/import
```
