import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15
import "components/"

ApplicationWindow {
    id: root
    visible: true
    width: 1280
    height: 800
    minimumWidth: 1100
    minimumHeight: 700
    title: "Anvil Organizer v2"
    color: "#1a1a2e"

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        TopBar {
            Layout.fillWidth: true
            height: 50
            onPlayClicked: console.log("Play clicked")
            onSettingsClicked: console.log("Settings clicked")
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            Sidebar {
                width: 220
                Layout.fillHeight: true
                onCategorySelected: function(name) { console.log("Category:", name) }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#1a1a2e"

                Column {
                    anchors.fill: parent

                    // Mod list header
                    Rectangle {
                        width: parent.width
                        height: 44
                        color: "#1a1a2e"

                        // Bottom border
                        Rectangle {
                            width: parent.width; height: 1
                            color: "#2a2a40"; anchors.bottom: parent.bottom
                        }

                        Row {
                            anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                            spacing: 8
                            Text { text: "Mod-Liste"; color: "#ffffff"; font.pixelSize: 14; font.bold: true }
                            Text { text: "247 aktiv · 2/1 gesamt"; color: "#8080a0"; font.pixelSize: 12 }
                        }

                        Row {
                            anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
                            spacing: 4
                            Text { text: "Sortieren: Reihenfolge ▾"; color: "#8080a0"; font.pixelSize: 12 }
                        }
                    }

                    // Scrollable mod list
                    ScrollView {
                        width: parent.width
                        height: parent.height - 44
                        clip: true
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                        Column {
                            width: parent.width
                            spacing: 0

                            ModGroup {
                                width: parent.width
                                groupName: "Angel · EVB · EBB"
                                modCount: 8
                                expanded: true
                                modItems: [
                                    {name: "MESH - Hyst EBB Push Up", enabled: true, category: "Kleidung", version: "1.2.0", conflictCount: 0, isRedmod: false},
                                    {name: "Chain Halter - EBBP", enabled: true, category: "Kleidung", version: "2.1", conflictCount: 0, isRedmod: false},
                                    {name: "SCAV Netrunner Suit - Main", enabled: false, category: "Kleidung", version: "1.8", conflictCount: 0, isRedmod: false},
                                    {name: "Intern Outfit - EBBP", enabled: false, category: "Kleidung", version: "1.1", conflictCount: 0, isRedmod: false}
                                ]
                            }

                            ModGroup {
                                width: parent.width
                                groupName: "bekleidung · ebbp"
                                modCount: 12
                                expanded: true
                                modItems: [
                                    {name: "Material & Texture Override", enabled: true, category: "Grafik", version: "", conflictCount: 2, isRedmod: true},
                                    {name: "MAIN FILE - Scav Netrunner Suit", enabled: true, category: "Kleidung", version: "1.8", conflictCount: 1, isRedmod: false},
                                    {name: "Military Armor Pads - Thigh", enabled: true, category: "Rüstung", version: "3.8", conflictCount: 0, isRedmod: false},
                                    {name: "Zenitex Core Dependency", enabled: true, category: "Framework", version: "2.4", conflictCount: 0, isRedmod: false},
                                    {name: "The Community Palette Project", enabled: true, category: "Texturen", version: "1.8", conflictCount: 0, isRedmod: false}
                                ]
                            }

                            ModGroup {
                                width: parent.width
                                groupName: "Frameworks & Core"
                                modCount: 8
                                expanded: true
                                modItems: [
                                    {name: "Cyber Engine Tweaks", enabled: true, category: "Framework", version: "1.35", conflictCount: 0, isRedmod: false},
                                    {name: "RED4ext", enabled: true, category: "Framework", version: "1.27", conflictCount: 0, isRedmod: false},
                                    {name: "ArchiveXL", enabled: true, category: "Framework", version: "1.28", conflictCount: 0, isRedmod: false},
                                    {name: "redscript", enabled: true, category: "Framework", version: "0.5", conflictCount: 0, isRedmod: false}
                                ]
                            }
                        }
                    }
                }
            }

            RightPanel {
                width: 250
                Layout.fillHeight: true
            }
        }

        BottomBar {
            Layout.fillWidth: true
            height: 28
        }
    }
}
