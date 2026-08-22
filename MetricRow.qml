import QtQuick
import qs.Commons
import qs.Ui
import "Model.js" as Model

Item {
  id: metric
  property string label: ""
  property string valueText: ""
  property real fraction: 0
  property bool warn: false
  property color foreground: Color.foreground
  property color dim: Qt.darker(foreground, 1.55)
  property color urgent: Color.urgent
  property color track: Style.selectedFillFor(foreground, Color.accent)
  property string fontFamily: Style.font.family
  height: Style.space(28)

  Text {
    id: metricLabel
    anchors.left: parent.left
    anchors.verticalCenter: parent.verticalCenter
    width: Style.space(44)
    text: metric.label
    color: metric.warn ? metric.urgent : metric.dim
    font.family: metric.fontFamily
    font.pixelSize: Style.font.body
    font.bold: true
  }

  Rectangle {
    id: meterTrack
    anchors.left: metricLabel.right
    anchors.leftMargin: Style.space(8)
    anchors.right: metricValue.left
    anchors.rightMargin: Style.space(10)
    anchors.verticalCenter: parent.verticalCenter
    height: Style.space(8)
    radius: height / 2
    color: metric.track

    Rectangle {
      width: parent.width * Model.clamp(metric.fraction, 0, 1)
      height: parent.height
      radius: parent.radius
      color: metric.warn ? metric.urgent : metric.foreground
    }
  }

  Text {
    id: metricValue
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    text: metric.valueText
    color: metric.warn ? metric.urgent : metric.foreground
    font.family: metric.fontFamily
    font.pixelSize: Style.font.body
  }
}
