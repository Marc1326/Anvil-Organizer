"""FOMOD installer config parser (ModuleConfig.xml).

Parses the FOMOD XML format used by Nexus Mods installers.
Supports steps, groups, plugins, files, flags, and conditions.

Reference: MO2 installerFomod plugin.
"""

from __future__ import annotations

import shutil
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


# ── Data structures ───────────────────────────────────────────────────


@dataclass
class FomodFile:
    """A file or folder entry in a FOMOD config."""

    source: str
    destination: str
    is_folder: bool
    priority: int = 0


@dataclass
class FomodPlugin:
    """A selectable plugin option within a group."""

    name: str
    description: str
    image_path: str | None
    files: list[FomodFile]
    condition_flags: list[tuple[str, str]]  # (flag_name, value)
    type_name: str  # Required, Optional, Recommended, NotUsable, CouldBeUsable


@dataclass
class FomodGroup:
    """A group of plugins within an install step."""

    name: str
    group_type: str  # SelectExactlyOne, SelectAtMostOne, SelectAtLeastOne, SelectAny, SelectAll
    plugins: list[FomodPlugin]


@dataclass
class FomodStep:
    """An installation step containing option groups."""

    name: str
    groups: list[FomodGroup]
    visible_conditions: list[tuple[str, str]] | None = None
    visible_operator: str = "And"


@dataclass
class FomodConditionPattern:
    """A conditional file install pattern."""

    flags: list[tuple[str, str]]
    operator: str
    files: list[FomodFile]


@dataclass
class FomodConfig:
    """Complete parsed FOMOD configuration."""

    module_name: str
    module_image: str | None
    required_files: list[FomodFile]
    install_steps: list[FomodStep]
    conditional_installs: list[FomodConditionPattern]


# ── XML helpers ───────────────────────────────────────────────────────


def _norm_path(p: str) -> str:
    """Normalize a Windows-style path to forward slashes."""
    return p.replace("\\", "/").strip("/") if p else ""


def _parse_files(node: ET.Element | None) -> list[FomodFile]:
    """Parse file/folder list from an XML element."""
    if node is None:
        return []
    files: list[FomodFile] = []
    for child in node:
        tag = child.tag.split("}")[-1].lower()  # strip namespace
        if tag == "folder":
            files.append(FomodFile(
                source=_norm_path(child.get("source", "")),
                destination=_norm_path(child.get("destination", "")),
                is_folder=True,
                priority=int(child.get("priority", "0")),
            ))
        elif tag == "file":
            src = _norm_path(child.get("source", ""))
            dst = _norm_path(child.get("destination", src))
            files.append(FomodFile(
                source=src,
                destination=dst,
                is_folder=False,
                priority=int(child.get("priority", "0")),
            ))
    return files


def _parse_flag_conditions(
    node: ET.Element | None,
) -> tuple[list[tuple[str, str]], str]:
    """Parse dependency conditions (flagDependency elements).

    Returns ``([(flag, value), ...], operator)``.
    """
    if node is None:
        return [], "And"

    operator = node.get("operator", "And")
    flags: list[tuple[str, str]] = []
    for child in node:
        tag = child.tag.split("}")[-1].lower()
        if tag == "flagdependency":
            flags.append((child.get("flag", ""), child.get("value", "")))
        elif tag == "dependencies":
            sub_flags, _ = _parse_flag_conditions(child)
            flags.extend(sub_flags)
        elif tag == "filedependency":
            pass  # file dependencies not supported yet
        elif tag == "gamedependency":
            pass  # game version dependencies not supported yet
    return flags, operator


def _parse_plugin(node: ET.Element) -> FomodPlugin:
    """Parse a single ``<plugin>`` element."""
    name = node.get("name", "")

    desc_el = node.find("description")
    description = (desc_el.text or "").strip() if desc_el is not None else ""

    image_el = node.find("image")
    image_path = _norm_path(image_el.get("path", "")) if image_el is not None else None

    files = _parse_files(node.find("files"))

    # Condition flags set when this plugin is selected
    condition_flags: list[tuple[str, str]] = []
    cflags_el = node.find("conditionFlags")
    if cflags_el is not None:
        for flag_el in cflags_el:
            tag = flag_el.tag.split("}")[-1].lower()
            if tag == "flag":
                condition_flags.append((
                    flag_el.get("name", ""),
                    (flag_el.text or "").strip(),
                ))

    # Type descriptor
    type_name = "Optional"
    td_el = node.find("typeDescriptor")
    if td_el is not None:
        type_el = td_el.find("type")
        if type_el is not None:
            type_name = type_el.get("name", "Optional")
        else:
            dep_type_el = td_el.find("dependencyType")
            if dep_type_el is not None:
                default_el = dep_type_el.find("defaultType")
                if default_el is not None:
                    type_name = default_el.get("name", "Optional")

    return FomodPlugin(
        name=name,
        description=description,
        image_path=image_path,
        files=files,
        condition_flags=condition_flags,
        type_name=type_name,
    )


