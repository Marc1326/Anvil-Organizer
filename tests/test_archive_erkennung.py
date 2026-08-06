"""Archive ohne Dateiendung und der Namensvorschlag dazu.

Nexus liefert ueber sein CDN Dateien aus, die nach ihrer UUID heissen
und keine Endung tragen. Sie tauchen in der Download-Liste auf, weil die
am Dateikopf erkannt wird -- alles danach hat frueher nur den Namen
angeschaut und sie deshalb liegen lassen.

Scan, Anzeige und Entpacken stehen in test_extensionless_downloads.py.
Hier geht es um die Annahme beim Ziehen und um den Namensvorschlag.
"""

from pathlib import Path

from anvil.core.mod_installer import ModInstaller, is_installable_archive

ZIP = b"PK\x03\x04" + b"\x00" * 26
SIEBEN_Z = b"7z\xbc\xaf\x27\x1c" + b"\x00" * 24
RAR = b"Rar!\x1a\x07\x00" + b"\x00" * 24


def _datei(ordner: Path, name: str, inhalt: bytes = ZIP) -> Path:
    p = ordner / name
    p.write_bytes(inhalt)
    return p


def _meta(archiv: Path, **felder: str) -> None:
    zeilen = ["[General]"] + [f"{k} = {v}" for k, v in felder.items()]
    Path(str(archiv) + ".meta").write_text("\n".join(zeilen), encoding="utf-8")


# ── Erkennung ──────────────────────────────────────────────────────────

def test_uuid_ohne_endung_gilt_als_archiv(tmp_path: Path) -> None:
    f = _datei(tmp_path, "4c85f1da-33b2-438e-9e9a-9df94039c224", SIEBEN_Z)
    assert is_installable_archive(f)


def test_alle_drei_kopfarten(tmp_path: Path) -> None:
    for i, kopf in enumerate((ZIP, SIEBEN_Z, RAR)):
        assert is_installable_archive(_datei(tmp_path, f"uuid-{i}", kopf))


def test_endung_reicht_ohne_die_datei_zu_lesen(tmp_path: Path) -> None:
    """Der Normalfall darf die Platte nicht anfassen -- canDropMimeData
    laeuft bei jeder Mausbewegung waehrend des Ziehens."""
    assert is_installable_archive(tmp_path / "gibt-es-gar-nicht.zip")


def test_zusatzendung_wird_beachtet(tmp_path: Path) -> None:
    assert is_installable_archive(tmp_path / "mod.pak", {".pak"})
    assert not is_installable_archive(tmp_path / "mod.pak")


def test_bild_ist_kein_archiv(tmp_path: Path) -> None:
    assert not is_installable_archive(_datei(tmp_path, "cover.png", b"\x89PNG\r\n\x1a\n"))


def test_datei_ohne_kopf_ist_kein_archiv(tmp_path: Path) -> None:
    assert not is_installable_archive(_datei(tmp_path, "notiz", b"Hallo Welt"))


# ── Namensvorschlag ────────────────────────────────────────────────────

def test_uuid_bekommt_den_namen_aus_der_meta(tmp_path: Path) -> None:
    mods = tmp_path / ".mods"
    mods.mkdir()
    f = _datei(tmp_path, "4c85f1da-33b2-438e-9e9a-9df94039c224", SIEBEN_Z)
    _meta(f, name="A44 Neurolink Skin")

    best, varianten = ModInstaller(tmp_path, mods_path=mods).suggest_names(f)
    assert best == "A44 Neurolink Skin"
    assert varianten[0] == "A44 Neurolink Skin"


def test_modname_schlaegt_name(tmp_path: Path) -> None:
    mods = tmp_path / ".mods"
    mods.mkdir()
    f = _datei(tmp_path, "63f9477b-f1a9-4612-92e4-ca1a5af57771", SIEBEN_Z)
    _meta(f, name="A47 Planet Diving Suit", modName="A47 Planet Diving Suit V2")

    best, _ = ModInstaller(tmp_path, mods_path=mods).suggest_names(f)
    assert best == "A47 Planet Diving Suit V2"


def test_ohne_meta_bleibt_der_dateiname(tmp_path: Path) -> None:
    mods = tmp_path / ".mods"
    mods.mkdir()
    f = _datei(tmp_path, "580ab29e-4839-4ee6-9eee-5ef78d13b3ee", SIEBEN_Z)

    best, _ = ModInstaller(tmp_path, mods_path=mods).suggest_names(f)
    assert best == "580ab29e-4839-4ee6-9eee-5ef78d13b3ee"


def test_normale_datei_nimmt_weiter_ihren_namen(tmp_path: Path) -> None:
    """Auch wenn eine .meta danebenliegt -- der Dateiname ist hier gut."""
    mods = tmp_path / ".mods"
    mods.mkdir()
    f = _datei(tmp_path, "KITSUNE Dark Panties-866-0-1-1751067882.zip")
    _meta(f, name="Irgendwas anderes")

    best, _ = ModInstaller(tmp_path, mods_path=mods).suggest_names(f)
    assert best == "KITSUNE Dark Panties"


def test_buchstabenrest_wird_verworfen() -> None:
    """"UE4SS_v3.1.0-6" ergab frueher "UE" -- die Regel bricht an der
    ersten Ziffer ab."""
    assert ModInstaller.suggest_name(Path("UE4SS_v3.1.0-6.zip")) == "UE4SS v3.1.0-6"


def test_uuid_ohne_regel_gibt_den_ganzen_namen() -> None:
    got = ModInstaller.suggest_name(Path("4c85f1da-33b2-438e-9e9a-9df94039c224"))
    assert got == "4c85f1da-33b2-438e-9e9a-9df94039c224"


def test_gute_namen_bleiben_unveraendert() -> None:
    proben = {
        "KITSUNE Dark Panties-866-0-1-1751067882.zip": "KITSUNE Dark Panties",
        "Eve Nude Natural - Skin Suit-740-1-6-0-1751728110.zip": "Eve Nude Natural - Skin Suit",
        "Menu Randomiser (No Sound)-529-1-0-1750301576.zip": "Menu Randomiser (No Sound)",
        "FOX-EYES-866-0-1-1751048809.zip": "FOX-EYES",
        "WarDress_Kitsune-866-0-1-1750908723.zip": "WarDress Kitsune",
    }
    for name, erwartet in proben.items():
        assert ModInstaller.suggest_name(Path(name)) == erwartet, name
