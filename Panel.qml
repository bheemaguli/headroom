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
  readonly property string defaultWindow: String(setting("defaultWindow", "7d") || "7d")
  readonly property int customDaysSetting: Math.max(0, Math.min(90, Number(setting("customDays", 0)) || 0))
  readonly property int cpuWarn: Number(setting("cpuWarnPercent", 85)) || 85
  readonly property int ramWarn: Number(setting("ramWarnPercent", 80)) || 80
  readonly property int gpuWarn: Number(setting("gpuWarnPercent", 80)) || 80

  readonly property string cliPath: Qt.resolvedUrl("cli.py").toString().replace(/^file:\/\//, "")

  property var payload: ({})
  property bool loading: false
  property bool exporting: false
  property string lastError: ""
  property string lastExportPath: ""
  property bool cursorActive: false
  // Preset key ("7d") or "custom" when the C tab owns the range.
  property string selectedWindow: "7d"
  property int customDays: 0
  property bool customEditing: false
  property int customDraft: 7

  readonly property var historyKeys: Model.windowKeys()
  readonly property bool isCustomSelected: selectedWindow === "custom" && customDays > 0
  readonly property string focusWindow: isCustomSelected
    ? (String(customDays) + "d")
    : (selectedWindow || defaultWindow || "7d")
  readonly property bool online: !!(payload && payload.online)
  readonly property var now: (payload && payload.now) ? payload.now : ({})
  readonly property var windows: (payload && payload.windows) ? payload.windows : ({})
  readonly property var series: (payload && payload.series) ? payload.series : ({})
  readonly property var advice: (payload && payload.advice) ? payload.advice : []
  readonly property string historyHeading: Model.historyTitle(root.isCustomSelected, root.customDays)
  readonly property bool alarming: Model.alarming(now, cpuWarn, ramWarn, gpuWarn)
  readonly property string chipLabel: Model.barLabel(payload)
  readonly property string chipTooltip: Model.barTooltip(payload)
  readonly property var selectedStats: windows[focusWindow] || ({})
  readonly property bool hasTrend: Model.seriesHasPoints(series.cpu)
    || Model.seriesHasPoints(series.ram)
    || Model.seriesHasPoints(series.gpu)

  function openFromHotkey() { root.open() }

  // Applied locally first so the panel redraws on the click itself; the
  // shell.json write comes back through the bar as the same value.
  function persistSettings(values) {
    var entry = { id: root.moduleName }
    for (var existing in root.settings) if (existing !== "id") entry[existing] = root.settings[existing]
    for (var key in values) entry[key] = values[key]

    root.settings = entry
    if (root.hostWidget && "settings" in root.hostWidget) root.hostWidget.settings = entry
    if (root.bar && root.bar.shell && typeof root.bar.shell.updateEntryInline === "function")
      root.bar.shell.updateEntryInline(root.moduleName, entry)
  }

  function refresh() {
    if (poll.running) return
    loading = true
    var focus = root.focusWindow
    var cmd = [
      "python3", root.cliPath, "--url", root.netdataUrl, "panel", "--window", focus
    ]
    if (root.customDays > 0)
      cmd.push("--extra-days", String(root.customDays))
    poll.command = cmd
    poll.running = true
  }

  function openNetdata() {
    if (root.bar)
      root.bar.run("python3 \"" + root.cliPath + "\" --url \"" + root.netdataUrl + "\" open")
    else
      Quickshell.execDetached(["python3", root.cliPath, "--url", root.netdataUrl, "open"])
  }

  function openCustomEditor() {
    customDraft = customDays > 0 ? customDays : 7
    customEditing = true
  }

  function confirmCustomDays() {
    var days = Math.max(1, Math.min(90, Number(customDraft) || 0))
    if (days < 1) return
    customDays = days
    customEditing = false
    selectedWindow = "custom"
    root.persistSettings({ customDays: days })
    root.refresh()
  }

  function onCustomTabClicked() {
    if (customEditing) return
    if (isCustomSelected)
      openCustomEditor()
    else if (customDays > 0) {
      selectedWindow = "custom"
      root.refresh()
    } else
      openCustomEditor()
  }

  function exportCsv() {
    if (exportProc.running) return
    exporting = true
    lastExportPath = ""
    var focus = root.focusWindow
    var dir = Quickshell.env("HOME") + "/Downloads"
    exportProc.command = [
      "python3", root.cliPath, "--url", root.netdataUrl,
      "export", focus, "-o", dir
    ]
    exportProc.running = true
  }

  function selectWindow(delta) {
    var keys = root.historyKeys.slice()
    if (root.customDays > 0) keys.push("custom")
    var current = root.selectedWindow
    var idx = keys.indexOf(current)
    if (idx < 0) idx = keys.indexOf(root.defaultWindow)
    if (idx < 0) idx = 0
    idx = (idx + delta + keys.length) % keys.length
    if (keys[idx] === "custom") {
      selectedWindow = "custom"
      root.refresh()
    } else
      root.chooseWindow(keys[idx])
  }

  function chooseWindow(key) {
    customEditing = false
    selectedWindow = key
    root.refresh()
  }

  Timer {
    id: refreshTimer
    interval: root.refreshSeconds * 1000
    running: true
    repeat: true
    onTriggered: root.refresh()
  }

  Component.onCompleted: {
    customDays = root.customDaysSetting
    if (customDays > 0)
      selectedWindow = "custom"
    else
      selectedWindow = root.defaultWindow || "7d"
    Qt.callLater(root.refresh)
  }
  onNetdataUrlChanged: Qt.callLater(root.refresh)
  onCustomDaysSettingChanged: {
    customDays = customDaysSetting
    if (customDays > 0 && selectedWindow === "custom")
      Qt.callLater(root.refresh)
  }
  onDefaultWindowChanged: {
    if (selectedWindow !== "custom" && historyKeys.indexOf(defaultWindow) >= 0)
      selectedWindow = defaultWindow
    Qt.callLater(root.refresh)
  }
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

  Process {
    id: exportProc
    stdout: StdioCollector {
      id: exportOut
      waitForEnd: true
      onStreamFinished: {
        root.exporting = false
        var path = String(exportOut.text || "").trim()
        root.lastExportPath = path
        if (path && root.bar)
          root.bar.run("omarchy-notification-send \"Exported " + path.replace(/"/g, "") + "\"")
      }
    }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(code) {
      if (code !== 0) root.exporting = false
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
        if (root.customEditing) {
          if (t === "\r" || t === "\n") root.confirmCustomDays()
          return
        }
        if (t === "r" || t === "R") root.refresh()
        else if (t === "o" || t === "O") root.openNetdata()
        else if (t === "1") root.chooseWindow("1h")
        else if (t === "2") root.chooseWindow("24h")
        else if (t === "3") root.chooseWindow("7d")
        else if (t === "4") root.chooseWindow("14d")
        else if (t === "5") root.chooseWindow("30d")
        else if (t === "c" || t === "C") root.onCustomTabClicked()
        else if (t === "e" || t === "E") root.exportCsv()
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
            detail: root.online ? "" : "setup"
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
            trailingControl: Component {
              Button {
                text: "Open Netdata"
                bordered: true
                foreground: root.foreground
                fontFamily: root.fontFamily
                onClicked: root.openNetdata()
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

            Item {
              width: parent.width
              height: Style.space(24)

              Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: "NOW"
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
              }

              BorderSurface {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: Style.space(28)
                implicitHeight: Style.space(28)
                color: refreshHover.hovered ? root.track : "transparent"
                borderSpec: Border.controlSpec(
                  refreshHover.hovered ? "hover-cursor" : "normal",
                  root.foreground, Color.accent)
                radius: Style.cornerRadius
                opacity: root.loading ? 0.6 : 1

                Text {
                  anchors.centerIn: parent
                  text: "󰑐"
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body

                  RotationAnimator on rotation {
                    running: root.loading
                    from: 0; to: 360
                    duration: 800
                    loops: Animation.Infinite
                  }
                }

                HoverHandler { id: refreshHover }
                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  enabled: !root.loading
                  onClicked: root.refresh()
                }
              }
            }

            MetricRow {
              width: parent.width
              label: "CPU"
              valueText: Model.pct(root.now.cpu)
              fraction: (Number(root.now.cpu) || 0) / 100
              warn: root.now.cpu != null && Number(root.now.cpu) >= root.cpuWarn
              foreground: root.foreground
              dim: root.dim
              urgent: root.urgent
              track: root.track
              fontFamily: root.fontFamily
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
              foreground: root.foreground
              dim: root.dim
              urgent: root.urgent
              track: root.track
              fontFamily: root.fontFamily
            }
            MetricRow {
              visible: root.now.gpu !== null && root.now.gpu !== undefined
              width: parent.width
              label: "GPU"
              valueText: Model.pct(root.now.gpu)
              fraction: (Number(root.now.gpu) || 0) / 100
              warn: root.now.gpu != null && Number(root.now.gpu) >= root.gpuWarn
              foreground: root.foreground
              dim: root.dim
              urgent: root.urgent
              track: root.track
              fontFamily: root.fontFamily
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
                text: root.historyHeading
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
              }

              Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: Style.space(6)

                Repeater {
                  model: root.historyKeys
                  delegate: BorderSurface {
                    required property string modelData
                    implicitWidth: Math.max(winLabel.implicitWidth + Style.space(10), Style.space(28))
                    implicitHeight: winLabel.implicitHeight + Style.space(4)
                    color: !root.isCustomSelected && modelData === root.selectedWindow ? root.track : "transparent"
                    borderSpec: Border.controlSpec(
                      (!root.isCustomSelected && modelData === root.selectedWindow) ? "selected" : "normal",
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
                      onClicked: root.chooseWindow(modelData)
                    }
                  }
                }

                BorderSurface {
                  implicitWidth: Style.space(28)
                  implicitHeight: customTabLabel.implicitHeight + Style.space(4)
                  color: root.isCustomSelected ? root.track : "transparent"
                  borderSpec: Border.controlSpec(
                    root.isCustomSelected ? "selected" : "normal",
                    root.foreground, Color.accent)
                  radius: Style.cornerRadius
                  Text {
                    id: customTabLabel
                    anchors.centerIn: parent
                    text: "C"
                    color: root.foreground
                    font.family: root.fontFamily
                    font.pixelSize: Style.font.caption
                    font.bold: true
                  }
                  MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.onCustomTabClicked()
                  }
                }
              }
            }

            Row {
              visible: root.customEditing
              width: parent.width
              spacing: Style.space(8)

              Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "Custom range"
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
              }

              NumberField {
                id: customDaysField
                anchors.verticalCenter: parent.verticalCenter
                label: ""
                value: root.customDraft
                from: 1
                to: 90
                stepSize: 1
                fieldWidth: Style.space(64)
                foreground: root.foreground
                fontFamily: root.fontFamily
                onModified: function(v) { root.customDraft = v }
              }

              Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "days"
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }

              BorderSurface {
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: Style.space(28)
                implicitHeight: Style.space(28)
                color: root.track
                borderSpec: Border.controlSpec("selected", root.foreground, Color.accent)
                radius: Style.cornerRadius
                Text {
                  anchors.centerIn: parent
                  text: "✓"
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  font.bold: true
                }
                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.confirmCustomDays()
                }
              }
            }

            StatRow {
              width: parent.width
              label: "CPU"
              stat: root.selectedStats.cpu
              foreground: root.foreground
              dim: root.dim
              fontFamily: root.fontFamily
            }
            StatRow {
              width: parent.width
              label: "RAM"
              stat: root.selectedStats.ram
              foreground: root.foreground
              dim: root.dim
              fontFamily: root.fontFamily
            }
            StatRow {
              visible: root.selectedStats.gpu && root.selectedStats.gpu.avg !== null && root.selectedStats.gpu.avg !== undefined
              width: parent.width
              label: "GPU"
              stat: root.selectedStats.gpu
              foreground: root.foreground
              dim: root.dim
              fontFamily: root.fontFamily
            }

            Item {
              width: parent.width
              height: Style.space(28)

              Text {
                visible: root.lastExportPath !== ""
                anchors.left: parent.left
                anchors.right: exportButton.left
                anchors.rightMargin: Style.space(8)
                anchors.verticalCenter: parent.verticalCenter
                wrapMode: Text.WrapAnywhere
                elide: Text.ElideMiddle
                maximumLineCount: 1
                color: root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                text: "Saved " + root.lastExportPath
              }

              BorderSurface {
                id: exportButton
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: exportLabel.implicitWidth + Style.space(14)
                implicitHeight: Style.space(28)
                color: exportHover.hovered ? root.track : "transparent"
                borderSpec: Border.controlSpec(
                  exportHover.hovered ? "hover-cursor" : "normal",
                  root.foreground, Color.accent)
                radius: Style.cornerRadius
                opacity: (!root.online || root.exporting) ? 0.5 : 1

                Text {
                  id: exportLabel
                  anchors.centerIn: parent
                  text: (root.exporting ? "󰔟" : "󰁅") + " Export"
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }

                HoverHandler { id: exportHover }
                MouseArea {
                  anchors.fill: parent
                  cursorShape: Qt.PointingHandCursor
                  enabled: root.online && !root.exporting
                  onClicked: root.exportCsv()
                }
              }
            }
          }

          // ---- sparklines for the selected window (hidden when Netdata has no series yet) ----
          Column {
            visible: root.online && root.hasTrend
            width: parent.width
            spacing: Style.space(8)

            Text {
              text: "TREND"
              color: root.dim
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              font.bold: true
            }

            SparkLine {
              visible: Model.seriesHasPoints(root.series.cpu)
              width: parent.width
              label: "CPU"
              values: root.series.cpu || []
              foreground: root.foreground
              dim: root.dim
              fontFamily: root.fontFamily
            }
            SparkLine {
              visible: Model.seriesHasPoints(root.series.ram)
              width: parent.width
              label: "RAM"
              values: root.series.ram || []
              foreground: root.foreground
              dim: root.dim
              fontFamily: root.fontFamily
            }
            SparkLine {
              visible: Model.seriesHasPoints(root.series.gpu)
              width: parent.width
              label: "GPU"
              values: root.series.gpu || []
              foreground: root.foreground
              dim: root.dim
              fontFamily: root.fontFamily
            }
          }

          PanelSeparator { visible: root.online; width: parent.width }

          Column {
            width: parent.width
            spacing: Style.space(6)
            Text {
              text: "FOR YOUR NEXT COMPUTER"
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

          Text {
            width: parent.width
            wrapMode: Text.WordWrap
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            text: "← → range · 1–5 · c custom · e export · r refresh · o Netdata"
          }
        }
      }
    }
  }
}
