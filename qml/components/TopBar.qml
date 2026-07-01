import QtQuick 2.15
import QtQuick.Layouts 1.15

Item {
    id: root

    width: parent.width
    height: 50

    property string gameName: "Cyberpunk 2077"
    property string activeProfile: "ebbp"

    signal playClicked()
    signal settingsClicked()

    Rectangle {
        anchors.fill: parent
        color: "#0f0f20"
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12

        // LEFT SECTION
        RowLayout {
            spacing: 8

            Rectangle {
                width: 36
                height: 36
                radius: 6
                color: "#e87d00"

                Text {
                    anchors.centerIn: parent
                    text: "C"
                    color: "white"
                    font.pixelSize: 16
                    font.bold: true
                }
            }

            Column {
                spacing: 2

                Text {
                    text: "Cyberpunk 2077"
                    color: "#ffffff"
                    font.pixelSize: 14
                    font.bold: true
                }

                Text {
                    text: "Instanz: wechseln öffnet das gewünschte Spiel"
                    color: "#8080a0"
                    font.pixelSize: 10
                }
            }

            Text {
                text: "▾"
                color: "#8080a0"
                font.pixelSize: 14
            }
        }

        // SPACER
        Item {
            Layout.fillWidth: true
        }

        // CENTER SECTION
        RowLayout {
            spacing: 4

            Rectangle {
                width: 70
                height: 34
                radius: 4
                color: "#1e1e32"

                Text {
                    anchors.centerIn: parent
                    text: "Default"
                    color: "#c0c0d0"
                    font.pixelSize: 13
                }
            }

            Rectangle {
                width: 60
                height: 34
                radius: 4
                color: "#252538"

                Row {
                    anchors.centerIn: parent
                    spacing: 4

                    Text {
                        text: "ebbp"
                        color: "#ffffff"
                        font.pixelSize: 13
                    }

                    Rectangle {
                        width: 6
                        height: 6
                        radius: 3
                        color: "#3d85c8"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }

        // SPACER before right section
        Item {
            width: 8
        }

        // RIGHT SECTION
        RowLayout {
            spacing: 8

            Rectangle {
                width: 100
                height: 34
                radius: 6
                color: "#3d85c8"

                Text {
                    anchors.centerIn: parent
                    text: "► Spielen"
                    color: "white"
                    font.pixelSize: 13
                    font.bold: true
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: root.playClicked()
                }
            }

            Rectangle {
                width: 34
                height: 34
                radius: 6
                color: "#1e1e32"

                Text {
                    anchors.centerIn: parent
                    text: "⚙"
                    color: "#c0c0d0"
                    font.pixelSize: 16
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: root.settingsClicked()
                }
            }
        }
    }
}
