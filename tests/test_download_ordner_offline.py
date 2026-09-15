"""Downloads landen nie im Ordner einer anderen Instanz.

Liegt der Speicher einer Instanz auf einem nicht eingehaengten Laufwerk,
bricht der Instanzwechsel frueh ab. Der DownloadManager zeigte danach weiter
auf den Download-Ordner der vorigen Instanz.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from anvil.core.download_manager import DownloadManager


def test_ohne_ziel_werden_downloads_abgelehnt(tmp_path):
    QApplication.instance() or QApplication([])
    dm = DownloadManager()
    dm.set_downloads_dir(tmp_path / "Downloads")
    dm.clear_downloads_dir()

    assert dm.downloads_dir() is None
    assert dm.enqueue(url="https://example.invalid/a.zip", file_name="a.zip") == -1
    assert list((tmp_path / "Downloads").iterdir()) == []


def test_offline_instanz_uebernimmt_keinen_fremden_download_ordner(hauptfenster_prozess, tmp_path):
    fehlt = tmp_path / "nicht-eingehaengt"
    ergebnis = hauptfenster_prozess(f"""
        from pathlib import Path
        from PySide6.QtCore import QSettings

        fenster.plugin_loader.get_game = lambda kurz: None
        basis = fenster.instance_manager.instances_path()
        fehlt = Path({str(fehlt)!r})

        def instanz(name, pfade):
            ordner = basis / name
            for unter in (".mods", ".downloads", ".profiles/Default", ".overwrite"):
                (ordner / unter).mkdir(parents=True, exist_ok=True)
            ini = QSettings(str(ordner / ".anvil.ini"), QSettings.Format.IniFormat)
            ini.beginGroup("General")
            ini.setValue("game_name", name)
            ini.setValue("game_short_name", "probe")
            ini.setValue("selected_profile", "Default")
            ini.endGroup()
            ini.beginGroup("Paths")
            for schluessel, wert in pfade.items():
                ini.setValue(schluessel, wert)
            ini.endGroup()
            ini.sync()
            return ordner

        a = instanz("A", {{}})
        offline = instanz("Offline", {{
            "mods_directory": str(fehlt / "Mods"),
            "downloads_directory": str(fehlt / "Downloads"),
        }})
        nur_mods = instanz("NurMods", {{"mods_directory": str(fehlt / "Mods")}})

        dm = fenster._game_panel.download_manager()
        ergebnis["a"] = [fenster._apply_instance("A"), str(dm.downloads_dir())]
        ergebnis["offline"] = [fenster._apply_instance("Offline"), dm.downloads_dir() is None,
                               fehlt.exists()]
        fenster._apply_instance("A")
        ergebnis["nur_mods"] = [fenster._apply_instance("NurMods"), str(dm.downloads_dir()),
                                fehlt.exists()]
        ergebnis["pfade"] = [str(a / ".downloads"), str(nur_mods / ".downloads")]
    """)
    a_downloads, nur_mods_downloads = ergebnis["pfade"]
    assert ergebnis["a"][1] == a_downloads
    # Downloads-Ordner fehlt: kein Ziel, nichts unter dem Mountpunkt angelegt
    assert ergebnis["offline"] == [False, True, False]
    # Nur die Mods fehlen: Downloads gehen in den eigenen Ordner
    assert ergebnis["nur_mods"] == [False, nur_mods_downloads, False]


def test_abgelehnter_download_meldet_fehlenden_ordner(hauptfenster_prozess):
    ergebnis = hauptfenster_prozess("""
        from types import SimpleNamespace

        dm = fenster._game_panel.download_manager()
        dm.clear_downloads_dir()
        nxm = SimpleNamespace(game="probe", mod_id=7, file_id=9)
        fenster._pending_nxm_links = {(7, 9): {"nxm": nxm, "mod_name": "M", "mod_version": "1"}}
        fenster._on_nexus_response(
            "download_link:probe:7:9", [{"URI": "https://example.invalid/datei.zip"}])
        ergebnis["meldung"] = fenster.statusBar().currentMessage()
        ergebnis["erwartet"] = tr("status.no_downloads_folder")
        ergebnis["offen"] = list(fenster._pending_nxm_links)
    """)
    assert ergebnis["meldung"] == ergebnis["erwartet"]
    assert ergebnis["offen"] == []
