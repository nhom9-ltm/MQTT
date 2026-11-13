/* =========================================================
 *  Dashboard giám sát nhiệt độ / độ ẩm qua MQTT over WebSocket
 *  - MQTT.js  : kết nối broker, subscribe wildcard, publish lệnh
 *  - Chart.js : biểu đồ thời gian thực
 *  Topic: <prefix>/<room>/<device>/{telemetry|status|cmd}
 * ========================================================= */
(() => {
  "use strict";

  // ---------------- cấu hình ----------------
  const qs = new URLSearchParams(location.search);
  const DEFAULT_URL = qs.get("broker") ||
    `${location.protocol === "https:" ? "wss" : "ws"}://${location.hostname || "localhost"}:9001`;
  const KEEPALIVE = 30;
  const MAX_HISTORY_MS = 15 * 60 * 1000;
  const PALETTE = ["#ff8a3d", "#4aa8ff", "#3ccf7e", "#c084fc", "#f5b942", "#ff5d8f", "#2dd4bf", "#a3e635"];

  const $ = (s, r = document) => r.querySelector(s);
  const el = {
    url: $("#brokerUrl"), prefix: $("#topicPrefix"), form: $("#connForm"),
    btnConnect: $("#btnConnect"), btnDemo: $("#btnDemo"), pill: $("#connPill"),
    devices: $("#devices"), empty: $("#emptyDevices"), tpl: $("#tplDevice"),
    kOnline: $("#kOnline"), kClients: $("#kClients"), kMsgs: $("#kMsgs"),
    kUptime: $("#kUptime"), kRate: $("#kRate"),
    chartTitle: $("#chartTitle"), rangeSeg: $("#rangeSeg"),
    alerts: $("#alerts"), thT: $("#thT"), thH: $("#thH"),
    logBody: $("#logBody"), logFilter: $("#logFilter"), logPause: $("#logPause"), logClear: $("#logClear"),
    wcHint: $("#wcHint"), dashWill: $("#dashWill"), kaInfo: $("#kaInfo"),
  };

  const state = {
    client: null,
    demo: null,
    prefix: qs.get("prefix") || "iot",
    devices: new Map(),       // key "room/device"
    selected: null,
    rangeSec: 300,
    rxTimes: [],
    colorIdx: 0,
    clientId: "dash-" + Math.random().toString(16).slice(2, 8),
  };

  el.url.value = DEFAULT_URL;
  el.prefix.value = state.prefix;
  el.kaInfo.textContent = KEEPALIVE;

  // ---------------- tiện ích ----------------
  const pad = (n) => String(n).padStart(2, "0");
  const hms = (ms) => { const d = new Date(ms); return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`; };
  const ago = (ms) => {
    const s = Math.max(0, Math.round((Date.now() - ms) / 1000));
    if (s < 60) return `${s}s trước`;
    if (s < 3600) return `${Math.floor(s / 60)} phút trước`;
    return `${Math.floor(s / 3600)} giờ trước`;
  };
  const fmtUptime = (sec) => {
    const d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600), m = Math.floor(sec % 3600 / 60);
    return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m ${sec % 60}s`;
  };
  const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function setPill(cls, text) {
    el.pill.className = "pill " + cls;
    el.pill.querySelector("span").textContent = text;
  }

  // =========================================================
  //  KẾT NỐI MQTT
  // =========================================================
  function connect() {
    disconnectAll();
    state.prefix = el.prefix.value.trim() || "iot";
    resetDevices();
    updateHints();

    const willTopic = `${state.prefix}/_dashboard/${state.clientId}/status`;
    setPill("wait", "Đang kết nối…");

    const client = mqtt.connect(el.url.value.trim(), {
      clientId: state.clientId,
      clean: true,
      keepalive: KEEPALIVE,            // PINGREQ mỗi 30s nếu không có traffic
      reconnectPeriod: 2000,
      connectTimeout: 6000,
      will: {                          // Dashboard cũng có LWT riêng
        topic: willTopic,
        payload: JSON.stringify({ state: "offline", reason: "lwt" }),
        qos: 1, retain: false,
      },
    });
    state.client = client;

    client.on("connect", () => {
      setPill("on", "Đã kết nối");
      el.btnConnect.textContent = "Ngắt";
      // Wildcard: + khớp đúng 1 cấp, # khớp mọi cấp còn lại
      client.subscribe(`${state.prefix}/+/+/#`, { qos: 1 });
      // $SYS không khớp với wildcard bắt đầu bằng + hoặc # -> subscribe riêng
      client.subscribe([
        "$SYS/broker/clients/connected",
        "$SYS/broker/messages/received",
        "$SYS/broker/uptime",
      ], { qos: 0 });
      client.publish(willTopic, JSON.stringify({ state: "online", ts: Date.now() }), { qos: 1 });
    });
    client.on("reconnect", () => setPill("wait", "Đang kết nối lại…"));
    client.on("offline", () => setPill("off", "Mất kết nối broker"));
    client.on("error", (err) => { setPill("off", "Lỗi: " + (err.message || err)); });
    client.on("message", (topic, payload, packet) => {
      handleMessage(topic, payload.toString(), { qos: packet.qos, retain: packet.retain });
    });
  }

  function disconnectAll() {
    if (state.client) { state.client.removeAllListeners(); state.client.end(true); state.client = null; }
    if (state.demo) { state.demo.stop(); state.demo = null; }
    el.btnConnect.textContent = "Kết nối";
    el.btnDemo.textContent = "Demo";
    setPill("", "Chưa kết nối");
  }

  function publishCmd(dev, cmd) {
    const topic = `${state.prefix}/${dev.room}/${dev.id}/cmd`;
    const body = JSON.stringify({ ...cmd, ts: Date.now(), from: state.clientId });
    if (state.demo) state.demo.command(dev, cmd, topic, body);
    else if (state.client && state.client.connected) state.client.publish(topic, body, { qos: 1, retain: false });
    else return addAlert("warn", "Chưa kết nối broker — không gửi được lệnh");
  }

  function updateHints() {
    el.wcHint.textContent = `${state.prefix}/+/+/#`;
    el.dashWill.textContent = `${state.prefix}/_dashboard/${state.clientId}/status`;
  }

  // =========================================================
  //  XỬ LÝ MESSAGE
  // =========================================================
  function handleMessage(topic, text, meta = {}) {
    if (!meta.silent) {
      state.rxTimes.push(Date.now());
      logMessage(topic, text, meta);
    }

    if (topic.startsWith("$SYS/")) return handleSys(topic, text);

    const parts = topic.split("/");
    if (parts.length !== 4 || parts[0] !== state.prefix) return;
    const [, room, id, kind] = parts;
    if (room.startsWith("_")) return;                 // bỏ qua client hệ thống (dashboard)

    if (text === "") {                                 // retained bị xóa
      if (kind === "status") removeDevice(`${room}/${id}`);
      return;
    }
    let data;
    try { data = JSON.parse(text); } catch { return; }

    if (kind === "telemetry") onTelemetry(room, id, data, meta);
    else if (kind === "status") onStatus(room, id, data, meta);
  }

  function handleSys(topic, text) {
    if (topic.endsWith("clients/connected")) el.kClients.textContent = text;
    else if (topic.endsWith("messages/received")) el.kMsgs.textContent = Number(text).toLocaleString("vi-VN");
    else if (topic.endsWith("uptime")) el.kUptime.textContent = fmtUptime(parseInt(text, 10) || 0);
  }

  function onTelemetry(room, id, d, meta) {
    const dev = upsertDevice(room, id);
    const ts = d.ts || Date.now();
    const t = Number(d.temperature), h = Number(d.humidity);
    if (!Number.isFinite(t) || !Number.isFinite(h)) return;

    dev.temp = t; dev.hum = h; dev.lastTs = ts; dev.battery = d.battery; dev.rssi = d.rssi;
    dev.lastRx = meta.retain ? ts : Date.now();
    dev.fromRetained = !!meta.retain;
    dev.lastQos = meta.qos;
    if (!dev.history.length || ts > dev.history[dev.history.length - 1].x) {
      dev.history.push({ x: ts, t, h });
    }
    const cut = Date.now() - MAX_HISTORY_MS;
    while (dev.history.length && dev.history[0].x < cut) dev.history.shift();

    if (!meta.silent) {
      renderDevice(dev, true);
      checkThreshold(dev, meta);
      scheduleCharts();
    }
  }

  function onStatus(room, id, d, meta) {
    const dev = upsertDevice(room, id);
    const prev = dev.status;
    dev.status = d.state || "unknown";
    dev.reason = d.reason || null;
    if (d.interval) dev.interval = d.interval;
    if (d.state === "online" && !meta.retain) dev.lastRx = Date.now();
    if (meta.silent) return;
    renderDevice(dev);

    const name = `${dev.room}/${dev.id}`;
    if (meta.retain) {
      if (dev.status === "offline") addAlert("warn", `${name} đang offline (thông điệp retained có sẵn trên broker${dev.reason === "lwt" ? ", do LWT" : ""})`);
      return;
    }
    if (dev.status === "offline" && dev.reason === "lwt") {
      addAlert("bad", `${name} mất kết nối đột ngột — broker phát Last Will`);
    } else if (dev.status === "offline") {
      addAlert("warn", `${name} tắt có kiểm soát (graceful disconnect, không có LWT)`);
    } else if (dev.status === "online" && prev && prev !== "online" && prev !== "paused") {
      addAlert("ok", `${name} đã online trở lại`);
    }
    updateKpis();
  }

  // =========================================================
  //  THIẾT BỊ (UI)
  // =========================================================
  function upsertDevice(room, id) {
    const key = `${room}/${id}`;
    let dev = state.devices.get(key);
    if (dev) return dev;

    const node = el.tpl.content.firstElementChild.cloneNode(true);
    dev = {
      key, room, id, node, status: null, reason: null, temp: null, hum: null,
      lastTs: 0, lastRx: 0, interval: 2, history: [], alarm: false,
      color: PALETTE[state.colorIdx++ % PALETTE.length],
    };
    node.querySelector(".dev-room").textContent = room;
    node.querySelector(".dev-id").textContent = id;
    node.addEventListener("click", (e) => { if (!e.target.closest(".dev-cmd")) select(key); });
    node.addEventListener("keydown", (e) => { if (e.key === "Enter") select(key); });

    const sel = node.querySelector(".sel-interval");
    sel.addEventListener("change", () => publishCmd(dev, { action: "set_interval", value: Number(sel.value) }));
    node.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", () => {
      const act = b.dataset.act;
      if (act === "toggle") publishCmd(dev, { action: dev.status === "paused" ? "resume" : "pause" });
      else publishCmd(dev, { action: act });
    }));

    state.devices.set(key, dev);
    // sắp xếp theo tên phòng
    const sorted = [...state.devices.values()].sort((a, b) => a.key.localeCompare(b.key));
    const idx = sorted.indexOf(dev);
    const next = sorted[idx + 1];
    el.devices.insertBefore(node, next ? next.node : null);
    el.empty.style.display = "none";

    addCmpDataset(dev);
    if (!state.selected) select(key);
    return dev;
  }

  function removeDevice(key) {
    const dev = state.devices.get(key);
    if (!dev) return;
    dev.node.remove();
    state.devices.delete(key);
    cmpChart.data.datasets = cmpChart.data.datasets.filter((ds) => ds._key !== key);
    if (state.selected === key) state.selected = null;
    if (!state.devices.size) el.empty.style.display = "";
    updateKpis(); scheduleCharts();
  }

  function resetDevices() {
    for (const d of state.devices.values()) d.node.remove();
    state.devices.clear();
    state.selected = null;
    state.colorIdx = 0;
    cmpChart.data.datasets = [];
    mainChart.data.datasets.forEach((ds) => (ds.data = []));
    el.empty.style.display = "";
    el.chartTitle.textContent = "Biểu đồ thời gian thực";
    ["kClients", "kMsgs", "kUptime"].forEach((k) => (el[k].textContent = "—"));
    updateKpis(); scheduleCharts();
  }

  function effectiveStatus(dev) {
    if (dev.status === "online") {
      const limit = Math.max(10, dev.interval * 4) * 1000;
      if (dev.lastRx && Date.now() - dev.lastRx > limit) return "stale";
    }
    return dev.status || "unknown";
  }

  function renderDevice(dev, flash = false) {
    const n = dev.node;
    const st = effectiveStatus(dev);
    const badge = n.querySelector(".badge");
    const label = {
      online: "● Online", paused: "Tạm dừng", stale: "Không có dữ liệu", unknown: "Chưa rõ",
      offline: dev.reason === "lwt" ? "Offline · LWT" : "Offline",
    }[st] || st;
    badge.textContent = label;
    badge.className = "badge " + (st === "unknown" ? "" : st);

    n.classList.toggle("offline", st === "offline");
    n.classList.toggle("alarm", dev.alarm && st !== "offline");
    n.querySelector(".v.t .num").textContent = dev.temp == null ? "—" : dev.temp.toFixed(1);
    n.querySelector(".v.h .num").textContent = dev.hum == null ? "—" : dev.hum.toFixed(0);
    n.querySelector(".seen").textContent = dev.lastTs ? "Cập nhật " + ago(dev.lastTs) : "—";

    const tags = [];
    if (dev.fromRetained) tags.push('<span class="tag ret" title="Giá trị lấy từ retained message">RETAINED</span>');
    if (dev.lastQos != null) tags.push(`<span class="tag">QoS ${dev.lastQos}</span>`);
    if (dev.battery != null) tags.push(`<span class="tag">🔋${Math.round(dev.battery)}%</span>`);
    n.querySelector(".tags").innerHTML = tags.join("");

    const toggle = n.querySelector('[data-act="toggle"]');
    toggle.textContent = dev.status === "paused" ? "Tiếp tục" : "Tạm dừng";
    n.querySelectorAll(".dev-cmd button, .dev-cmd select").forEach((b) => (b.disabled = dev.status === "offline"));
    const sel = n.querySelector(".sel-interval");
    if (document.activeElement !== sel && [...sel.options].some((o) => Number(o.value) === dev.interval)) sel.value = String(dev.interval);

    drawSpark(dev);
    if (flash) { n.classList.remove("flash"); void n.offsetWidth; n.classList.add("flash"); }
    updateKpis();
  }

  function drawSpark(dev) {
    const c = dev.node.querySelector(".spark");
    const w = c.clientWidth || 240, h = 34, dpr = window.devicePixelRatio || 1;
    if (c.width !== w * dpr) { c.width = w * dpr; c.height = h * dpr; }
    const ctx = c.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const pts = dev.history.slice(-60);
    if (pts.length < 2) return;
    const vals = pts.map((p) => p.t);
    const min = Math.min(...vals) - 0.2, max = Math.max(...vals) + 0.2;
    ctx.beginPath();
    pts.forEach((p, i) => {
      const x = (i / (pts.length - 1)) * w;
      const y = h - 3 - ((p.t - min) / (max - min)) * (h - 6);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.strokeStyle = cssVar("--temp");
    ctx.lineWidth = 1.6;
    ctx.stroke();
  }

  function select(key) {
    state.selected = key;
    for (const d of state.devices.values()) d.node.classList.toggle("selected", d.key === key);
    const dev = state.devices.get(key);
    if (dev) el.chartTitle.textContent = `${dev.room} · ${dev.id}`;
    scheduleCharts();
  }

  function updateKpis() {
    const all = [...state.devices.values()];
    const on = all.filter((d) => ["online", "paused"].includes(effectiveStatus(d))).length;
    el.kOnline.textContent = `${on}/${all.length}`;
  }

  // =========================================================
  //  CẢNH BÁO
  // =========================================================
  function checkThreshold(dev, meta) {
    const tMax = Number(el.thT.value), hMax = Number(el.thH.value);
    const bad = dev.temp > tMax || dev.hum > hMax;
    if (bad && !dev.alarm && !meta.retain) {
      const what = dev.temp > tMax ? `nhiệt độ ${dev.temp.toFixed(1)}°C > ${tMax}°C` : `độ ẩm ${dev.hum.toFixed(0)}% > ${hMax}%`;
      addAlert("bad", `${dev.room}/${dev.id}: ${what}`);
    } else if (!bad && dev.alarm) {
      addAlert("ok", `${dev.room}/${dev.id}: trở lại bình thường`);
    }
    dev.alarm = bad;
    renderDevice(dev);
  }

  function addAlert(level, text) {
    const first = el.alerts.querySelector(".muted");
    if (first) first.remove();
    const li = document.createElement("li");
    li.className = level;
    li.innerHTML = `<time>${hms(Date.now())}</time>${esc(text)}`;
    el.alerts.prepend(li);
    while (el.alerts.children.length > 50) el.alerts.lastChild.remove();
  }

  // =========================================================
  //  MESSAGE LOG
  // =========================================================
  function logMessage(topic, text, meta) {
    if (el.logPause.checked) return;
    const f = el.logFilter.value.trim();
    if (f && !topic.includes(f)) return;
    const tr = document.createElement("tr");
    const kind = topic.startsWith("$SYS") ? "sys" : topic.split("/")[3] || "";
    tr.className = kind + (text.includes('"lwt"') ? " lwt" : "");
    tr.innerHTML =
      `<td>${hms(Date.now())}</td><td class="topic">${esc(topic)}</td><td>${meta.qos ?? "-"}</td>` +
      `<td>${meta.retain ? '<span class="yes">✓</span>' : ""}</td><td class="payload" title="${esc(text)}">${esc(text || "(rỗng)")}</td>`;
    el.logBody.prepend(tr);
    while (el.logBody.children.length > 200) el.logBody.lastChild.remove();
  }

  // =========================================================
  //  BIỂU ĐỒ
  // =========================================================
  Chart.defaults.font.family = '"Be Vietnam Pro", system-ui, sans-serif';
  Chart.defaults.color = cssVar("--muted");
  Chart.defaults.borderColor = cssVar("--line");

  const timeAxis = () => ({
    type: "linear",
    ticks: { maxTicksLimit: 6, callback: (v) => hms(v).slice(0, 5 + (state.rangeSec <= 60 ? 3 : 0)) },
    grid: { display: false },
  });

  const mainChart = new Chart($("#mainChart"), {
    type: "line",
    data: {
      datasets: [
        { label: "Nhiệt độ (°C)", data: [], yAxisID: "yT", borderColor: cssVar("--temp"),
          backgroundColor: cssVar("--temp") + "22", fill: true, tension: 0.35, pointRadius: 0, borderWidth: 2 },
        { label: "Độ ẩm (%)", data: [], yAxisID: "yH", borderColor: cssVar("--hum"),
          backgroundColor: "transparent", tension: 0.35, pointRadius: 0, borderWidth: 2 },
      ],
    },
    options: {
      animation: false, responsive: true, maintainAspectRatio: false, parsing: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: timeAxis(),
        yT: { position: "left", title: { display: true, text: "°C" }, grace: "10%" },
        yH: { position: "right", title: { display: true, text: "%" }, grid: { display: false }, grace: "10%" },
      },
      plugins: {
        legend: { labels: { usePointStyle: true, boxWidth: 8 } },
        tooltip: { callbacks: { title: (it) => it.length ? hms(it[0].parsed.x) : "" } },
      },
    },
  });

  const cmpChart = new Chart($("#cmpChart"), {
    type: "line",
    data: { datasets: [] },
    options: {
      animation: false, responsive: true, maintainAspectRatio: false, parsing: false,
      interaction: { mode: "nearest", intersect: false },
      scales: { x: timeAxis(), y: { title: { display: true, text: "°C" }, grace: "10%" } },
      plugins: {
        legend: { labels: { usePointStyle: true, boxWidth: 8 } },
        tooltip: { callbacks: { title: (it) => it.length ? hms(it[0].parsed.x) : "" } },
      },
    },
  });

  function addCmpDataset(dev) {
    cmpChart.data.datasets.push({
      _key: dev.key, label: dev.room, data: [], borderColor: dev.color, backgroundColor: dev.color,
      tension: 0.35, pointRadius: 0, borderWidth: 1.8,
    });
  }

  let chartPending = false;
  function scheduleCharts() {
    if (chartPending) return;
    chartPending = true;
    requestAnimationFrame(() => { chartPending = false; drawCharts(); });
  }

  function drawCharts() {
    const now = Date.now(), min = now - state.rangeSec * 1000;
    const inRange = (p) => p.x >= min - 5000;

    const dev = state.devices.get(state.selected);
    const pts = dev ? dev.history.filter(inRange) : [];
    mainChart.data.datasets[0].data = pts.map((p) => ({ x: p.x, y: p.t }));
    mainChart.data.datasets[1].data = pts.map((p) => ({ x: p.x, y: p.h }));
    mainChart.options.scales.x.min = min; mainChart.options.scales.x.max = now;
    mainChart.update("none");

    for (const ds of cmpChart.data.datasets) {
      const d = state.devices.get(ds._key);
      ds.data = d ? d.history.filter(inRange).map((p) => ({ x: p.x, y: p.t })) : [];
    }
    cmpChart.options.scales.x.min = min; cmpChart.options.scales.x.max = now;
    cmpChart.update("none");
  }

  // Cập nhật mỗi giây: trượt trục thời gian, "x giây trước", phát hiện mất tín hiệu
  setInterval(() => {
    const now = Date.now();
    state.rxTimes = state.rxTimes.filter((t) => now - t < 60000);
    el.kRate.textContent = state.rxTimes.length;
    for (const d of state.devices.values()) renderDevice(d);
    scheduleCharts();
  }, 1000);

  // =========================================================
  //  DEMO MODE — giả lập broker + 3 cảm biến ngay trong trình duyệt
  // =========================================================
  class DemoBroker {
    constructor(emit) {
      this.emit = emit;
      this.timers = [];
      this.devs = [
        { room: "living", id: "sensor-01", bt: 28, bh: 62 },
        { room: "bedroom", id: "sensor-02", bt: 26.5, bh: 58 },
        { room: "server", id: "sensor-03", bt: 24, bh: 45 },
      ].map((d) => ({ ...d, interval: 2, paused: false, online: true, seq: 0, dt: 0, dh: 0, spike: 0, bat: 95 + Math.random() * 5 }));
    }
    topic(d, k) { return `${state.prefix}/${d.room}/${d.id}/${k}`; }
    read(d, at) {
      const hr = new Date(at).getHours() + new Date(at).getMinutes() / 60;
      const daily = Math.sin((hr - 9) / 24 * 2 * Math.PI);
      d.dt = Math.max(-1.5, Math.min(1.5, d.dt + (Math.random() - 0.5) * 0.2));
      d.dh = Math.max(-5, Math.min(5, d.dh + (Math.random() - 0.5) * 0.8));
      let t = d.bt + 2.5 * daily + d.dt + (Math.random() - 0.5) * 0.3;
      let h = d.bh - 6 * daily + d.dh + (Math.random() - 0.5) * 1.2;
      if (at < d.spike) { t += 12 + Math.random() * 2; h -= 15; }
      d.bat = Math.max(0, d.bat - 0.003);
      return { t: +t.toFixed(2), h: +Math.max(0, Math.min(100, h)).toFixed(1) };
    }
    telemetry(d, at, meta) {
      const { t, h } = this.read(d, at);
      const body = { device: d.id, room: d.room, temperature: t, humidity: h, battery: +d.bat.toFixed(1),
        rssi: -45 - Math.round(Math.random() * 30), seq: ++d.seq, ts: at };
      this.emit(this.topic(d, "telemetry"), JSON.stringify(body), meta);
    }
    status(d, st, meta, reason) {
      const body = st === "offline" && reason === "lwt"
        ? { state: "offline", reason: "lwt" }
        : { state: st, ts: Date.now(), interval: d.interval, qos: 1, keepalive: 10, fw: "demo-1.0", ...(reason ? { reason } : {}) };
      this.emit(this.topic(d, "status"), JSON.stringify(body), meta);
    }
    start() {
      const now = Date.now();
      // lịch sử 5 phút để biểu đồ có sẵn đường (không ghi log)
      for (const d of this.devs) for (let at = now - 300000; at < now - 2000; at += 2000) this.telemetry(d, at, { qos: 1, retain: false, silent: true });
      // giống broker thật: subscriber mới nhận ngay các retained message
      for (const d of this.devs) { this.status(d, "online", { qos: 1, retain: true }); this.telemetry(d, now, { qos: 1, retain: true }); }
      for (const d of this.devs) this.loop(d);
      // $SYS
      let msgs = 18234, up = 7380;
      this.timers.push(setInterval(() => {
        msgs += 9 + Math.round(Math.random() * 4); up += 5;
        this.emit("$SYS/broker/clients/connected", String(this.devs.filter((d) => d.online).length + 2), { qos: 0, retain: true });
        this.emit("$SYS/broker/messages/received", String(msgs), { qos: 0, retain: true });
        this.emit("$SYS/broker/uptime", `${up} seconds`, { qos: 0, retain: true });
      }, 5000));
    }
    loop(d) {
      clearTimeout(d.timer);
      d.timer = setTimeout(() => {
        if (d.online && !d.paused) this.telemetry(d, Date.now(), { qos: 1, retain: false });
        if (d.online) this.loop(d);
      }, d.interval * 1000);
    }
    command(dev, cmd, topic, body) {
      this.emit(topic, body, { qos: 1, retain: false });
      const d = this.devs.find((x) => x.id === dev.id && x.room === dev.room);
      if (!d || !d.online) return;
      setTimeout(() => {
        if (cmd.action === "set_interval") { d.interval = cmd.value; this.status(d, "online", { qos: 1, retain: false }); this.loop(d); }
        if (cmd.action === "pause") { d.paused = true; this.status(d, "paused", { qos: 1, retain: false }); }
        if (cmd.action === "resume") { d.paused = false; this.status(d, "online", { qos: 1, retain: false }); }
        if (cmd.action === "spike") d.spike = Date.now() + 20000;
        if (cmd.action === "crash") {
          d.online = false; clearTimeout(d.timer);
          addAlert("warn", `${d.room}/${d.id}: socket bị ngắt, broker chờ hết keep-alive (≈1.5 × 10s)…`);
          // broker phát hiện client chết sau 1.5 × keep-alive -> publish LWT
          this.timers.push(setTimeout(() => this.status(d, "offline", { qos: 1, retain: false }, "lwt"), 6000));
          // tự "cắm điện lại" sau 20s
          this.timers.push(setTimeout(() => { d.online = true; this.status(d, "online", { qos: 1, retain: false }); this.loop(d); }, 20000));
        }
      }, 150);
    }
    stop() { this.timers.forEach(clearTimeout); this.timers.forEach(clearInterval); this.devs.forEach((d) => clearTimeout(d.timer)); }
  }

  function startDemo() {
    disconnectAll();
    state.prefix = el.prefix.value.trim() || "iot";
    resetDevices(); updateHints();
    state.demo = new DemoBroker(handleMessage);
    state.demo.start();
    setPill("demo", "Demo (giả lập trong trình duyệt)");
    el.btnDemo.textContent = "Dừng demo";
    scheduleCharts();
  }

  // ---------------- sự kiện UI ----------------
  el.form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (state.client) { disconnectAll(); return; }
    if (typeof mqtt === "undefined") { setPill("off", "Không tải được MQTT.js (cần Internet cho CDN)"); return; }
    connect();
  });
  el.btnDemo.addEventListener("click", () => (state.demo ? disconnectAll() : startDemo()));
  el.rangeSeg.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    el.rangeSeg.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    state.rangeSec = Number(b.dataset.range);
    scheduleCharts();
  });
  el.logClear.addEventListener("click", () => (el.logBody.innerHTML = ""));
  [el.thT, el.thH].forEach((i) => i.addEventListener("change", () => {
    for (const d of state.devices.values()) if (d.temp != null) checkThreshold(d, { retain: false });
  }));

  updateHints();
  if (qs.get("demo") === "1") startDemo();
  else if (typeof mqtt !== "undefined") connect();
})();
