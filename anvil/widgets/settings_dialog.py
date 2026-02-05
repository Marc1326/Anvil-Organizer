"""Einstellungen — QDialog (Platzhalter)."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QGroupBox,
    QComboBox,
    QCheckBox,
    QPushButton,
    QScrollArea,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QFormLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QSpinBox,
)
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt

_SETTINGS_DIALOG_STYLE = """
QDialog, QWidget { background: #1C1C1C; color: #D3D3D3; border: none; }
QTabWidget::pane {
    background: #1C1C1C;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
}
QTabBar::tab { background: #242424; color: #D3D3D3; padding: 8px 16px; margin-right: 2px; }
QTabBar::tab:selected { background: #3D3D3D; }
QGroupBox {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
    font-weight: bold;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QComboBox, QPushButton {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 4px;
}
QTableWidget {
    background: #1C1C1C;
    color: #D3D3D3;
    gridline-color: #3D3D3D;
}
QTableWidget::item { padding: 4px; }
"""


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setMinimumSize(560, 520)
        self.setStyleSheet(_SETTINGS_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        tabs = QTabWidget()

        # Tab Allgemein
        allgemein = QWidget()
        ag_layout = QVBoxLayout(allgemein)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: #1C1C1C; }")
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Gruppe Sprache
        lang_grp = QGroupBox("Sprache")
        lang_layout = QVBoxLayout(lang_grp)
        lang_combo = QComboBox()
        lang_combo.addItem("Deutsch (Deutschland)")
        lang_layout.addWidget(lang_combo)
        scroll_layout.addWidget(lang_grp)

        # Gruppe Download Liste
        dl_grp = QGroupBox("Download Liste")
        dl_layout = QVBoxLayout(dl_grp)
        dl_layout.addWidget(QCheckBox("Zeige Meta Informationen"))
        dl_layout.addWidget(QCheckBox("Kompakte Liste"))
        dl_layout.addWidget(QCheckBox("Verstecke Downloads nach Installation"))
        scroll_layout.addWidget(dl_grp)

        # Gruppe Updates
        up_grp = QGroupBox("Updates")
        up_layout = QVBoxLayout(up_grp)
        cb_updates = QCheckBox("Auf Updates prüfen")
        cb_updates.setChecked(True)
        up_layout.addWidget(cb_updates)
        cb_beta = QCheckBox("Update auf Beta Version")
        cb_beta.setChecked(False)
        up_layout.addWidget(cb_beta)
        scroll_layout.addWidget(up_grp)

        # Gruppe Profil-Standardeinstellungen
        prof_grp = QGroupBox("Profil-Standardeinstellungen")
        prof_layout = QVBoxLayout(prof_grp)
        for label in ("Lokale INIs", "Lokale Spielstände", "Automatische Archiv Invalidierung"):
            cb = QCheckBox(label)
            cb.setChecked(True)
            prof_layout.addWidget(cb)
        scroll_layout.addWidget(prof_grp)

        # Gruppe Sonstiges
        misc_grp = QGroupBox("Sonstiges")
        misc_layout = QVBoxLayout(misc_grp)
        misc_layout.addWidget(QCheckBox("Dialoge immer zentrieren"))
        cb_inst = QCheckBox("Bestätigung beim Ändern der Instanz anzeigen")
        cb_inst.setChecked(True)
        misc_layout.addWidget(cb_inst)
        cb_alt = QCheckBox("Zeigt beim drücken von ALT die Menüleiste")
        cb_alt.setChecked(True)
        misc_layout.addWidget(cb_alt)
        cb_preview = QCheckBox("Öffnen Sie die Vorschau per Doppelklick")
        cb_preview.setChecked(True)
        misc_layout.addWidget(cb_preview)
        scroll_layout.addWidget(misc_grp)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        ag_layout.addWidget(scroll)
        tabs.addTab(allgemein, "Allgemein")

        # Tab Style
        style_tab = QWidget()
        style_layout = QVBoxLayout(style_tab)
        stil_grp = QGroupBox("Stil")
        stil_layout = QHBoxLayout(stil_grp)
        stil_combo = QComboBox()
        stil_combo.addItem("1809 Dark Mode")
        stil_layout.addWidget(stil_combo)
        stil_layout.addWidget(QPushButton("Erkunden"))
        style_layout.addWidget(stil_grp)
        farben_grp = QGroupBox("Farben")
        farben_layout = QVBoxLayout(farben_grp)
        color_table = QTableWidget(6, 4)
        color_table.setHorizontalHeaderLabels(
            ["Beschreibung", "Text-Button", "Icons", "Farbiger Hintergrund"]
        )
        color_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        _rows = [
            ("Wird überschrieben (lose Dateien)", "#2d5a2d"),   # grün
            ("Überschreibt (lose Dateien)", "#5a2020"),         # dunkelrot
            ("Wird überschrieben (Archive)", "#006868"),         # teal
            ("Überschreibt (Archive)", "#5a2020"),               # dunkelrot
            ("Mod enthält ausgewähltes Plugin", "#4a2d5a"),      # lila
            ("Plugin ist in ausgewähltem Mod enthalten", "#1a3a5a"),  # blau
        ]
        for row, (desc, bg_hex) in enumerate(_rows):
            color_table.setItem(row, 0, QTableWidgetItem(desc))
            color_table.setCellWidget(row, 1, QPushButton("Text"))
            color_table.setItem(row, 2, QTableWidgetItem(""))
            bg_item = QTableWidgetItem("")
            bg_item.setBackground(QColor(bg_hex))
            color_table.setItem(row, 3, bg_item)
        farben_layout.addWidget(color_table)
        style_layout.addWidget(farben_grp)
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_row.addWidget(QPushButton("Farben zurücksetzen"))
        reset_row.addStretch()
        style_layout.addLayout(reset_row)
        tabs.addTab(style_tab, "Style")

        # Tab Mod Liste
        modliste_tab = QWidget()
        ml_layout = QVBoxLayout(modliste_tab)
        cb_scroll = QCheckBox("Farbe der Trenner der Modliste in der Bildlaufleiste anzeigen")
        cb_scroll.setChecked(True)
        ml_layout.addWidget(cb_scroll)
        cb_outer = QCheckBox("Zeige Mods die außerhalb von AO installiert wurden")
        cb_outer.setChecked(True)
        ml_layout.addWidget(cb_outer)
        cb_filter = QCheckBox("Merke ausgewählte Filter nachdem der Anvil Organizer neu gestartet wurde")
        cb_filter.setChecked(False)
        ml_layout.addWidget(cb_filter)
        cb_upd = QCheckBox("Überprüfe auf Updates nach dem Installieren einer Mod")
        cb_upd.setChecked(True)
        ml_layout.addWidget(cb_upd)
        cb_collapse = QCheckBox("Automatisches Einklappen von Objekten beim Ziehen mit dem Mauszeiger")
        cb_collapse.setChecked(False)
        ml_layout.addWidget(cb_collapse)
        sep_grp = QGroupBox("Zusammenklappbare Trenner")
        sep_layout = QVBoxLayout(sep_grp)
        sort_row = QHBoxLayout()
        sort_row.addWidget(QLabel("Aktiviere wenn sortiert wird bei"))
        cb_asc = QCheckBox("aufsteigende Priorität")
        cb_asc.setChecked(True)
        cb_desc = QCheckBox("absteigende Priorität")
        cb_desc.setChecked(True)
        sort_row.addWidget(cb_asc)
        sort_row.addWidget(cb_desc)
        sort_row.addStretch()
        sep_layout.addLayout(sort_row)
        conflict_row = QHBoxLayout()
        conflict_row.addWidget(QLabel("Zeige Konflikte und Plugins"))
        cb_auf = QCheckBox("auf Trenner")
        cb_auf.setChecked(True)
        cb_von = QCheckBox("Von Trenner")
        cb_von.setChecked(True)
        conflict_row.addWidget(cb_auf)
        conflict_row.addWidget(cb_von)
        conflict_row.addStretch()
        sep_layout.addLayout(conflict_row)
        symbol_row = QHBoxLayout()
        symbol_row.addWidget(QLabel("Zeige Symbole auf Trenner"))
        for lbl in ("Konflikte", "Flaggen", "Inhalt", "Version"):
            cb = QCheckBox(lbl)
            cb.setChecked(True)
            symbol_row.addWidget(cb)
        symbol_row.addStretch()
        sep_layout.addLayout(symbol_row)
        ml_layout.addWidget(sep_grp)
        cb_profil = QCheckBox("Profil-abhängiger eingeklappter Zustand für Trenner")
        cb_profil.setChecked(False)
        ml_layout.addWidget(cb_profil)
        ml_layout.addStretch()
        tabs.addTab(modliste_tab, "Mod Liste")

        # Tab Pfade
        pfade_tab = QWidget()
        pf_layout = QVBoxLayout(pfade_tab)
        pf_scroll = QScrollArea()
        pf_scroll.setWidgetResizable(True)
        pf_scroll.setFrameShape(QFrame.Shape.NoFrame)
        pf_scroll.setStyleSheet("QScrollArea { border: none; background: #1C1C1C; }")
        pf_content = QWidget()
        pf_content_layout = QVBoxLayout(pf_content)

        def add_path_row(form, label, text_or_placeholder, is_placeholder=True):
            le = QLineEdit()
            if is_placeholder:
                le.setPlaceholderText(text_or_placeholder)
            else:
                le.setText(text_or_placeholder)
            row = QHBoxLayout()
            row.addWidget(le)
            row.addWidget(QPushButton("..."))
            form.addRow(label, row)

        pf_form = QFormLayout()
        add_path_row(pf_form, "Basisverzeichnis:", "~/.local/share/AnvilOrganizer/Cyberpunk 2077", False)
        add_path_row(pf_form, "Downloads:", "~/Downloads/Mods", False)
        add_path_row(pf_form, "Mods:", "%BASE_DIR%/mods", False)
        add_path_row(pf_form, "Caches:", "%BASE_DIR%/webcache", False)
        add_path_row(pf_form, "Profile:", "%BASE_DIR%/profiles", False)
        add_path_row(pf_form, "Overwrite:", "%BASE_DIR%/overwrite", False)
        pf_content_layout.addLayout(pf_form)
        pf_content_layout.addWidget(QLabel("Verwenden Sie %BASE_DIR%, um auf das Basisverzeichnis zu verweisen."))
        pf_content_layout.addSpacing(16)
        pf_game_form = QFormLayout()
        add_path_row(pf_game_form, "Verwaltetes Spiel:", "~/.local/share/Steam/steamapps/common/Cyberpunk 2077/bin/x64/Cyberpunk2077", False)
        pf_content_layout.addLayout(pf_game_form)
        pf_content_layout.addStretch()
        pf_content_layout.addWidget(QLabel("Alle Verzeichnisse müssen beschreibbar sein."))
        pf_scroll.setWidget(pf_content)
        pf_layout.addWidget(pf_scroll)
        tabs.addTab(pfade_tab, "Pfade")

        # Tab Nexus
        nexus_tab = QWidget()
        nx_layout = QVBoxLayout(nexus_tab)
        nx_scroll = QScrollArea()
        nx_scroll.setWidgetResizable(True)
        nx_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nx_scroll.setStyleSheet("QScrollArea { border: none; background: #1C1C1C; }")
        nx_content = QWidget()
        nx_content_layout = QVBoxLayout(nx_content)

        konto_grp = QGroupBox("Nexus-Konto")
        konto_layout = QHBoxLayout(konto_grp)
        konto_left = QFormLayout()
        uid = QLineEdit("195810152")
        uid.setReadOnly(True)
        konto_left.addRow("User ID:", uid)
        name_edit = QLineEdit("Platzhalter")
        name_edit.setReadOnly(True)
        konto_left.addRow("Name:", name_edit)
        konto_edit = QLineEdit("Premium")
        konto_edit.setReadOnly(True)
        konto_left.addRow("Konto:", konto_edit)
        konto_layout.addLayout(konto_left)
        konto_layout.addSpacing(24)
        stats = QFormLayout()
        daily = QLineEdit("20000/20000")
        daily.setReadOnly(True)
        stats.addRow("Tägliche Anfragen:", daily)
        hourly = QLineEdit("500/500")
        hourly.setReadOnly(True)
        stats.addRow("Stündliche Anfragen:", hourly)
        konto_layout.addLayout(stats)
        nx_content_layout.addWidget(konto_grp)

        verb_grp = QGroupBox("Nexus-Verbindung")
        verb_layout = QVBoxLayout(verb_grp)
        verb_row1 = QHBoxLayout()
        btn_connect = QPushButton("Verbinde zu Nexus")
        btn_connect.setEnabled(False)
        verb_row1.addWidget(btn_connect)
        verb_row1.addWidget(QLabel("Verbunden."))
        verb_row1.addStretch()
        verb_layout.addLayout(verb_row1)
        verb_row2 = QHBoxLayout()
        btn_api = QPushButton("Gebe API-Schlüssel manuell ein")
        btn_api.setEnabled(False)
        verb_row2.addWidget(btn_api)
        btn_disconnect = QPushButton("Trennen Sie die Verbindung zum Nexus 🤝")
        verb_row2.addWidget(btn_disconnect)
        verb_row2.addStretch()
        verb_layout.addLayout(verb_row2)
        nx_content_layout.addWidget(verb_grp)

        opt_grp = QGroupBox("Optionen")
        opt_layout = QHBoxLayout(opt_grp)
        opt_left = QVBoxLayout()
        for lbl, checked in (
            ("Endorsement Integration", True),
            ("Integration zur Beobachtung von Mods", True),
            ("Nexus-Kategoriezuordnungen verwenden", True),
            ("API-Anforderungszähler ausblenden", False),
        ):
            cb = QCheckBox(lbl)
            cb.setChecked(checked)
            opt_left.addWidget(cb)
        opt_layout.addLayout(opt_left)
        opt_right = QVBoxLayout()
        opt_right.addWidget(QPushButton("Mit MOD MANAGER DOWNLOAD-Links verknüpfen"))
        opt_right.addWidget(QPushButton("Cache leeren"))
        opt_right.addStretch()
        opt_layout.addLayout(opt_right)
        nx_content_layout.addWidget(opt_grp)

        server_grp = QGroupBox("Server")
        server_layout = QHBoxLayout(server_grp)
        known_lbl = QLabel("Bekannte Server (aktualisiert bei Download)")
        server_left = QVBoxLayout()
        server_left.addWidget(known_lbl)
        known_list = QListWidget()
        for city in ("Amsterdam", "Prague", "Chicago", "Los Angeles", "Miami", "Dallas"):
            known_list.addItem(QListWidgetItem(city))
        server_left.addWidget(known_list)
        server_layout.addLayout(server_left)
        pref_lbl = QLabel("Bevorzugte Server (Drag & Drop)")
        server_right = QVBoxLayout()
        server_right.addWidget(pref_lbl)
        pref_list = QListWidget()
        pref_list.addItem(QListWidgetItem("Nexus CDN (58.45 MB/s)"))
        server_right.addWidget(pref_list)
        server_layout.addLayout(server_right)
        nx_content_layout.addWidget(server_grp)

        nx_content_layout.addStretch()
        nx_scroll.setWidget(nx_content)
        nx_layout.addWidget(nx_scroll)
        tabs.addTab(nexus_tab, "Nexus")

        # Tab Plugins
        plugins_tab = QWidget()
        pl_layout = QHBoxLayout(plugins_tab)
        pl_left = QVBoxLayout()
        pl_tree = QTreeWidget()
        pl_tree.setHeaderLabels(["Plugin"])
        pl_tree.setMinimumWidth(260)
        diag = QTreeWidgetItem(pl_tree, ["Diagnose"])
        basic = QTreeWidgetItem(diag, ["Basic diagnosis plugin"])
        pl_tree.setCurrentItem(basic)
        form43 = QTreeWidgetItem(diag, ["Form 43 Plugin Checker"])
        _italic_font = QFont()
        _italic_font.setItalic(True)
        form43.setFont(0, _italic_font)
        script_ext = QTreeWidgetItem(diag, ["Script Extender Plugin Lade-Überprüfer"])
        script_ext.setFont(0, _italic_font)
        file_mapper = QTreeWidgetItem(pl_tree, ["File Mapper"])
        QTreeWidgetItem(file_mapper, ["INI Verwaltung"])
        game = QTreeWidgetItem(pl_tree, ["Game"])
        QTreeWidgetItem(game, ["Cyberpunk 2077 Support Plugin"])
        QTreeWidgetItem(game, ["Weitere Platzhalter 1"])
        QTreeWidgetItem(game, ["Weitere Platzhalter 2"])
        pl_left.addWidget(pl_tree)
        pl_filter = QLineEdit()
        pl_filter.setPlaceholderText("Filter")
        pl_left.addWidget(pl_filter)
        pl_layout.addLayout(pl_left)
        pl_right = QVBoxLayout()
        pl_detail = QFormLayout()
        pl_detail.addRow("Autor:", QLineEdit("Tannin"))
        pl_detail.addRow("Version:", QLineEdit("1.1.3.0"))
        pl_detail.addRow("Beschreibung:", QLineEdit("Prüft auf Probleme, die nicht im Zusammenhang mit anderen Plugins stehen."))
        pl_cb_active = QCheckBox("Aktiviert")
        pl_cb_active.setChecked(True)
        pl_detail.addRow(pl_cb_active)
        pl_right.addLayout(pl_detail)
        pl_table = QTableWidget(9, 2)
        pl_table.setHorizontalHeaderLabels(["Key", "Value"])
        pl_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        _pl_rows = [
            ("check_alternategames", "false"),
            ("check_conflict", "true"),
            ("check_errorlog", "true"),
            ("check_fileattributes", "false"),
            ("check_font", "true"),
            ("check_missingmasters", "true"),
            ("check_overwrite", "true"),
            ("ow_ignore_empty", "false"),
            ("ow_ignore_log", "false"),
        ]
        for row, (k, v) in enumerate(_pl_rows):
            pl_table.setItem(row, 0, QTableWidgetItem(k))
            pl_table.setItem(row, 1, QTableWidgetItem(v))
        pl_right.addWidget(pl_table)
        pl_right.addWidget(QLabel("Gesperrte Plugins (<entf> drücken um Plugins von dieser Liste zu entfernen):"))
        pl_blocked_list = QListWidget()
        pl_right.addWidget(pl_blocked_list)
        pl_layout.addLayout(pl_right, 1)
        tabs.addTab(plugins_tab, "Plugins")

        # Tab Workarounds
        workarounds_tab = QWidget()
        wa_layout = QVBoxLayout(workarounds_tab)
        wa_scroll = QScrollArea()
        wa_scroll.setWidgetResizable(True)
        wa_scroll.setFrameShape(QFrame.Shape.NoFrame)
        wa_scroll.setStyleSheet("QScrollArea { border: none; background: #1C1C1C; }")
        wa_content = QWidget()
        wa_content_layout = QVBoxLayout(wa_content)
        opt_wa_grp = QGroupBox("Optionen")
        opt_wa_layout = QVBoxLayout(opt_wa_grp)
        cb_load = QCheckBox("Laden von benötigten Spieldateien erzwingen")
        cb_load.setChecked(True)
        opt_wa_layout.addWidget(cb_load)
        cb_arch = QCheckBox("Aktiviere Archiv Parsing (experimentell)")
        cb_arch.setChecked(False)
        opt_wa_layout.addWidget(cb_arch)
        cb_lock = QCheckBox("Sperre das GUI, wenn das Spiel ausgeführt wird")
        cb_lock.setChecked(True)
        opt_wa_layout.addWidget(cb_lock)
        wa_content_layout.addWidget(opt_wa_grp)
        steam_grp = QGroupBox("Steam")
        steam_layout = QFormLayout(steam_grp)
        steam_layout.addRow("Steam AppID:", QLineEdit("1091500"))
        steam_layout.addRow("Nutzername:", QLineEdit())
        steam_layout.addRow("Kennwort:", QLineEdit())
        wa_content_layout.addWidget(steam_grp)
        net_grp = QGroupBox("Netzwerk")
        net_layout = QVBoxLayout(net_grp)
        net_layout.addWidget(QCheckBox("Offline Modus"))
        net_layout.addWidget(QCheckBox("Nutze Systems HTTP Proxy"))
        browser_row = QHBoxLayout()
        cb_browser = QCheckBox("Benutzerdefinierter Browser")
        cb_browser.setChecked(False)
        browser_row.addWidget(cb_browser)
        browser_row.addWidget(QLineEdit())
        browser_row.addWidget(QPushButton("..."))
        net_layout.addLayout(browser_row)
        wa_content_layout.addWidget(net_grp)
        btn_row_wa = QHBoxLayout()
        btn_row_wa.addWidget(QPushButton("Fenstergeometrien zurücksetzen"))
        btn_row_wa.addWidget(QPushButton("BSAs zurückdatieren"))
        btn_row_wa.addWidget(QPushButton("Anwendungen Blockliste"))
        btn_row_wa.addWidget(QPushButton("Datei-Endungen überspringen"))
        btn_row_wa.addWidget(QPushButton("Verzeichnisse überspringen"))
        wa_content_layout.addLayout(btn_row_wa)
        wa_content_layout.addStretch()
        wa_content_layout.addWidget(QLabel("Dies sind Workarounds für Probleme mit Anvil Organizer. Bitte lesen Sie unbedingt die Hilfetexte bevor Sie hier etwas ändern."))
        wa_scroll.setWidget(wa_content)
        wa_layout.addWidget(wa_scroll)
        tabs.addTab(workarounds_tab, "Workarounds")

        # Tab Diagnose
        diagnose_tab = QWidget()
        diag_layout = QVBoxLayout(diagnose_tab)
        diag_scroll = QScrollArea()
        diag_scroll.setWidgetResizable(True)
        diag_scroll.setFrameShape(QFrame.Shape.NoFrame)
        diag_scroll.setStyleSheet("QScrollArea { border: none; background: #1C1C1C; }")
        diag_content = QWidget()
        diag_content_layout = QVBoxLayout(diag_content)
        logs_grp = QGroupBox("Logs und Abstürze")
        logs_layout = QFormLayout(logs_grp)
        log_combo = QComboBox()
        log_combo.addItem("Info (empfohlen)")
        logs_layout.addRow("Log Stufe:", log_combo)
        crash_combo = QComboBox()
        crash_combo.addItem("Mini (empfohlen)")
        logs_layout.addRow("Absturzabbildung:", crash_combo)
        crash_spin = QSpinBox()
        crash_spin.setValue(5)
        logs_layout.addRow("Maximale Absturzabbilder zu behalten:", crash_spin)
        diag_content_layout.addWidget(logs_grp)
        loot_grp = QGroupBox("Integriertes LOOT")
        loot_layout = QFormLayout(loot_grp)
        loot_combo = QComboBox()
        loot_combo.addItem("Info (empfohlen)")
        loot_layout.addRow("LOOT Log Stufe:", loot_combo)
        diag_content_layout.addWidget(loot_grp)
        diag_hint = QLabel(
            "Protokolle und Absturzabbilder werden unter Ihrer aktuellen Instanz in den Verzeichnissen logs und crashDumps gespeichert. "
            "Das Senden von Protokollen und/oder Absturzabbildern an die Entwickler kann bei der Untersuchung von Problemen hilfreich sein. "
            "Es wird empfohlen, vor dem Senden große Protokoll- und DMP-Dateien zu komprimieren."
        )
        diag_hint.setWordWrap(True)
        diag_content_layout.addWidget(diag_hint)
        diag_content_layout.addStretch()
        diag_scroll.setWidget(diag_content)
        diag_layout.addWidget(diag_scroll)
        tabs.addTab(diagnose_tab, "Diagnose")

        layout.addWidget(tabs)

        # Unten: Buttons
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(QPushButton("Dialogoptionen zurücksetzen"))
        bottom_row.addWidget(QPushButton("Mod Kategorien anpassen"))
        bottom_row.addStretch()
        layout.addLayout(bottom_row)

        # Unten rechts: OK, Abbrechen
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)
