import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15

Rectangle {
    id: root
    color: "#0d0d1a"
    height: 28

    property string status: "Bereit"
    property string instanceName: "Cyberpunk"
    property int conflictCount: 3
    property bool apiConnected: false

    // Top border
    Rectangle {
        width: parent.width
        height: 1
        color: "#2a2a40"
        anchors.top: parent.top
    }

    // Left side
    Row {
        anchors {
            left: parent.left
            leftMargin: 12
            verticalCenter: parent.verticalCenter
        }
        spacing: 16

        // Status dot + text
        Row {
            spacing: 4

            Rectangle {
                width: 8
                height: 8
                radius: 4
                color: "#4caf50"
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                text: root.status
                color: "#8080a0"
                font.pixelSize: 11
            }
        }

        Text {
            text: "Instanz: " + root.instanceName
            color: "#8080a0"
            font.pixelSize: 11
        }

        Text {
            text: "Plugin " + root.instanceName.toLowerCase() + "2077..."
            color: "#606070"
            font.pixelSize: 11
        }
    }

    // Right side
    Row {
        anchors {
            right: parent.right
            rightMargin: 12
            verticalCenter: parent.verticalCenter
        }
        spacing: 12

        Text {
            text: root.conflictCount + " Konflikte"
            color: "#e8a000"
            font.pixelSize: 11
            visible: root.conflictCount > 0
        }

        Text {
            text: root.apiConnected ? "API: verbunden" : "API: nicht verbunden"
            color: "#6060a0"
            font.pixelSize: 11
        }
    }
}
