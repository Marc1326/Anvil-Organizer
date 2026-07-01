import QtQuick 2.15
import QtQuick.Layouts 1.15

Column {
    id: root
    width: parent.width

    property string groupName: "Group"
    property var tags: []
    property int modCount: 0
    property bool expanded: true
    property var modItems: []

    signal expandToggled(bool expanded)

    // Group Header
    Rectangle {
        id: header
        width: parent.width
        height: 36
        color: "#1e1e32"

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onClicked: {
                root.expanded = !root.expanded
                root.expandToggled(root.expanded)
            }
            onEntered: header.color = "#252538"
            onExited: header.color = "#1e1e32"
        }

        Row {
            anchors {
                left: parent.left
                leftMargin: 12
                verticalCenter: parent.verticalCenter
            }
            spacing: 6

            Text {
                text: root.expanded ? "▼" : "►"
                color: "#8080a0"
                font.pixelSize: 12
            }

            Text {
                text: root.groupName
                color: "#ffffff"
                font.pixelSize: 13
                font.bold: true
            }

            Repeater {
                model: root.tags
                Text {
                    text: " · " + modelData
                    color: "#8080a0"
                    font.pixelSize: 12
                }
            }
        }

        Text {
            anchors {
                right: parent.right
                rightMargin: 12
                verticalCenter: parent.verticalCenter
            }
            text: root.modCount + " Mods"
            color: "#8080a0"
            font.pixelSize: 12
        }
    }

    // Content
    Column {
        visible: root.expanded
        width: parent.width

        Repeater {
            model: root.modItems
            delegate: ModItem {
                width: parent.width
                modName: modelData.name
                modEnabled: modelData.enabled
                category: modelData.category
                version: modelData.version || ""
                conflictCount: modelData.conflictCount || 0
                isRedmod: modelData.isRedmod || false
            }
        }
    }
}
