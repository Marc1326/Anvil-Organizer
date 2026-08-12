"""Die Mods, die ein Autor fuer sein Preset vorausgesetzt hat.

Ein Charakter-Preset ist ohne diese Mods wertlos -- fehlt die Haar- oder
Hautmod, sieht die Figur anders aus als auf den Bildern. Nexus fuehrt diese
Liste auf der Webseite unter "Mod file requirements", die aeltere
REST-Schnittstelle kennt sie aber nicht. Ueber GraphQL ist sie zu haben,
ohne Anmeldung und ohne das Tageskontingent des Benutzers zu belasten.

Reines Python, kein Qt -- damit sich der Abruf ohne laufende Oberflaeche
pruefen laesst.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from anvil.version import APP_VERSION

ENDPOINT = "https://api.nexusmods.com/v2/graphql"

# Ueber den Domainnamen statt der Spielnummer: den kennt jedes Plugin
# ohnehin als GameNexusName, die Nummer muesste erst erfragt werden.
_QUERY = """
query($ids: [CompositeDomainWithIdInput!]!) {
  legacyModsByDomain(ids: $ids) {
    nodes {
      modId
      modRequirements {
        nexusRequirements {
          nodes { modId modName notes url externalRequirement }
        }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class Requirement:
    """Eine vorausgesetzte Mod.

    Attributes:
        mod_id:   Nexus-Nummer. 0 bei einer Voraussetzung ausserhalb von Nexus.
        name:     Anzeigename, wie der Autor ihn verlinkt hat.
        notes:    Anmerkung des Autors, z.B. "Required" oder "optional but cool".
        url:      Vollstaendige Adresse.
        external: True, wenn die Mod nicht bei Nexus liegt.
    """

    mod_id: int
    name: str
    notes: str
    url: str
    external: bool

    @property
    def required(self) -> bool:
        """Ob der Autor die Mod als zwingend bezeichnet hat.

        Es gibt kein Feld dafuer -- nur den frei getippten Text. "Required"
        ist die Vorgabe von Nexus und damit haeufig genug, um sie
        auszuwerten; alles andere gilt als freiwillig.
        """
        return self.notes.strip().lower().startswith("required")


class RequirementsError(RuntimeError):
    """Abruf fehlgeschlagen."""


def fetch(domain: str, mod_id: int, timeout: float = 20.0) -> list[Requirement]:
    """Holt die Voraussetzungen einer Mod von Nexus.

    Args:
        domain: Nexus-Kuerzel des Spiels, z.B. ``cyberpunk2077``.
        mod_id: Nexus-Nummer der Mod.

    Raises:
        RequirementsError: Netzfehler, oder die Antwort passt nicht.
    """
    rumpf = json.dumps({
        "query": _QUERY,
        "variables": {"ids": [{"gameDomain": domain, "modId": int(mod_id)}]},
    }).encode("utf-8")

    anfrage = urllib.request.Request(
        ENDPOINT,
        data=rumpf,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Ohne eigene Kennung antwortet Nexus mit 403 -- die Vorgabe
            # von urllib steht dort auf der Sperrliste.
            "User-Agent": f"Anvil Organizer/{APP_VERSION}",
        },
    )

    try:
        with urllib.request.urlopen(anfrage, timeout=timeout) as antwort:
            daten = json.loads(antwort.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise RequirementsError(str(exc)) from exc

    if daten.get("errors"):
        raise RequirementsError(str(daten["errors"][0].get("message", "")))

    return _parse(daten, domain)


def _parse(daten: dict, domain: str) -> list[Requirement]:
    knoten = (
        daten.get("data", {})
        .get("legacyModsByDomain", {})
        .get("nodes", [])
    )
    if not knoten:
        return []

    roh = (
        (knoten[0].get("modRequirements") or {})
        .get("nexusRequirements", {})
        .get("nodes", [])
    )

    ergebnis: list[Requirement] = []
    for eintrag in roh:
        extern = bool(eintrag.get("externalRequirement"))
        try:
            nummer = int(eintrag.get("modId") or 0)
        except (TypeError, ValueError):
            nummer = 0

        adresse = (eintrag.get("url") or "").strip()
        if not adresse and nummer and not extern:
            adresse = f"https://www.nexusmods.com/{domain}/mods/{nummer}"

        ergebnis.append(Requirement(
            mod_id=nummer,
            name=(eintrag.get("modName") or "").strip(),
            notes=(eintrag.get("notes") or "").strip(),
            url=adresse,
            external=extern,
        ))
    return ergebnis


# ── Zwischenspeicher ─────────────────────────────────────────────────
#
# Ohne ihn braeuchte jedes Oeffnen des Mod-Fensters das Netz. Die Liste
# aendert sich hoechstens, wenn der Autor sein Paket ueberarbeitet.


def _key(domain: str, mod_id: int) -> str:
    return f"{domain}:{mod_id}"


def load_cache(cache_path: Path, domain: str, mod_id: int) -> list[Requirement] | None:
    """Gespeicherte Liste, oder None wenn nichts vorliegt."""
    try:
        alles = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    eintrag = alles.get(_key(domain, mod_id))
    if not isinstance(eintrag, dict):
        return None

    posten = eintrag.get("items")
    if not isinstance(posten, list):
        return None

    return [
        Requirement(
            mod_id=int(p.get("mod_id", 0) or 0),
            name=str(p.get("name", "")),
            notes=str(p.get("notes", "")),
            url=str(p.get("url", "")),
            external=bool(p.get("external")),
        )
        for p in posten
        if isinstance(p, dict)
    ]


def save_cache(
    cache_path: Path, domain: str, mod_id: int, eintraege: list[Requirement],
) -> None:
    """Schreibt die Liste weg. Fehler werden geschluckt -- ohne
    Zwischenspeicher laeuft alles weiter, nur langsamer."""
    try:
        alles = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(alles, dict):
            alles = {}
    except (OSError, ValueError):
        alles = {}

    alles[_key(domain, mod_id)] = {
        "fetched": datetime.now(timezone.utc).isoformat(),
        "items": [
            {
                "mod_id": e.mod_id,
                "name": e.name,
                "notes": e.notes,
                "url": e.url,
                "external": e.external,
            }
            for e in eintraege
        ],
    }

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(alles, indent=2, ensure_ascii=False), encoding="utf-8",
        )
    except OSError:
        pass
