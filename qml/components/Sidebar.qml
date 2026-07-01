import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root
    width: 220
    color: "#131325"
    clip: true

    signal categorySelected(string name)
    signal filterChanged(string filter, bool enabled)

    Column {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 0

        // Search Box
        Rectangle {
            width: parent.width
            height: 32
            color: "#252538"
            radius: 6
            bottomPadding: 0

            Row {
                anchors.left: parent.left
                anchors.leftMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6

                Text {
                    text: "⌕"
                    color: "#8080a0"
                    font.pixelSize: 14
                }
                Text {
                    text: "Suchen..."
                    color: "#606070"
                    font.pixelSize: 13
                }
            }
        }

        Item { width: parent.width; height: 12 }

        // Section header EIGENSCHAFTEN
        Text {
            text: "EIGENSCHAFTEN"
            color: "#6060a0"
            font.pixelSize: 10
            topPadding: 4
            bottomPadding: 4
        }

        // Filter Rows
        Repeater {
            model: [
                {icon: "✓", label: "Aktiviert",   iconColor: "#4caf50"},
                {icon: "",  label: "Deaktiviert", iconColor: "#8080a0"},
                {icon: "△", label: "Konflikte",   iconColor: "#e8a000"},
                {icon: "★", label: "Endorsed",    iconColor: "#8080a0"},
                {icon: "",  label: "Notizen",     iconColor: "#8080a0"}
            ]

            delegate: Rectangle {
                width: parent.width
                height: 28
                radius: 4
                color: filterHovered ? "#252538" : "transparent"

                property bool filterHovered: false

                Row {
                    anchors.left: parent.left
                    anchors.leftMargin: 6
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 6

                    Text {
                        text: modelData.icon
                        color: modelData.iconColor
                        font.pixelSize: 13
                        visible: modelData.icon !== ""
                    }
                    Text {
                        text: modelData.label
                        color: "#c0c0d0"
                        font.pixelSize: 13
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    onEntered: parent.filterHovered = true
                    onExited: parent.filterHovered = false
                    onClicked: root.filterChanged(modelData.label, true)
                }
            }
        }

        // Section header KATEGORIEN
        Text {
            text: "KATEGORIEN"
            color: "#6060a0"
            font.pixelSize: 10
            topPadding: 8
            bottomPadding: 4
        }

        // Category List
        Repeater {
            model: [
                {name: "Alle Mods",   count: 271, selected: true},
                {name: "Kleidung",    count: 48,  selected: false},
                {name: "Grafik",      count: 31,  selected: false},
                {name: "Rüstung",     count: 22,  selected: false},
                {name: "Texturen",    count: 19,  selected: false},
                {name: "NPCs",        count: 12,  selected: false},
                {name: "Frameworks",  count: 10,  selected: false}
            ]

            delegate: Rectangle {
                width: parent.width
                height: 28
                radius: 4
                color: modelData.selected ? "#1e3a5f" : (catHovered ? "#252538" : "transparent")

                property bool catHovered: false

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 6
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.name
                    color: modelData.selected ? "#3d85c8" : "#c0c0d0"
                    font.pixelSize: 13
                }

                Text {
                    anchors.right: parent.right
                    anchors.rightMargin: 6
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.count
                    color: modelData.selected ? "#3d85c8" : "#8080a0"
                    font.pixelSize: 12
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    onEntered: parent.catHovered = true
                    onExited: parent.catHovered = false
                    onClicked: root.categorySelected(modelData.name)
                }
            }
        }
    }
}
