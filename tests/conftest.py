"""Tests laufen ohne sichtbare Fenster.

Mehrere Tests bauen echte Qt-Widgets und rufen show(). Ohne diese Zeile
poppen sie waehrend der Suite auf dem Desktop auf und stoeren die Arbeit.
Zum Debuggen mit sichtbaren Fenstern: ANVIL_TEST_SHOW_WINDOWS=1 setzen.
"""

import os

if os.environ.get("ANVIL_TEST_SHOW_WINDOWS") != "1":
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
