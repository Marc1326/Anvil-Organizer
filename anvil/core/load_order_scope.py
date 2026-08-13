"""Wofuer die Reihenfolge in der Mod-Liste im Spiel tatsaechlich gilt.

Oben in der Liste bedeutet hoechste Prioritaet. Bei losen Dateien stimmt
das immer -- der Deployer rollt von der schwaechsten zur staerksten Mod
aus, die letzte gewinnt.

Bei gepackten Archiven haengt es am Spiel. Die Engines lesen die
Mod-Liste nicht; dort entscheidet der Dateiname. Anvil kann das
ausgleichen, indem es beim Ausrollen durchnummeriert -- aber nur, wo das
geprueft ist. Ueberall sonst geht die Reihenfolge fuer Archive verloren,
und bisher sagte die Oberflaeche das nirgends.

Dieses Modul beantwortet die Frage an einer Stelle, damit Spaltenkopf,
Hinweiszeile, Konflikt-Anzeige und Diagnose-Bericht nicht
auseinanderlaufen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Fuer alle Dateien, unabhaengig vom Ordner.
VOLL = "voll"
# Nur in bestimmten Ordnern.
TEILWEISE = "teilweise"
# Nirgends -- nur lose Dateien folgen der Liste.
KEINE = "keine"


@dataclass(frozen=True)
class OrderScope:
    """Was die Reihenfolge bei diesem Spiel bewirkt."""

    art: str = KEINE
    # Ordner, in denen Anvil durchnummeriert.
    ordner: list[str] = field(default_factory=list)
    # Mod-Ordner des Spiels, die NICHT dabei sind.
    rest: list[str] = field(default_factory=list)
    # Bethesda: Plugins haben ihre eigene Reihenfolge.
    eigene_plugin_liste: bool = False

    @property
    def archive_folgen_der_liste(self) -> bool:
        """True, wenn gepackte Dateien wenigstens teilweise folgen."""
        return self.art in (VOLL, TEILWEISE)


def _liste(wert) -> list[str]:
    if not wert:
        return []
    return [str(e).replace("\\", "/").strip("/") for e in wert if str(e).strip()]


def scope_for(plugin) -> OrderScope:
    """Liest die Einstufung aus einem Spiel-Plugin.

    Nimmt Klasse wie Instanz. Ohne Plugin gilt die vorsichtige Annahme:
    es wird nicht nummeriert.
    """
    if plugin is None:
        return OrderScope()

    ordner = _liste(getattr(plugin, "GamePakLoadOrderDirs", []))
    prefix = bool(getattr(plugin, "GamePakLoadOrderPrefix", False))
    mod_ordner = _liste(getattr(plugin, "GameModDirs", []))
    bethesda = getattr(plugin, "PluginLoadOrderFormat", "") == "asterisk"

    if ordner:
        # Ein Mod-Ordner gilt als abgedeckt, wenn er selbst freigegeben
        # ist oder unterhalb eines freigegebenen liegt.
        def abgedeckt(m: str) -> bool:
            unten = m.lower()
            return any(unten == o.lower() or unten.startswith(o.lower() + "/")
                       for o in ordner)

        return OrderScope(
            art=TEILWEISE,
            ordner=ordner,
            rest=[m for m in mod_ordner if not abgedeckt(m)],
            eigene_plugin_liste=bethesda,
        )

    if prefix:
        return OrderScope(art=VOLL, eigene_plugin_liste=bethesda)

    return OrderScope(art=KEINE, rest=mod_ordner,
                      eigene_plugin_liste=bethesda)


def scope_saetze(scope: OrderScope) -> list[str]:
    """Die Erklaerung als einzelne Saetze, uebersetzt.

    Spaltenkopf, Hinweiszeile und Diagnose setzen sich daraus zusammen --
    so kann keine der drei Stellen etwas anderes behaupten.
    """
    from anvil.core.translator import tr

    saetze: list[str] = []
    if scope.art == VOLL:
        saetze.append(tr("order_scope.numbered_all"))
    elif scope.art == TEILWEISE:
        saetze.append(
            tr("order_scope.numbered_dirs", dirs=", ".join(scope.ordner)),
        )
        if scope.rest:
            saetze.append(
                tr("order_scope.numbered_rest", rest=", ".join(scope.rest)),
            )
    else:
        saetze.append(tr("order_scope.not_numbered"))

    if scope.eigene_plugin_liste:
        saetze.append(tr("order_scope.bethesda_plugins"))
    return saetze


def scope_tooltip(plugin) -> str:
    """Text fuer den Spaltenkopf „Prioritaet"."""
    from anvil.core.translator import tr

    scope = scope_for(plugin)
    return "\n".join([tr("order_scope.tooltip_head")] + scope_saetze(scope))
