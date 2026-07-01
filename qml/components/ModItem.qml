import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root

    height: 36
    color: hovered ? "#252538" : "transparent"
    radius: 4

    property bool hovered: false

    property string modName: "Unnamed Mod"
    property bool modEnabled: true
    property string category: ""
    property string version: ""
    property int conflictCount: 0
    property bool isRedmod: false

    signal toggled(bool enabled)

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        onEntered: root.hovered = true
        onExited: root.hovered = false
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        spacing: 6

        // 1. Drag Handle
        Text {
            text: "⠿"
            color: "#404050"
            font.pixelSize: 14
            Layout.preferredWidth: 14
        }

        // 2. Toggle Switch
        Item {
            Layout.preferredWidth: 36
            Layout.preferredHeight: 20

            Rectangle {
                id: toggleTrack
                width: 36
                height: 20
                radius: 10
                color: root.modEnabled ? "#3d85c8" : "#404050"

                Behavior on color {
                    ColorAnimation { duration: 150 }
                }

                Rectangle {
                    id: toggleThumb
                    width: 16
                    height: 16
                    radius: 8
                    color: "white"
                    anchors.verticalCenter: parent.verticalCenter
                    x: root.modEnabled ? parent.width - width - 2 : 2

                    Behavior on x {
                        NumberAnimation { duration: 150 }
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        root.modEnabled = !root.modEnabled
                        root.toggled(root.modEnabled)
                    }
                }
            }
        }

        // 3. Mod Name
        Text {
            text: root.modName
            color: "#ffffff"
            font.pixelSize: 13
            Layout.fillWidth: true
            elide: Text.ElideRight
        }

        // 4. Category Pill
        Rectangle {
            visible: root.category !== ""
            color: "#252538"
            radius: 10
            height: 20
            implicitWidth: catText.width + 16

            Text {
                id: catText
                anchors.centerIn: parent
                text: root.category
                color: "#a0a0b0"
                font.pixelSize: 11
            }
        }

        // 5. Conflict Badge
        Rectangle {
            visible: root.conflictCount > 0
            color: "#e8a000"
            radius: 10
            height: 20
            implicitWidth: confText.width + 12

            Text {
                id: confText
                anchors.centerIn: parent
                text: "△" + root.conflictCount
                color: "white"
                font.pixelSize: 11
            }
        }

        // 6. REDmod Badge
        Rectangle {
            visible: root.isRedmod
            color: "#1a3a1a"
            radius: 10
            height: 20
            implicitWidth: 56

            Text {
                anchors.centerIn: parent
                text: "REDmod"
                color: "#4caf50"
                font.pixelSize: 10
            }
        }

        // 7. Version
        Text {
            text: root.version
            color: "#606070"
            font.pixelSize: 11
            Layout.preferredWidth: 36
            horizontalAlignment: Text.AlignRight
        }
    }
}
