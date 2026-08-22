import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "bheemaguli.system-health-check"
  ipcTarget: "bheemaguli.system-health-check"
  manageIpc: false

  property Item anchorItem: null
  property var hostWidget: null

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property color track: Style.selectedFillFor(foreground, Color.accent)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  readonly property string netdataUrl: String(setting("netdataUrl", "http://127.0.0.1:19999"))
  readonly property int refreshSeconds: Math.max(5, Number(setting("refreshSeconds", 15)) || 15)
  readonly property int cpuWarn: Number(setting("cpuWarnPercent", 85)) || 85
  readonly property int ramWarn: Number(setting("ramWarnPercent", 80)) || 80
  readonly property int gpuWarn: Number(setting("gpuWarnPercent", 80)) || 80

  readonly property string cliPath: Qt.resolvedUrl("cli.py").toString().replace(/^file:\/\//, "")

  property var payload: ({})
  property bool loading: false
  property string lastError: ""
  property bool cursorActive: false

  readonly property bool online: !!(payload && payload.online)
  readonly property var now: (payload && payload.now) ? payload.now : ({})
  readonly property var windows: (payload && payload.windows) ? payload.windows : ({})
  readonly property var series: (payload && payload.series) ? payload.series : ({})
  readonly property var advice: (payload && payload.advice) ? payload.advice : []
  readonly property bool alarming: Model.alarming(now, cpuWarn, ramWarn, gpuWarn)
  readonly property string chipLabel: Model.barLabel(payload)
  readonly property string chipTooltip: Model.barTooltip(payload)

  function openFromHotkey() { root.open() }

  function refresh() {
    if (poll.running) return
    loading = true
    poll.command = [
      "python3", root.cliPath, "--url", root.netdataUrl, "panel"
    ]
    poll.running = true
  }

  function openNetdata() {
    if (root.bar)
      root.bar.run("python3 \"" + root.cliPath + "\" --url \"" + root.netdataUrl + "\" open")
    else
      Quickshell.execDetached(["python3", root.cliPath, "--url", root.netdataUrl, "open"])
  }

  function selectWindow(delta) {
    var keys = Model.windowKeys()
    var idx = keys.indexOf(selectedWindow)
    if (idx < 0) idx = 1
    idx = (idx + delta + keys.length) % keys.length
    selectedWindow = keys[idx]
  }

  property string selectedWindow: "24h"
  readonly property var selectedStats: windows[selectedWindow] || ({})

  Timer {
    id: refreshTimer
    interval: root.refreshSeconds * 1000
    running: true
    repeat: true
    onTriggered: root.refresh()
  }

  Component.onCompleted: Qt.callLater(root.refresh)
  onNetdataUrlChanged: Qt.callLater(root.refresh)
  onRefreshSecondsChanged: refreshTimer.restart()

  Process {
    id: poll
    stdout: StdioCollector {
      id: pollOut
      waitForEnd: true
      onStreamFinished: {
        root.loading = false
        var text = String(pollOut.text || "").trim()
        if (!text) {
          root.lastError = "empty response"
          return
        }
        try {
          root.payload = JSON.parse(text)
          root.lastError = root.payload.error || ""
        } catch (e) {
          root.lastError = "bad JSON from CLI"
        }
      }
    }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(code) {
      if (!pollOut.text) root.loading = false
    }
  }

  IpcHandler {
    target: "bheemaguli.system-health-check"
    function open(): void { root.openFromHotkey() }
    function close(): void { root.close() }
    function show(): void { root.openFromHotkey() }
    function hide(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): string { root.refresh(); return "ok" }
    function openNetdata(): string { root.openNetdata(); return "ok" }
  }

  // Invisible anchor button host is provided by BarWidget; this Panel only
  // owns the popup content.
  Item {
    id: buttonProxy
    width: 1
    height: 1
    visible: false
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem || buttonProxy
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(400))
    contentHeight: panel.fittedContentHeight(column.implicitHeight, Style.space(620))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent

      onMoveRequested: function(dx, dy) {
        if (dx !== 0) {
          root.cursorActive = true
          root.selectWindow(dx)
        }
        if (dy !== 0)
          panelFlick.contentY = Math.max(0, Math.min(
            panelFlick.contentY + dy * Style.space(48),
            Math.max(0, panelFlick.contentHeight - panelFlick.height)))
      }
      onActivateRequested: root.refresh()
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) {
        if (t === "r" || t === "R") root.refresh()
        else if (t === "o" || t === "O") root.openNetdata()
        else if (t === "1") root.selectedWindow = "1h"
        else if (t === "2") root.selectedWindow = "24h"
        else if (t === "3") root.selectedWindow = "7d"
      }

      Flickable {
        id: panelFlick
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
          id: column
          width: panelFlick.width
          spacing: Style.space(12)

          PanelHero {
            width: parent.width
            title: "System health"
            meta: root.online
              ? ((root.payload.netdata_version ? "Netdata " + root.payload.netdata_version : "Netdata") +
                 (root.loading ? " · refreshing" : ""))
              : "Netdata offline"
            detail: root.online ? root.selectedWindow : "setup"
            foreground: root.alarming ? root.urgent : root.foreground
            fontFamily: root.fontFamily
            iconComponent: Component {
              Text {
                text: "󰍛"
                color: root.alarming ? root.urgent : root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.display
              }
            }
          }

          Text {
            visible: !root.online
            width: parent.width
            wrapMode: Text.WordWrap
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            text: (root.lastError ? root.lastError + "\n\n" : "") +
                  "Install and start Netdata, then this chip tracks history for laptop sizing.\n\n" +
                  "omarchy pkg add netdata\n" +
                  "sudo systemctl enable --now netdata"
          }

          // ---- live meters ----
          Column {
            visible: root.online
            width: parent.width
            spacing: Style.space(8)

            Text {
              text: "NOW"
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              font.bold: true
            }

            MetricRow {
              width: parent.width
              label: "CPU"
              valueText: Model.pct(root.now.cpu)
              fraction: (Number(root.now.cpu) || 0) / 100
              warn: root.now.cpu != null && Number(root.now.cpu) >= root.cpuWarn
            }
            MetricRow {
              width: parent.width
              label: "RAM"
              valueText: {
                var p = Model.pct(root.now.ram)
                if (root.now.ram_used_gb != null && root.now.ram_total_gb != null)
                  return p + "  " + Model.gb(root.now.ram_used_gb) + "/" + Model.gb(root.now.ram_total_gb)
                return p
              }
              fraction: (Number(root.now.ram) || 0) / 100
              warn: root.now.ram != null && Number(root.now.ram) >= root.ramWarn
            }
            MetricRow {
              visible: root.now.gpu !== null && root.now.gpu !== undefined
              width: parent.width
              label: "GPU"
              valueText: Model.pct(root.now.gpu)
              fraction: (Number(root.now.gpu) || 0) / 100
              warn: root.now.gpu != null && Number(root.now.gpu) >= root.gpuWarn
            }
            Text {
              text: "Load  " + (root.now.load1 != null ? root.now.load1 : "—")
                    + "  " + (root.now.load5 != null ? root.now.load5 : "—")
                    + "  " + (root.now.load15 != null ? root.now.load15 : "—")
                    + (root.now.disk != null ? "   ·   Disk " + Model.pct(root.now.disk) : "")
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
            }
          }

          PanelSeparator { visible: root.online; width: parent.width }

          // ---- history window picker ----
          Column {
            visible: root.online
            width: parent.width
            spacing: Style.space(8)

            Item {
              width: parent.width
              height: Style.space(24)

              Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: "HISTORY"
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
              }

              Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: Style.space(8)
                Repeater {
                  model: Model.windowKeys()
                  delegate: BorderSurface {
                    required property string modelData
                    implicitWidth: winLabel.implicitWidth + Style.space(10)
                    implicitHeight: winLabel.implicitHeight + Style.space(4)
                    color: modelData === root.selectedWindow ? root.track : "transparent"
                    borderSpec: Border.controlSpec(
                      modelData === root.selectedWindow ? "selected" : "normal",
                      root.foreground, Color.accent)
                    radius: Style.cornerRadius
                    Text {
                      id: winLabel
                      anchors.centerIn: parent
                      text: modelData
                      color: root.foreground
                      font.family: root.fontFamily
                      font.pixelSize: Style.font.caption
                    }
                    MouseArea {
                      anchors.fill: parent
                      cursorShape: Qt.PointingHandCursor
                      onClicked: root.selectedWindow = modelData
                    }
                  }
                }
              }
            }

            StatRow { width: parent.width; label: "CPU"; stat: root.selectedStats.cpu }
            StatRow { width: parent.width; label: "RAM"; stat: root.selectedStats.ram }
            StatRow {
              visible: root.selectedStats.gpu && root.selectedStats.gpu.avg !== null && root.selectedStats.gpu.avg !== undefined
              width: parent.width; label: "GPU"; stat: root.selectedStats.gpu
            }
          }

          // ---- 24h sparklines ----
          Column {
            visible: root.online
            width: parent.width
            spacing: Style.space(8)

            Text {
              text: "LAST 24H"
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              font.bold: true
            }

            SparkLine { width: parent.width; label: "CPU"; values: root.series.cpu || [] }
            SparkLine { width: parent.width; label: "RAM"; values: root.series.ram || [] }
            SparkLine {
              visible: (root.series.gpu || []).some(function(v) { return v !== null && v !== undefined })
              width: parent.width; label: "GPU"; values: root.series.gpu || []
            }
          }

          PanelSeparator { visible: root.online; width: parent.width }

          Column {
            width: parent.width
            spacing: Style.space(6)
            Text {
              text: "FOR YOUR NEXT LAPTOP"
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              font.bold: true
            }
            Repeater {
              model: root.advice
              delegate: Text {
                required property string modelData
                width: column.width
                wrapMode: Text.WordWrap
                text: "·  " + modelData
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
              }
            }
          }

          Row {
            spacing: Style.space(8)
            Button {
              text: "Open Netdata"
              bordered: true
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.openNetdata()
            }
            Button {
              text: root.loading ? "Refreshing…" : "Refresh"
              bordered: true
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.refresh()
            }
          }

          Text {
            width: parent.width
            wrapMode: Text.WordWrap
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            text: "← → window · 1/2/3 · r refresh · o Netdata · click chip · middle refresh · right open"
          }
        }
      }
    }
  }

  component MetricRow: Item {
    id: metric
    property string label: ""
    property string valueText: ""
    property real fraction: 0
    property bool warn: false
    height: Style.space(28)

    Text {
      id: metricLabel
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      width: Style.space(44)
      text: metric.label
      color: metric.warn ? root.urgent : root.dim
      font.family: root.fontFamily
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
      color: root.track

      Rectangle {
        width: parent.width * Model.clamp(metric.fraction, 0, 1)
        height: parent.height
        radius: parent.radius
        color: metric.warn ? root.urgent : root.foreground
      }
    }

    Text {
      id: metricValue
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      text: metric.valueText
      color: metric.warn ? root.urgent : root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
    }
  }

  component StatRow: Item {
    id: statRow
    property string label: ""
    property var stat: ({})
    height: Style.space(22)

    Text {
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      width: Style.space(44)
      text: statRow.label
      color: root.dim
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
      font.bold: true
    }
    Text {
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      text: Model.statLine(statRow.stat)
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
    }
  }

  component SparkLine: Item {
    id: spark
    property string label: ""
    property var values: []
    height: Style.space(36)

    Text {
      id: sparkLabel
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      width: Style.space(44)
      text: spark.label
      color: root.dim
      font.family: root.fontFamily
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
        ctx.strokeStyle = root.foreground
        ctx.lineWidth = 1.5
        ctx.lineJoin = "round"
        ctx.lineCap = "round"
        ctx.beginPath()
        // Path from Model.sparkPath uses M/L commands — parse simply:
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
      }
      Component.onCompleted: requestPaint()
      onWidthChanged: requestPaint()
      onHeightChanged: requestPaint()
    }
  }
}
