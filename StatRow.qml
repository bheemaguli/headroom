import QtQuick
import qs.Commons
import "Model.js" as Model

Item {
  id: statRow
  property string label: ""
  property var stat: ({})
  property color foreground: Color.foreground
  property color dim: Qt.darker(foreground, 1.55)
  property string fontFamily: Style.font.family
  height: Style.space(22)

  Text {
    anchors.left: parent.left
    anchors.verticalCenter: parent.verticalCenter
    width: Style.space(44)
    text: statRow.label
    color: statRow.dim
    font.family: statRow.fontFamily
    font.pixelSize: Style.font.body
    font.bold: true
  }
  Text {
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    text: Model.statLine(statRow.stat)
    color: statRow.foreground
    font.family: statRow.fontFamily
    font.pixelSize: Style.font.body
  }
}