def _parse_group(node: ET.Element) -> FomodGroup:
    """Parse a single ``<group>`` element."""
    name = node.get("name", "")
    group_type = node.get("type", "SelectAny")

    plugins: list[FomodPlugin] = []
    plugins_el = node.find("plugins")
    if plugins_el is not None:
        for plugin_el in plugins_el.findall("plugin"):
            plugins.append(_parse_plugin(plugin_el))

    return FomodGroup(name=name, group_type=group_type, plugins=plugins)


def _parse_step(node: ET.Element) -> FomodStep:
    """Parse a single ``<installStep>`` element."""
    name = node.get("name", "")

    visible_conditions = None
    visible_operator = "And"
    visible_el = node.find("visible")
    if visible_el is not None:
        visible_conditions, visible_operator = _parse_flag_conditions(visible_el)

    groups: list[FomodGroup] = []
    groups_el = node.find("optionalFileGroups")
    if groups_el is not None:
        for group_el in groups_el.findall("group"):
            groups.append(_parse_group(group_el))

    return FomodStep(
        name=name,
        groups=groups,
        visible_conditions=visible_conditions,
        visible_operator=visible_operator,
    )


# ── Public API ────────────────────────────────────────────────────────


def parse_fomod(config_path: Path) -> FomodConfig | None:
    """Parse a FOMOD ModuleConfig.xml file.

    Handles UTF-8 BOM and Windows-1252 encoding gracefully.

    Returns:
        :class:`FomodConfig`, or *None* on parse failure.
    """
    try:
        raw = config_path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("windows-1252")
        except Exception:
            print(f"fomod_parser: cannot decode {config_path}", flush=True)
            return None

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        print(f"fomod_parser: XML parse error in {config_path}: {exc}", flush=True)
        return None

    # Module name
    name_el = root.find("moduleName")
    module_name = (name_el.text or "").strip() if name_el is not None else "FOMOD Package"

    # Module image
    image_el = root.find("moduleImage")
    module_image = _norm_path(image_el.get("path", "")) if image_el is not None else None

    # Required files (always installed)
    required_files = _parse_files(root.find("requiredInstallFiles"))

    # Install steps
    steps: list[FomodStep] = []
    steps_el = root.find("installSteps")
    if steps_el is not None:
        for step_el in steps_el.findall("installStep"):
            steps.append(_parse_step(step_el))

    # Conditional file installs
    conditional: list[FomodConditionPattern] = []
    cond_el = root.find("conditionalFileInstalls")
    if cond_el is not None:
        patterns_el = cond_el.find("patterns")
        if patterns_el is not None:
            for pat in patterns_el.findall("pattern"):
                deps_el = pat.find("dependencies")
                flags, operator = _parse_flag_conditions(deps_el)
                files = _parse_files(pat.find("files"))
                conditional.append(FomodConditionPattern(
                    flags=flags,
                    operator=operator,
                    files=files,
                ))

    return FomodConfig(
        module_name=module_name,
        module_image=module_image,
        required_files=required_files,
        install_steps=steps,
        conditional_installs=conditional,
    )


def detect_fomod(temp_dir: Path) -> Path | None:
    """Check if an extracted archive contains a FOMOD installer config.

    Searches case-insensitively for ``fomod/ModuleConfig.xml``.

    Returns:
        Path to *ModuleConfig.xml*, or *None* if not found.
    """
    try:
        for item in temp_dir.iterdir():
            if item.is_dir() and item.name.lower() == "fomod":
                for f in item.iterdir():
                    if f.is_file() and f.name.lower() == "moduleconfig.xml":
                        return f
    except OSError:
        pass
    return None


