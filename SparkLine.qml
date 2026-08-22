import QtQuick
import qs.Commons
import "Model.js" as Model

Item {
  id: spark
  property string label: ""
  property var values: []
  property color foreground: Color.foreground
  property color dim: Qt.darker(foreground, 1.55)
  property string fontFamily: Style.font.family
  height: Style.space(36)

  Text {
    id: sparkLabel
    anchors.left: parent.left
    anchors.verticalCenter: parent.verticalCenter
    width: Style.space(44)
    text: spark.label
    color: spark.dim
    font.family: spark.fontFamily
    font.pixelSize: Style.font.caption
    font.bold: true
  }

  Canvas {
    id: canvas
    anchors.left: sparkLabel.right
    anchors.leftMargin: Style.space(8)
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    height: Style.space(28)
    onPaint: {
      var ctx = getContext("2d")
      ctx.clearRect(0, 0, width, height)
      var path = Model.sparkPath(spark.values, width, height)
      if (!path) return
      ctx.strokeStyle = spark.foreground
      ctx.lineWidth = 1.5
      ctx.lineJoin = "round"
      ctx.lineCap = "round"
      ctx.beginPath()
      var parts = path.split(" ")
      for (var i = 0; i < parts.length; ) {
        var cmd = parts[i++]
        var x = parseFloat(cmd.substring(1))
        var y = parseFloat(parts[i++])
        if (cmd.charAt(0) === "M") ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.stroke()
    }
    Connections {
      target: spark
      function onValuesChanged() { canvas.requestPaint() }
      function onForegroundChanged() { canvas.requestPaint() }
    }
    Component.onCompleted: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
  }
}
