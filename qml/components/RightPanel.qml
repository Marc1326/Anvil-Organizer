import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls 2.15

Rectangle {
    id: root
    color: "#0f0f20"
    clip: true

    property string gameName: "CYBERPUNK 2077"
    property string activeTab: "Daten"

    signal tabChanged(string tab)

    property var fileItems: [
        {icon: "📁", name: "archive", info: "Ordner"},
        {icon: "📁", name: "bin", info: "Ordner"},
        {icon: "📁", name: "r6", info: "Ordner"},
        {icon: "📄", name: "red4ext.dll", info: "1.8 MB"},
        {icon: "📄", name: "pcre2-16.dll", info: "414 KB"}
    ]

    Column {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        // 1. GAME COVER CARD
        Rectangle {
            width: parent.width
            height: 120
            radius: 8
            color: "#1a1000"
            clip: true

            Rectangle {
                anchors {
                    left: parent.left
                    top: parent.top
                }
                width: parent.width * 0.6
                height: parent.height
                color: "#e87d00"
                opacity: 0.7
                radius: 8
            }

            Column {
                anchors {
                    left: parent.left
                    bottom: parent.bottom
                    leftMargin: 12
                    bottomMargin: 10
                }
                spacing: 0

                Text {
                    text: "CYBERPUNK"
                    color: "white"
                    font.pixelSize: 14
                    font.bold: true
                    font.letterSpacing: 2
                }
                Text {
                    text: "2077"
                    color: "white"
                    font.pixelSize: 20
                    font.bold: true
                }
            }
        }

        // 2. TAB BAR
        Row {
            width: parent.width
            height: 32
            spacing: 0

            Repeater {
                model: ["Daten", "Spielstände", "Downloads"]

                Rectangle {
                    width: parent.width / 3
                    height: 32
                    color: "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: modelData
                        color: root.activeTab === modelData ? "#ffffff" : "#8080a0"
                        font.pixelSize: 13
                    }

                    Rectangle {
                        anchors {
                            bottom: parent.bottom
                            left: parent.left
                            right: parent.right
                        }
                        height: 2
                        color: root.activeTab === modelData ? "#3d85c8" : "transparent"
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            root.activeTab = modelData
                            root.tabChanged(modelData)
                        }
                    }
                }
            }
        }

        // Sort Button (anchors.right workaround: wrap in Item)
        Item {
            width: parent.width
            height: 26

            Rectangle {
                width: 80
                height: 26
                radius: 6
                color: "#252538"
                anchors.right: parent.right

                Text {
                    anchors.centerIn: parent
                    text: "Sortieren"
                    color: "#a0a0b0"
                    font.pixelSize: 12
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                }
            }
        }

        // 3. FILE LIST
        Column {
            width: parent.width
            spacing: 0

            Repeater {
                model: root.fileItems

                Rectangle {
                    width: parent.width
                    height: 32
                    radius: 4
                    color: hovered ? "#252538" : "transparent"

                    property bool hovered: false

                    Row {
                        anchors {
                            left: parent.left
                            leftMargin: 8
                            verticalCenter: parent.verticalCenter
                        }
                        spacing: 8

                        Text {
                            text: modelData.icon
                            font.pixelSize: 14
                        }
                        Text {
                            text: modelData.name
                            color: "#ffffff"
                            font.pixelSize: 13
                        }
                    }

                    Text {
                        anchors {
                            right: parent.right
                            rightMargin: 8
                            verticalCenter: parent.verticalCenter
                        }
                        text: modelData.info
                        color: "#8080a0"
                        font.pixelSize: 11
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        onEntered: parent.hovered = true
                        onExited: parent.hovered = false
                    }
                }
            }
        }

        // 5. KATEGORIEN HEADER
        Text {
            text: "KATEGORIEN"
            color: "#6060a0"
            font.pixelSize: 10
            topPadding: 4
        }
    }
}
