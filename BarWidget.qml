import QtQuick
import qs.Commons
import qs.Ui

// Compact CPU · RAM · GPU chip. The panel lives in Panel.qml and stays loaded
// so history survives between opens.
BarWidget {
  id: root
  moduleName: "bheemaguli.system-health-check"

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.settings
    if ("anchorItem" in target) target.anchorItem = button
    if ("hostWidget" in target) target.hostWidget = root
  }

  function togglePanel() {
    if (panelLoader.item && panelLoader.item.toggle) panelLoader.item.toggle()
  }

  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false

  function open() {
    if (panelLoader.item && panelLoader.item.openFromHotkey) panelLoader.item.openFromHotkey()
    else if (panelLoader.item && panelLoader.item.open) panelLoader.item.open()
  }

  function close() {
    if (panelLoader.item && panelLoader.item.close) panelLoader.item.close()
  }

  readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing === true : false

  function closeForPopoutSwitch() {
    if (panelLoader.item) panelLoader.item.closeForPopoutSwitch()
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  // WidgetButton (not BarIconButton): icon slots are fixed-width and cause
  // multi-digit CPU·RAM·GPU text to overflow into neighboring widgets.
  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: panelLoader.item ? panelLoader.item.chipLabel : "···"
    tooltipText: panelLoader.item ? panelLoader.item.chipTooltip : "System health"
    active: panelLoader.item ? panelLoader.item.alarming : false
    fontSize: Style.font.caption
    horizontalMargin: 8
    onPressed: function(b) {
      if (b === Qt.MiddleButton && panelLoader.item && panelLoader.item.refresh)
        panelLoader.item.refresh()
      else if (b === Qt.RightButton && panelLoader.item && panelLoader.item.openNetdata)
        panelLoader.item.openNetdata()
      else
        root.togglePanel()
    }
  }
}