def parse_fomod_info(fomod_dir: Path) -> dict[str, str]:
    """Parse ``fomod/info.xml`` for mod metadata (name, author, version).

    Returns:
        Dict with lowercase tag names as keys (e.g. ``{"name": "CBBE", ...}``).
    """
    info: dict[str, str] = {}
    try:
        for f in fomod_dir.iterdir():
            if f.name.lower() == "info.xml" and f.is_file():
                raw = f.read_bytes()
                if raw.startswith(b"\xef\xbb\xbf"):
                    raw = raw[3:]
                text = raw.decode("utf-8", errors="replace")
                root = ET.fromstring(text)
                for child in root:
                    if child.text and child.text.strip():
                        info[child.tag.lower()] = child.text.strip()
                break
    except Exception:
        pass
    return info


def resolve_path_ci(base: Path, rel_path: str) -> Path | None:
    """Resolve a relative path case-insensitively under *base*.

    FOMOD configs use Windows-style paths that may not match actual
    case on a case-sensitive Linux filesystem.

    Returns:
        Resolved :class:`Path`, or *None* if not found.
    """
    if not rel_path:
        return base

    parts = rel_path.replace("\\", "/").split("/")
    current = base

    for part in parts:
        if not part:
            continue
        part_lower = part.lower()
        found = None
        try:
            for child in current.iterdir():
                if child.name.lower() == part_lower:
                    found = child
                    break
        except OSError:
            return None
        if found is None:
            return None
        current = found

    return current


def evaluate_conditions(
    flags: list[tuple[str, str]],
    operator: str,
    current_flags: dict[str, str],
) -> bool:
    """Evaluate flag conditions against current flag state.

    Args:
        flags: ``[(flag_name, expected_value), ...]``
        operator: ``"And"`` or ``"Or"``
        current_flags: Current flag state.

    Returns:
        *True* if conditions are satisfied.
    """
    if not flags:
        return True

    results = [current_flags.get(name, "") == value for name, value in flags]
    return any(results) if operator == "Or" else all(results)


def collect_fomod_files(
    config: FomodConfig,
    selected_plugins: list[FomodPlugin],
    flags: dict[str, str],
) -> list[FomodFile]:
    """Collect all files to install based on user selections.

    Combines required files, selected plugin files, and conditional files.
    Higher-priority files take precedence at the same destination.
    """
    # destination (lower) → (FomodFile, priority)
    file_map: dict[str, tuple[FomodFile, int]] = {}

    def _add(files: list[FomodFile]) -> None:
        for f in files:
            key = f"DIR:{f.source.lower()}" if f.is_folder else f.destination.lower()
            existing = file_map.get(key)
            if existing is None or f.priority >= existing[1]:
                file_map[key] = (f, f.priority)

    _add(config.required_files)
    for plugin in selected_plugins:
        _add(plugin.files)
    for cond in config.conditional_installs:
        if evaluate_conditions(cond.flags, cond.operator, flags):
            _add(cond.files)

    return [f for f, _ in file_map.values()]


def _is_safe_path(base: Path, target: Path) -> bool:
    """Check that *target* resolves within *base* (path traversal guard)."""
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def assemble_fomod_files(source_dir: Path, files: list[FomodFile]) -> Path | None:
    """Create a temp directory with only the FOMOD-selected files.

    Args:
        source_dir: Extracted archive temp directory.
        files: List of :class:`FomodFile` objects to install.

    Returns:
        Path to new temp directory, or *None* if empty.
        Caller must clean up the returned directory.
    """
    dest = Path(tempfile.mkdtemp(prefix="anvil_fomod_"))

    # Sort by priority so higher-priority files overwrite lower
    sorted_files = sorted(files, key=lambda f: f.priority)

    for f in sorted_files:
        src = resolve_path_ci(source_dir, f.source)
        if src is None:
            continue

        if f.is_folder and src.is_dir():
            dst_dir = dest / f.destination if f.destination else dest
            # Path traversal guard (K1 fix)
            if not _is_safe_path(dest, dst_dir):
                print(f"fomod_parser: skipping unsafe folder path: {f.destination}", flush=True)
                continue
            dst_dir.mkdir(parents=True, exist_ok=True)
            for item in src.rglob("*"):
                rel = item.relative_to(src)
                target = dst_dir / rel
                if not _is_safe_path(dest, target):
                    continue
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                elif item.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)

        elif not f.is_folder and src.is_file():
            target = dest / f.destination if f.destination else dest / f.source
            # Path traversal guard (K1 fix)
            if not _is_safe_path(dest, target):
                print(f"fomod_parser: skipping unsafe file path: {f.destination}", flush=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)

    try:
        if any(dest.iterdir()):
            return dest
    except OSError:
        pass

    shutil.rmtree(dest, ignore_errors=True)
    return None
