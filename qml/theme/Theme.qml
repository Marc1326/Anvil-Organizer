pragma Singleton
import QtQuick 2.15

QtObject {
    id: theme
    readonly property color background: "#1a1a2e"
    readonly property color backgroundSecondary: "#131325"
    readonly property color groupBackground: "#1e1e32"
    readonly property color hoverBackground: "#252538"
    readonly property color selectedBackground: "#1e3a5f"
    readonly property color topbarBackground: "#0f0f20"
    readonly property color bottombarBackground: "#0d0d1a"
    readonly property color accent: "#3d85c8"
    readonly property color accentHover: "#4a96d9"
    readonly property color textPrimary: "#ffffff"
    readonly property color textSecondary: "#c0c0d0"
    readonly property color textMuted: "#8080a0"
    readonly property color textVeryMuted: "#606070"
    readonly property color conflictColor: "#e8a000"
    readonly property color successColor: "#4caf50"
    readonly property color toggleOn: "#3d85c8"
    readonly property color toggleOff: "#404050"
    readonly property color pillBackground: "#252538"
    readonly property color pillText: "#a0a0b0"
    readonly property color borderColor: "#2a2a40"
    readonly property int fontSmall: 11
    readonly property int fontNormal: 13
    readonly property int fontMedium: 14
    readonly property int fontLarge: 16
    readonly property int fontTitle: 18
    readonly property int spacingXS: 4
    readonly property int spacingS: 8
    readonly property int spacingM: 12
    readonly property int spacingL: 16
    readonly property int spacingXL: 24
}
