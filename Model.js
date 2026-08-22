.pragma library

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v))
}

function pct(v) {
  if (v === null || v === undefined || !isFinite(Number(v))) return "—"
  return Math.round(Number(v)) + "%"
}

function pctShort(v) {
  if (v === null || v === undefined || !isFinite(Number(v))) return "—"
  return String(Math.round(Number(v)))
}

function gb(v) {
  if (v === null || v === undefined || !isFinite(Number(v))) return "—"
  var n = Number(v)
  return (n < 10 ? n.toFixed(1) : String(Math.round(n))) + " GB"
}

function statLine(stat) {
  if (!stat || stat.avg === null || stat.avg === undefined) return "avg —   peak —"
  return "avg " + pct(stat.avg) + "   peak " + pct(stat.peak)
}

function alarming(now, cpuWarn, ramWarn, gpuWarn) {
  if (!now) return false
  if (now.cpu != null && Number(now.cpu) >= cpuWarn) return true
  if (now.ram != null && Number(now.ram) >= ramWarn) return true
  if (now.gpu != null && Number(now.gpu) >= gpuWarn) return true
  return false
}

function barLabel(payload) {
  if (!payload || !payload.online) return "ND?"
  var now = payload.now || {}
  var parts = []
  parts.push(pctShort(now.cpu))
  parts.push(pctShort(now.ram))
  if (now.gpu !== null && now.gpu !== undefined) parts.push(pctShort(now.gpu))
  return parts.join("·")
}

function barTooltip(payload) {
  if (!payload) return "System health"
  if (!payload.online) return "Netdata offline — click for setup"
  var now = payload.now || {}
  var bits = [
    "CPU " + pct(now.cpu),
    "RAM " + pct(now.ram),
  ]
  if (now.gpu !== null && now.gpu !== undefined) bits.push("GPU " + pct(now.gpu))
  if (now.ram_used_gb != null && now.ram_total_gb != null)
    bits.push(gb(now.ram_used_gb) + " / " + gb(now.ram_total_gb))
  return bits.join("  ·  ")
}

function sparkPath(values, width, height) {
  var pts = []
  var list = values || []
  var n = list.length
  if (n === 0) return ""
  var max = 1
  for (var i = 0; i < n; i++) {
    var v = Number(list[i])
    if (isFinite(v) && v > max) max = v
  }
  for (var j = 0; j < n; j++) {
    var raw = list[j]
    var yv = (raw === null || raw === undefined || !isFinite(Number(raw))) ? 0 : Number(raw)
    var x = n === 1 ? 0 : (j / (n - 1)) * width
    var y = height - (clamp(yv, 0, max) / max) * height
    pts.push((j === 0 ? "M" : "L") + x.toFixed(1) + " " + y.toFixed(1))
  }
  return pts.join(" ")
}

function windowKeys() {
  return ["1h", "24h", "7d"]
}
