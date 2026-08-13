"""Deploy per Overlay statt per Symlink.

Der Spielordner wird nicht beschrieben.  Er liegt als unterste, nur
lesbare Schicht in einem Kernel-Overlay; darueber die Mods, darueber
die Schreibschicht (.overwrite).  Das Einhaengen passiert beim Deploy
direkt am Spielordner -- jeder Startweg (Anvil, Steam, Verknuepfung)
sieht danach dieselbe Sicht.  Root-Rechte braucht nur der Mount selbst,
vermittelt ueber pkexec (siehe overlay_mount).
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from anvil.core.mod_deployer import DeployResult
from anvil.core.overlay_mount import (
    mount,
    mount_requirements,
    purge_mounts,
    unmount,
    write_helper,
)
from anvil.core.overlay_staging import OverlayStage
from anvil.core.translator import tr

# Dateisysteme, die overlayfs nicht als Schreibschicht akzeptiert.
_UNSUPPORTED_UPPER = {"tmpfs", "overlay", "ramfs"}


def filesystem_of(path: Path) -> str:
    """Dateisystemtyp des naechstgelegenen vorhandenen Elternverzeichnisses."""
    target = path
    while not target.exists() and target != target.parent:
        target = target.parent
    try:
        with open("/proc/mounts", encoding="utf-8") as stream:
            mounts = [line.split() for line in stream if line.strip()]
    except OSError:
        return ""
    resolved = str(target.resolve())
    best = ""
    best_len = -1
    for parts in mounts:
        if len(parts) < 3:
            continue
        point, fstype = parts[1], parts[2]
        point = point.replace("\\040", " ")
        if (resolved == point or resolved.startswith(point.rstrip("/") + "/")) \
                and len(point) > best_len:
            best, best_len = fstype, len(point)
    return best


def force_rmtree(path: Path) -> None:
    """Loescht einen Baum auch dann, wenn overlayfs ihn zugenagelt hat.

    Das Arbeitsverzeichnis bekommt vom Kernel ein Unterverzeichnis mit den
    Rechten 000.  Ohne vorheriges Aufsperren scheitert jedes normale Loeschen.
    """
    if not path.exists():
        return

    for root, dirs, _files in os.walk(path, topdown=True):
        for name in dirs:
            try:
                os.chmod(os.path.join(root, name), 0o700)
            except OSError:
                pass

    shutil.rmtree(path)


def environment_problems(
    upper_dir: Path | None = None,
    game_path: Path | None = None,
) -> list[str]:
    """Was dem Overlay auf diesem System im Weg steht.

    Leere Liste heisst: es kann losgehen.  Wird auch von den Einstellungen
    benutzt, bevor eine Instanz ueberhaupt umgestellt wird.
    """
    problems: list[str] = mount_requirements()

    if upper_dir is not None:
        fstype = filesystem_of(upper_dir)
        if fstype in _UNSUPPORTED_UPPER:
            problems.append(tr("overlay.bad_filesystem", fs=fstype))

    if game_path is not None and not game_path.is_dir():
        problems.append(tr("overlay.no_game_path", path=str(game_path)))

    return problems


class OverlayDeployer:
    """Bereitet einen Overlay-Deploy vor.

    Bedient dieselbe Schnittstelle wie der Symlink-Deployer, damit die
    Oberflaeche nicht unterscheiden muss.
    """

    MANIFEST_NAME = ".overlay_manifest.json"
    STAGE_DIR = ".overlay"

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
        redmod_path: str = "",
        needs_ba2_packing: bool = False,
        ba2_loose_paths: list[str] | None = None,
        separator_deploy_paths: dict[str, str] | None = None,
        mods_path: Path | None = None,
        profiles_path: Path | None = None,
        overwrite_path: Path | None = None,
        copy_deploy_paths: list[str] | None = None,
        keep_file_name_mods: set[str] | None = None,
        pak_load_order_prefix: bool = False,
        pak_load_order_dirs: list[str] | None = None,
        pak_load_order_extensions: list[str] | None = None,
        pak_load_order_first_wins: bool = False,
        archive_load_order_file: str = "",
        deploy_strip_prefixes: list[str] | None = None,
        deploy_anchors: list[str] | None = None,
        deploy_routes: list[dict] | None = None,
        mod_index=None,
    ) -> None:
        self._instance_path = instance_path
        self._game_path = game_path
        self._profile_name = profile_name
        self._mods_path = mods_path if mods_path is not None else instance_path / ".mods"
        self._profiles_dir = (
            profiles_path if profiles_path is not None else instance_path / ".profiles"
        )
        self._overwrite = (
            overwrite_path if overwrite_path is not None else instance_path / ".overwrite"
        )
        self._base = instance_path / self.STAGE_DIR
        self._manifest_path = instance_path / self.MANIFEST_NAME
        self._separator_deploy_paths = separator_deploy_paths or {}
        self._skipped_mods: set[str] = set()
        self._layers: dict[str, Path] = {"": self._base / "stage" / "main"}

        self._stage = OverlayStage(
            self._mods_path,
            self._profiles_dir,
            profile_name,
            data_path=data_path,
            nest_under_mod_name=nest_under_mod_name,
            multi_folder_routes=multi_folder_routes,
            direct_patterns=direct_install_patterns,
            lml_path=lml_path,
            redmod_path=redmod_path,
            separator_deploy_paths=separator_deploy_paths,
            needs_ba2_packing=needs_ba2_packing,
            ba2_loose_paths=ba2_loose_paths,
            keep_file_name_mods=keep_file_name_mods,
            pak_load_order_prefix=pak_load_order_prefix,
            pak_load_order_dirs=pak_load_order_dirs,
            pak_load_order_extensions=pak_load_order_extensions,
            pak_load_order_first_wins=pak_load_order_first_wins,
            deploy_strip_prefixes=deploy_strip_prefixes,
            deploy_anchors=deploy_anchors,
            deploy_routes=deploy_routes,
        )
        # Diese Dateien muessen echte Kopien im Spielordner sein --
        # unter Proton kommt ein Verweis nicht als gueltige DLL an.
        self._copy_deploy_paths = [
            p.replace("\\", "/") for p in (copy_deploy_paths or [])
        ]
        self._archive_load_order_file = archive_load_order_file
        self._mod_index = mod_index

    # ── Pfade ──────────────────────────────────────────────────────────

    @property
    def stage_dir(self) -> Path:
        """Die Schicht fuer den Spielordner."""
        return self._base / "stage" / "main"

    @property
    def stage_root(self) -> Path:
        return self._base / "stage"

    def stage_dirs(self) -> dict[str, Path]:
        """Zielbasis -> Schicht. Leerer Schluessel ist der Spielordner."""
        return dict(self._layers)

    @property
    def work_dir(self) -> Path:
        return self._base / "work"

    @property
    def upper_dir(self) -> Path:
        return self._overwrite

    @property
    def manifest_path(self) -> Path:
        return self._manifest_path

    @property
    def mount_conf_path(self) -> Path:
        """Mount-Angaben fuer den Startwrapper, bewusst ohne JSON."""
        return self._base / "mount.conf"

    @property
    def start_log_path(self) -> Path:
        return self._base / "start.log"

    @property
    def wrapper(self) -> Path:
        """Veraltet: der neue Weg braucht keinen Startwrapper mehr."""
        return self._instance_path / ".overlay" / "wrapper"

    # ── Schnittstelle ──────────────────────────────────────────────────

    def set_separator_deploy_paths(self, paths: dict[str, str]) -> None:
        """Eigene Zielpfade je Trenner -- auch im Staging nachziehen.

        Die Oberflaeche setzt die Pfade erst nach dem Konstruktor. Ohne das
        Nachziehen baut das Staging seine Schichten ohne sie.
        """
        self._separator_deploy_paths = dict(paths or {})
        self._stage.set_separator_deploy_paths(self._separator_deploy_paths)

    def set_skipped_mods(self, names) -> None:
        self._skipped_mods = {str(n).lower() for n in names}
        self._stage._skipped = self._skipped_mods

    def set_ba2_packing_enabled(self, enabled: bool) -> None:
        self._stage.set_ba2_packing_enabled(enabled)

    def is_direct_install(self, mod_name: str) -> bool:
        return self._stage.is_direct_install(mod_name)

    def is_deployed(self) -> bool:
        return self._manifest_path.is_file()

    def check_requirements(self) -> list[str]:
        """Was dem Overlay auf diesem System im Weg steht."""
        return environment_problems(self.upper_dir, self._game_path)

    def lowerdirs(self, deploy_base: str = "") -> list[Path]:
        """Untere Schichten fuer eine Zielbasis, hoechste Prioritaet zuerst."""
        schicht = self._layers.get(deploy_base, self.stage_dir)
        ziel = Path(deploy_base) if deploy_base else self._game_path
        return [schicht, ziel]

    def mounts(self) -> list[tuple[Path, list[Path]]]:
        """Was der Wrapper einhaengen muss: Ziel und seine unteren Schichten."""
        eintraege = []
        for basis in self._layers:
            ziel = Path(basis) if basis else self._game_path
            eintraege.append((ziel, self.lowerdirs(basis)))
        return eintraege

    def deploy(self) -> DeployResult:
        result = DeployResult()

        problems = self.check_requirements()
        if problems:
            result.success = False
            result.errors.extend(problems)
            return result

        self._migrate_from_symlinks(result)

        if self.is_deployed():
            purged = self.purge()
            if not purged.success:
                result.success = False
                result.errors.extend(purged.errors)
                return result

        for directory in (self.stage_root, self.work_dir, self.upper_dir):
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                result.success = False
                result.errors.append(f"{directory}: {exc}")
                return result

        staged = self._stage.build(self.stage_root)
        self._layers = staged.layers or {"": self.stage_dir}
        result.links_created = staged.files_linked
        result.files_copied = staged.files_copied
        result.errors.extend(staged.errors)
        if not staged.success:
            result.success = False
            return result

        if staged.mods_staged == 0:
            result.success = False
            result.errors.append("Keine aktiven Mods gefunden.")
            return result

        manifest = {
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "game_path": str(self._game_path),
            "instance_path": str(self._instance_path),
            "profile": self._profile_name,
            "mounts": [
                {"target": str(ziel), "lowerdirs": [str(p) for p in unten]}
                for ziel, unten in self.mounts()
            ],
            "upperdir": str(self.upper_dir),
            "workdir": str(self.work_dir),
            "mods_staged": staged.mods_staged,
            "files": staged.files_linked + staged.files_copied,
        }
        try:
            self._manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            self._write_mount_conf()
            write_helper(self._instance_path)
        except OSError as exc:
            result.success = False
            result.errors.append(f"Manifest schreiben: {exc}")
            return result

        ok, protokoll = mount(self._instance_path, self.mount_conf_path)
        if not ok and protokoll:
            result.success = False
            result.errors.append(tr("overlay.mount_failed", detail=protokoll))
        elif not ok:
            # Passwort-Dialog abgebrochen: die Schicht steht bereit, der
            # Mount kann beim naechsten Deploy nachgeholt werden.
            result.errors.append(tr("overlay.mount_aborted"))

        return result

    def _write_mount_conf(self) -> None:
        """Eine Zeile je Mount: Ziel, untere Schichten, Schreibschicht, Arbeit.

        Bewusst kein JSON -- der Startwrapper ist ein Shell-Skript und soll
        ohne Fremdwerkzeug auskommen.
        """
        lines = []
        for index, (ziel, unten) in enumerate(self.mounts()):
            # Nur der Hauptmount schreibt nach .overwrite. Weitere Schreib-
            # schichten duerfen nicht darin liegen -- bwrap verbietet, dass
            # eine Schreibschicht Vorfahre einer anderen ist, und der Ordner
            # taucht sonst im Spiel auf.
            upper = self.upper_dir if index == 0 else self._base / f"upper-{index}"
            work = self.work_dir / f"m{index}"
            lines.append(
                "MOUNT="
                + "|".join([
                    str(ziel),
                    ":".join(str(p) for p in unten),
                    str(upper),
                    str(work),
                ])
            )
        self.mount_conf_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _migrate_from_symlinks(self, result: DeployResult) -> None:
        """Raeumt einen alten Symlink-Deploy weg, bevor der Overlay uebernimmt.

        Laeuft nur, wenn wirklich noch ein Symlink-Manifest liegt -- sonst
        wuerde bei jedem Start der ganze Spielordner abgelaufen.
        """
        from anvil.core.mod_deployer import ModDeployer

        altes_manifest = self._instance_path / ModDeployer.MANIFEST_NAME
        if not altes_manifest.is_file():
            return

        alt = ModDeployer(
            self._instance_path,
            self._game_path,
            mods_path=self._mods_path,
            profiles_path=self._profiles_dir,
        )
        alt.purge()
        uebrig = alt.remove_orphaned_links()
        if uebrig:
            print(f"[OVERLAY] {uebrig} Symlink(s) aus dem alten Deploy entfernt", flush=True)

    def purge(self) -> DeployResult:
        """Haengt das Overlay ab und raeumt die Mod-Schicht weg."""
        result = DeployResult()

        if self.mount_conf_path.is_file():
            ok, protokoll = purge_mounts(self._instance_path, self.mount_conf_path)
            if not ok and protokoll:
                result.success = False
                result.errors.append(tr("overlay.unmount_failed", detail=protokoll))
                return result
            self.mount_conf_path.unlink(missing_ok=True)

        if self.stage_root.exists():
            try:
                force_rmtree(self.stage_root)
            except OSError as exc:
                result.success = False
                result.errors.append(f"Schicht entfernen: {exc}")

        try:
            force_rmtree(self.work_dir)
        except OSError:
            pass

        try:
            self._manifest_path.unlink(missing_ok=True)
        except OSError as exc:
            result.success = False
            result.errors.append(f"Manifest entfernen: {exc}")

        return result

    def deployed_mod_count(self) -> int:
        return int(self._read_manifest().get("mods_staged", 0))

    def deployed_link_count(self) -> int:
        return int(self._read_manifest().get("files", 0))

    def _read_manifest(self) -> dict:
        if not self._manifest_path.is_file():
            return {}
        try:
            data = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}
