/* =========================================================
 *  Dashboard Nhà thông minh qua MQTT over WebSocket
 *  - MQTT.js  : kết nối broker, subscribe wildcard, publish lệnh
 *  - Chart.js : biểu đồ nhiệt độ & công suất
 *  Topic: <prefix>/<phòng>/<thiết bị>/{status|state|set}
 *         <prefix>/_auto/{engine|mode|scene|rule|notify}/...
 *  Dashboard KHÔNG tự đổi giao diện khi bấm nút: nó publish lệnh lên .../set
 *  và chỉ vẽ lại khi thiết bị báo trạng thái mới trên .../state.
 * ========================================================= */
(() => {
  "use strict";

  // ---------------- cấu hình ----------------
  const qs = new URLSearchParams(location.search);
  const DEFAULT_URL = qs.get("broker") ||
    `${location.protocol === "https:" ? "wss" : "ws"}://${location.hostname || "localhost"}:9001`;
  const KEEPALIVE = 30;
  const HISTORY_MS = 30 * 60 * 1000;
  const PENDING_MS = 4000;            // quá thời gian này mà thiết bị chưa báo state -> cảnh báo
  const ROOM_ORDER = ["living", "bedroom", "kitchen", "entrance", "lab"];
  const TYPE_ORDER = ["climate", "light", "fan", "ac", "curtain", "plug", "lock", "door", "motion", "gas", "node"];
  const PALETTE = ["#ff8a3d", "#4aa8ff", "#3ccf7e", "#c084fc", "#f5b942", "#ff5d8f", "#2dd4bf", "#a3e635"];
  const SWITCHABLE = new Set(["light", "fan", "ac", "plug"]);
  const TRIGGER_LABEL = { climate: "Nắng nóng", motion: "Giả lập", door: "Mở cửa", gas: "Rò rỉ gas" };
  const AC_MODE = { cool: "Làm lạnh", dry: "Hút ẩm", fan: "Quạt" };

  const ICON = {
    light: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.6 1.1 1.3 1.1 2.2h5c0-.9.4-1.6 1.1-2.2A6 6 0 0 0 12 3z"/>',
    fan: '<circle cx="12" cy="12" r="1.8"/><path d="M12 10.2C11 6.5 12.2 3.5 14.6 4c2 .4 1.8 3.4-.8 5.4M13.8 12c3.7-1 6.7.2 6.2 2.6-.4 2-3.4 1.8-5.4-.8M12 13.8c1 3.7-.2 6.7-2.6 6.2-2-.4-1.8-3.4.8-5.4M10.2 12C6.5 13 3.5 11.8 4 9.4c.4-2 3.4-1.8 5.4.8"/>',
    ac: '<rect x="3" y="5" width="18" height="8" rx="2"/><path d="M7 10h10M8 16.5c0 1.2-1 1.5-1 2.5M12 16.5v3M16 16.5c0 1.2 1 1.5 1 2.5"/>',
    curtain: '<path d="M3 4h18M5 4v16M19 4v16M5 4c0 6 2.5 10 5 16M19 4c0 6-2.5 10-5 16"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4M12 15v2"/>',
    unlock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.6-1.8M12 15v2"/>',
    plug: '<path d="M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4"/>',
    climate: '<path d="M12 3a2 2 0 0 0-2 2v8.3a4 4 0 1 0 4 0V5a2 2 0 0 0-2-2z"/><path d="M12 9v8"/>',
    motion: '<circle cx="13" cy="4.5" r="1.8"/><path d="M8 21l3-6 2 2 1 4M11 15l1-5 3 3h3M12 10l-3 1-2 3"/>',
    door: '<path d="M6 21V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v17M4 21h16M14.5 12.5v.01"/>',
    gas: '<path d="M12 21c-3.9 0-6-2.6-6-5.6 0-3.6 3-5.3 3.5-9.4C12 7.5 14 10 14 12.2c.8-.4 1.5-1.4 1.7-2.6 1.7 1.4 2.3 3.6 2.3 5.6 0 3.2-2.4 5.8-6 5.8z"/>',
    node: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
    generic: '<circle cx="12" cy="12" r="8"/>',
  };
  const svg = (name) => `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">${ICON[name] || ICON.generic}</svg>`;

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const el = {
    url: $("#brokerUrl"), prefix: $("#topicPrefix"), form: $("#connForm"),
    btnConnect: $("#btnConnect"), btnDemo: $("#btnDemo"), pill: $("#connPill"),
    enginePill: $("#enginePill"), modeSeg: $("#modeSeg"), scenes: $("#scenes"), sceneTopic: $("#sceneTopic"),
    rules: $("#rules"), alerts: $("#alerts"), alertClear: $("#alertClear"), toasts: $("#toasts"),
    rooms: $("#rooms"), tabs: $("#roomTabs"), empty: $("#emptyDevices"),
    kTemp: $("#kTemp"), kHum: $("#kHum"), kPower: $("#kPower"), kLights: $("#kLights"),
    kDoor: $("#kDoor"), kOnline: $("#kOnline"), kClients: $("#kClients"), kRate: $("#kRate"),
    rangeSeg: $("#rangeSeg"), energyHint: $("#energyHint"),
    logBody: $("#logBody"), logFilter: $("#logFilter"), logPause: $("#logPause"),
    logHide: $("#logHideState"), logClear: $("#logClear"),
    wcHint: $("#wcHint"), dashWill: $("#dashWill"), kaInfo: $("#kaInfo"),
  };

  const state = {
    client: null,
    demo: null,
    prefix: qs.get("prefix") || "home",
    devices: new Map(),       // "phòng/thiết bị" -> dev
    rooms: new Map(),         // phòng -> {id, name, sec, grid}
    roomFilter: "all",
    engine: null,
    mode: null,
    rangeSec: 300,
    rxTimes: [],
    power: [],                // [{x, y}] tổng công suất theo thời gian
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
  const fmtW = (w) => w >= 1000 ? `${(w / 1000).toFixed(2)} kW` : `${Math.round(w)} W`;
  const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const orderOf = (list, v) => { const i = list.indexOf(v); return i < 0 ? list.length : i; };

  function setPill(pill, cls, text) {
    pill.className = pill.className.replace(/\b(on|off|wait|demo)\b/g, "").trim() + (cls ? " " + cls : "");
    pill.querySelector("span").textContent = text;
  }

  // =========================================================
  //  KẾT NỐI MQTT
  // =========================================================
  function connect() {
    disconnectAll();
    state.prefix = el.prefix.value.trim() || "home";
    resetAll();

    const willTopic = `${state.prefix}/_dashboard/${state.clientId}/status`;
    setPill(el.pill, "wait", "Đang kết nối…");

    const client = mqtt.connect(el.url.value.trim(), {
      clientId: state.clientId,
      clean: true,
      keepalive: KEEPALIVE,
      reconnectPeriod: 2000,
      connectTimeout: 6000,
      will: {
        topic: willTopic,
        payload: JSON.stringify({ state: "offline", reason: "lwt" }),
        qos: 1, retain: false,
      },
    });
    state.client = client;

    client.on("connect", () => {
      setPill(el.pill, "on", "Đã kết nối");
      el.btnConnect.textContent = "Ngắt";
      // Mọi topic của hệ thống đều có đúng 4 cấp: + khớp đúng 1 cấp
      client.subscribe(`${state.prefix}/+/+/+`, { qos: 1 });
      // $SYS không khớp với wildcard bắt đầu bằng + hoặc # -> subscribe riêng
      client.subscribe(["$SYS/broker/clients/connected", "$SYS/broker/messages/received"], { qos: 0 });
      client.publish(willTopic, JSON.stringify({ state: "online", ts: Date.now() }), { qos: 1 });
    });
    client.on("reconnect", () => setPill(el.pill, "wait", "Đang kết nối lại…"));
    client.on("offline", () => setPill(el.pill, "off", "Mất kết nối broker"));
    client.on("error", (err) => setPill(el.pill, "off", "Lỗi: " + (err.message || err)));
    client.on("message", (topic, payload, packet) => {
      handleMessage(topic, payload.toString(), { qos: packet.qos, retain: packet.retain });
    });
  }

  function disconnectAll() {
    if (state.client) { state.client.removeAllListeners(); state.client.end(true); state.client = null; }
    if (state.demo) { state.demo.stop(); state.demo = null; }
    el.btnConnect.textContent = "Kết nối";
    el.btnDemo.textContent = "Demo";
    setPill(el.pill, "", "Chưa kết nối");
  }

  function send(topic, obj) {
    const body = JSON.stringify({ ...obj, from: "dashboard", ts: Date.now() });
    if (state.demo) { state.demo.publish(topic, body); return true; }
    if (state.client && state.client.connected) { state.client.publish(topic, body, { qos: 1, retain: false }); return true; }
    addAlert("warn", "Chưa kết nối broker — không gửi được lệnh");
    return false;
  }

  function command(dev, payload) {
    if (!send(`${state.prefix}/${dev.room}/${dev.id}/set`, payload)) return;
    if (payload.action !== "crash") { dev.pending = Date.now(); renderDevice(dev); }
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

    let data = null;
    if (text !== "") { try { data = JSON.parse(text); } catch { return; } }

    if (room === "_auto") return onAuto(id, kind, data || {}, meta);
    if (room.startsWith("_")) return;                    // client hệ thống khác (dashboard)

    if (kind === "status") {
      if (data === null) return removeDevice(`${room}/${id}`);   // retained bị xóa
      onStatus(room, id, data, meta);
    } else if (kind === "state" && data) {
      onState(room, id, data, meta);
    } else if (kind === "set" && data) {
      const dev = state.devices.get(`${room}/${id}`);
      if (dev) { dev.lastCmd = { from: data.from || "?", via: data.via, ts: Date.now() }; renderDevice(dev); }
    }
  }

  function handleSys(topic, text) {
    if (topic.endsWith("clients/connected")) el.kClients.textContent = text;
  }

  function onStatus(room, id, d, meta) {
    const dev = upsertDevice(room, id);
    const prev = dev.status;
    dev.status = d.state || "unknown";
    dev.reason = d.reason || null;
    if (d.type) {             // status đầy đủ (discovery); payload LWT chỉ có state + reason
      dev.type = d.type;
      dev.name = d.name || id;
      dev.caps = d.caps || {};
      dev.sim = !!d.sim;
      dev.node = d.node || null;
      dev.info = d;
    }
    if (d.room_name) ensureRoom(room, d.room_name);
    renderDevice(dev);
    if (dev.type === "node") for (const c of state.devices.values()) if (c.node === id && c.room === room) renderDevice(c);
    updateKpis();

    const name = `${dev.name} (${room})`;
    if (meta.retain || meta.silent) {
      if (dev.status === "offline" && dev.reason === "lwt") addAlert("warn", `${name} đang offline (LWT retained trên broker)`);
      return;
    }
    if (dev.status === "offline" && dev.reason === "lwt") addAlert("bad", `${name} mất kết nối đột ngột — broker phát Last Will`);
    else if (dev.status === "offline") addAlert("warn", `${name} tắt có kiểm soát (không có LWT)`);
    else if (dev.status === "online" && prev === "offline") addAlert("ok", `${name} đã online trở lại`);
  }

  function onState(room, id, d, meta) {
    const dev = upsertDevice(room, id);
    const prev = dev.state;
    dev.state = d;
    dev.lastState = d.ts || Date.now();
    dev.fromRetained = !!meta.retain;
    dev.pending = 0;
    if (dev.type === "climate" || d.temperature != null) {
      const x = d.ts || Date.now();
      const h = dev.history;
      if (!h.length || x > h[h.length - 1].x) h.push({ x, t: Number(d.temperature), h: Number(d.humidity) });
      const cut = Date.now() - HISTORY_MS;
      while (h.length && h[0].x < cut) h.shift();
    }
    if (dev.type === "motion" && d.motion) dev.lastMotion = d.last_motion || Date.now();
    if (!meta.silent) {
      renderDevice(dev, true);
      if (!meta.retain) localAlerts(dev, prev, d);
      updateKpis();
      scheduleCharts();
    }
  }

  // Cảnh báo do chính thiết bị báo (độc lập với automation engine)
  function localAlerts(dev, prev, s) {
    if (dev.type === "gas" && s.alarm && !prev.alarm) toast("bad", `${dev.name}: ${s.ppm} ppm — nguy hiểm!`);
    if (dev.type === "gas" && !s.alarm && prev.alarm) addAlert("ok", `${dev.name}: nồng độ gas đã an toàn`);
  }

  function onAuto(what, kind, d, meta) {
    if (what === "engine" && kind === "status") {
      const wasOnline = state.engine && state.engine.state === "online";
      state.engine = d.state === "offline" ? { ...(state.engine || {}), state: "offline", reason: d.reason } : d;
      if (wasOnline && d.state === "offline" && !meta.retain) {
        addAlert(d.reason === "lwt" ? "bad" : "warn", `Automation engine ngừng hoạt động${d.reason === "lwt" ? " (LWT)" : ""}`);
      }
      renderEngine();
    } else if (what === "mode" && kind === "state") {
      state.mode = d.mode;
      renderMode();
    } else if (what === "notify" && kind === "event") {
      const lvl = { critical: "bad", warn: "warn", info: "info", rule: "rule" }[d.level] || "info";
      if (lvl === "bad" && !meta.retain) toast("bad", d.text);    // toast tự thêm vào danh sách
      else addAlert(lvl, d.text || "", d.ts);
      if (lvl === "rule") renderEngine();
    }
  }

  // =========================================================
  //  PHÒNG & THIẾT BỊ
  // =========================================================
  function ensureRoom(room, name) {
    let r = state.rooms.get(room);
    if (!r) {
      const sec = document.createElement("section");
      sec.className = "room";
      sec.dataset.room = room;
      sec.innerHTML = `<div class="room-head"><h2></h2><span class="room-sum"></span></div><div class="grid"></div>`;
      r = { id: room, name: name || cap(room), sec, grid: sec.querySelector(".grid") };
      state.rooms.set(room, r);
      const sorted = [...state.rooms.values()].sort((a, b) =>
        orderOf(ROOM_ORDER, a.id) - orderOf(ROOM_ORDER, b.id) || a.id.localeCompare(b.id));
      const next = sorted[sorted.indexOf(r) + 1];
      el.rooms.insertBefore(sec, next ? next.sec : null);
      el.empty.style.display = "none";
    }
    if (name) r.name = name;
    r.sec.querySelector("h2").textContent = r.name;
    renderTabs();
    return r;
  }

  function renderTabs() {
    const rooms = [...state.rooms.values()].sort((a, b) =>
      orderOf(ROOM_ORDER, a.id) - orderOf(ROOM_ORDER, b.id) || a.id.localeCompare(b.id));
    el.tabs.innerHTML = [{ id: "all", name: "Tất cả" }, ...rooms]
      .map((r) => `<button role="tab" data-room="${esc(r.id)}" class="${state.roomFilter === r.id ? "on" : ""}">${esc(r.name)}</button>`)
      .join("");
    for (const r of state.rooms.values()) r.sec.hidden = state.roomFilter !== "all" && state.roomFilter !== r.id;
  }

  function upsertDevice(room, id) {
    const key = `${room}/${id}`;
    let dev = state.devices.get(key);
    if (dev) return dev;
    dev = {
      key, room, id, name: id, type: null, caps: {}, status: null, reason: null, node: null, sim: false,
      info: {}, state: {}, lastState: 0, history: [], pending: 0, lastCmd: null, el: null,
      color: PALETTE[state.colorIdx++ % PALETTE.length],
    };
    state.devices.set(key, dev);
    ensureRoom(room);
    return dev;
  }

  function removeDevice(key) {
    const dev = state.devices.get(key);
    if (!dev) return;
    if (dev.el) dev.el.remove();
    state.devices.delete(key);
    const r = state.rooms.get(dev.room);
    if (r && ![...state.devices.values()].some((d) => d.room === dev.room)) {
      r.sec.remove(); state.rooms.delete(dev.room); renderTabs();
    }
    if (!state.devices.size) el.empty.style.display = "";
    updateKpis(); scheduleCharts();
  }

  function resetAll() {
    for (const r of state.rooms.values()) r.sec.remove();
    state.devices.clear(); state.rooms.clear();
    state.engine = null; state.mode = null; state.power = []; state.colorIdx = 0; state.roomFilter = "all";
    el.empty.style.display = "";
    el.kClients.textContent = "—";
    el.wcHint.textContent = `${state.prefix}/+/+/+`;
    el.sceneTopic.textContent = `${state.prefix}/_auto/scene/set`;
    el.dashWill.textContent = `${state.prefix}/_dashboard/${state.clientId}/status`;
    renderTabs(); renderEngine(); renderMode(); updateKpis(); scheduleCharts();
  }

  function effStatus(dev) {
    if (dev.status === "offline") return "offline";
    if (dev.node) {
      const n = state.devices.get(`${dev.room}/${dev.node}`);
      if (n && n.status === "offline") return "offline";
    }
    return dev.status === "online" ? "online" : "unknown";
  }

  // ---------------- thẻ thiết bị ----------------
  function bodyHtml(dev) {
    const c = dev.caps || {};
    switch (dev.type) {
      case "light":
        return c.dimmable ? `<label class="rng"><span>Độ sáng</span><input type="range" min="1" max="100" data-set="brightness"><output></output></label>` : "";
      case "fan":
        return (c.speeds || 1) > 1
          ? `<div class="seg sm" data-seg="speed">${Array.from({ length: c.speeds }, (_, i) => `<button data-v="${i + 1}">Số ${i + 1}</button>`).join("")}</div>` : "";
      case "ac":
        return `<div class="ac-row"><button class="btn sm ghost" data-step="-1" aria-label="Giảm nhiệt độ">−</button>
          <span class="ac-target"><b data-f="target">—</b><small>°C</small></span>
          <button class="btn sm ghost" data-step="1" aria-label="Tăng nhiệt độ">+</button>
          <span class="ac-room" data-f="room"></span></div>
          <div class="seg sm" data-seg="mode">${(c.modes || ["cool"]).map((m) => `<button data-v="${m}">${AC_MODE[m] || m}</button>`).join("")}</div>`;
      case "curtain":
        return `<div class="curtain-vis"><i></i><i></i></div>
          <div class="row"><button class="btn sm ghost" data-pos="100">Mở</button><button class="btn sm ghost" data-stop>Dừng</button>
          <button class="btn sm ghost" data-pos="0">Đóng</button><input type="range" min="0" max="100" step="10" data-set="position" aria-label="Vị trí rèm"></div>`;
      case "lock":
        return `<button class="btn lock-btn" data-lock></button><div class="muted-row" data-f="by"></div>`;
      case "plug":
        return `<div class="big"><b data-f="power">—</b></div><div class="muted-row">Điện năng tích lũy <b data-f="energy">—</b> kWh</div>`;
      case "climate":
        return `<div class="vals"><div class="v t"><b data-f="temperature">—</b><small>°C</small></div>
          <div class="v h"><b data-f="humidity">—</b><small>%</small></div></div><canvas class="spark" height="30"></canvas>`;
      case "motion":
      case "door":
        return `<div class="sense"><i class="dot"></i><span data-f="text">—</span></div><div class="muted-row" data-f="last"></div>`;
      case "gas":
        return `<div class="big"><b data-f="ppm">—</b><small>ppm</small></div><div class="meter"><i></i><span class="th"></span></div>`;
      case "node":
        return `<dl class="kv"><dt>IP</dt><dd data-f="ip">—</dd><dt>WiFi</dt><dd data-f="rssi">—</dd>
          <dt>Uptime</dt><dd data-f="uptime">—</dd><dt>Firmware</dt><dd data-f="fw">—</dd></dl>`;
      default:
        return `<pre class="raw"></pre>`;
    }
  }

  function createCard(dev) {
    const art = document.createElement("article");
    art.className = `dev t-${dev.type || "generic"}`;
    art.dataset.type = dev.type || "";
    art.dataset.sim = dev.sim ? "1" : "";
    const acts = [];
    if (dev.sim && TRIGGER_LABEL[dev.type]) acts.push(`<button class="btn sm ghost" data-act="trigger" title="Giả lập sự kiện vật lý">${TRIGGER_LABEL[dev.type]}</button>`);
    if (dev.sim || dev.type === "node") acts.push(`<button class="btn sm danger" data-act="crash" title="Ngắt kết nối đột ngột → broker phát LWT">Mất điện</button>`);
    art.innerHTML = `
      <header class="dev-head">
        <span class="ico-wrap">${svg(dev.type)}</span>
        <div class="dev-title"><b class="dev-name"></b><small class="dev-sub">—</small></div>
        ${SWITCHABLE.has(dev.type) ? '<button class="sw" role="switch" aria-checked="false" aria-label="Bật/tắt"><i></i></button>' : ""}
      </header>
      <div class="dev-body">${bodyHtml(dev)}</div>
      <footer class="dev-foot">
        <span class="badge"></span><span class="meta"></span>
        <span class="acts">${acts.join("")}</span>
      </footer>`;

    art.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b || b.disabled) return;
      const s = dev.state, c = dev.caps || {};
      const seg = b.parentElement.dataset.seg;
      // Gửi trạng thái tuyệt đối {"on": true} thay vì "toggle": gửi lặp lại (QoS 1 có thể trùng) vẫn đúng
      if (b.classList.contains("sw")) command(dev, { on: !s.on });
      else if (seg) command(dev, seg === "speed" ? { on: true, speed: Number(b.dataset.v) } : { [seg]: b.dataset.v });
      else if (b.dataset.step) command(dev, { target: Math.max(c.min || 16, Math.min(c.max || 30, (s.target ?? 26) + Number(b.dataset.step))) });
      else if (b.dataset.pos) command(dev, { position: Number(b.dataset.pos) });
      else if ("stop" in b.dataset) command(dev, { stop: true });
      else if ("lock" in b.dataset) command(dev, { locked: !s.locked });
      else if (b.dataset.act) command(dev, { action: b.dataset.act });
    });
    art.addEventListener("input", (e) => {
      const r = e.target.closest('input[data-set="brightness"]');
      if (r) r.nextElementSibling.textContent = r.value + "%";
    });
    art.addEventListener("change", (e) => {
      const r = e.target.closest("input[data-set]");
      if (r) command(dev, { [r.dataset.set]: Number(r.value) });
    });
    return art;
  }

  function ensureCard(dev) {
    const want = dev.type || "";
    if (dev.el && dev.el.dataset.type === want && dev.el.dataset.sim === (dev.sim ? "1" : "")) return;
    const old = dev.el;
    dev.el = createCard(dev);
    if (old) { old.replaceWith(dev.el); return; }
    const r = ensureRoom(dev.room);
    const peers = [...state.devices.values()].filter((d) => d.room === dev.room && d.el && d !== dev);
    const rank = (d) => orderOf(TYPE_ORDER, d.type) * 1000;
    const next = peers.filter((d) => rank(d) > rank(dev) || (rank(d) === rank(dev) && d.id > dev.id))
      .sort((a, b) => rank(a) - rank(b) || a.id.localeCompare(b.id))[0];
    r.grid.insertBefore(dev.el, next ? next.el : null);
  }

  function subText(dev) {
    const s = dev.state, c = dev.caps || {};
    switch (dev.type) {
      case "light": return s.on ? `Bật${c.dimmable ? ` · ${s.brightness}%` : ""}` : "Tắt";
      case "fan": return s.on ? `Bật${(c.speeds || 1) > 1 ? ` · số ${s.speed}` : ""}` : "Tắt";
      case "ac": return s.on ? `${AC_MODE[s.mode] || s.mode} · ${s.target}°C` : "Tắt";
      case "curtain":
        if (s.moving) return `Đang chuyển động… ${s.position}%`;
        return s.position === 0 ? "Đóng" : s.position === 100 ? "Mở hoàn toàn" : `Mở ${s.position}%`;
      case "lock": return s.locked ? "Đã khóa" : "Đang mở khóa";
      case "plug": return s.on ? "Đang cấp điện" : "Tắt";
      case "climate": return s.battery != null ? `Pin ${Math.round(s.battery)}%` : "";
      case "motion": return s.motion ? "Có chuyển động" : "Yên tĩnh";
      case "door": return s.open ? "Đang mở" : "Đã đóng";
      case "gas": return s.alarm ? "NGUY HIỂM" : "An toàn";
      case "node": {
        const kids = [...state.devices.values()].filter((d) => d.node === dev.id && d.room === dev.room).length;
        return `Bo mạch · ${kids} thiết bị con`;
      }
      default: return dev.type || "chưa rõ loại";
    }
  }

  function renderDevice(dev, flash = false) {
    ensureCard(dev);
    const n = dev.el, s = dev.state || {}, c = dev.caps || {};
    const f = (k) => n.querySelector(`[data-f="${k}"]`);
    const st = effStatus(dev);

    if (dev.pending && Date.now() - dev.pending > PENDING_MS) {
      dev.pending = 0;
      addAlert("warn", `${dev.name} (${dev.room}) không phản hồi lệnh — thiết bị offline?`);
    }

    n.querySelector(".dev-name").textContent = dev.name;
    n.querySelector(".dev-sub").textContent = subText(dev);
    const badge = n.querySelector(".badge");
    badge.className = "badge " + st;
    badge.textContent = st === "offline"
      ? (dev.reason === "lwt" ? "Offline · LWT" : dev.status === "offline" ? "Offline" : "Bo mạch offline")
      : st === "online" ? "Online" : "Chưa rõ";

    const active = { light: s.on, fan: s.on, ac: s.on, plug: s.on, curtain: s.position > 0,
      lock: s.locked === false, motion: s.motion, door: s.open, gas: s.alarm }[dev.type];
    n.classList.toggle("on", !!active && st !== "offline");
    n.classList.toggle("alarm", dev.type === "gas" && !!s.alarm && st !== "offline");
    n.classList.toggle("offline", st === "offline");
    n.classList.toggle("pending", !!dev.pending);
    $$("button, input", n).forEach((b) => (b.disabled = st === "offline"));
    const sw = n.querySelector(".sw");
    if (sw) sw.setAttribute("aria-checked", String(!!s.on));

    const meta = [];
    if (s.power != null && dev.type !== "plug" && s.power > 0) meta.push(fmtW(s.power));
    if (dev.lastCmd && Date.now() - dev.lastCmd.ts < 60000) meta.push(`lệnh: ${dev.lastCmd.from}`);
    else if (dev.fromRetained) meta.push("retained");
    else if (dev.lastState) meta.push(ago(dev.lastState));
    n.querySelector(".meta").textContent = meta.join(" · ");

    const range = (k, v) => { const r = n.querySelector(`input[data-set="${k}"]`); if (r && document.activeElement !== r && v != null) r.value = v; return r; };
    const seg = (k, v) => $$(`[data-seg="${k}"] button`, n).forEach((b) => b.classList.toggle("on", b.dataset.v === String(v)));

    switch (dev.type) {
      case "light": {
        const r = range("brightness", s.brightness);
        if (r) r.nextElementSibling.textContent = r.value + "%";
        n.style.setProperty("--glow", s.on ? (s.brightness ?? 100) / 100 : 0);
        break;
      }
      case "fan":
        seg("speed", s.speed);
        n.style.setProperty("--spin", s.on ? `${1.4 - (s.speed || 1) * 0.35}s` : "0s");
        break;
      case "ac": {
        f("target").textContent = s.target ?? "—";
        seg("mode", s.on ? s.mode : "");
        const cl = [...state.devices.values()].find((d) => d.room === dev.room && d.type === "climate");
        f("room").textContent = cl && cl.state.temperature != null ? `Phòng ${Number(cl.state.temperature).toFixed(1)}°C` : "";
        break;
      }
      case "curtain":
        range("position", s.position);
        n.style.setProperty("--open", (s.position ?? 0) / 100);
        break;
      case "lock": {
        const b = n.querySelector(".lock-btn");
        b.innerHTML = `${svg(s.locked ? "lock" : "unlock")}<span>${s.locked ? "Mở khóa" : "Khóa cửa"}</span>`;
        n.querySelector(".ico-wrap").innerHTML = svg(s.locked === false ? "unlock" : "lock");
        f("by").textContent = s.by ? `Thao tác cuối: ${s.by}` : "";
        break;
      }
      case "plug":
        f("power").textContent = s.power != null ? fmtW(s.power) : "—";
        f("energy").textContent = s.energy != null ? Number(s.energy).toFixed(3) : "—";
        break;
      case "climate":
        f("temperature").textContent = s.temperature != null ? Number(s.temperature).toFixed(1) : "—";
        f("humidity").textContent = s.humidity != null ? Math.round(s.humidity) : "—";
        drawSpark(dev);
        break;
      case "motion":
        f("text").textContent = s.motion ? "Phát hiện chuyển động" : "Không có chuyển động";
        f("last").textContent = dev.lastMotion ? `Lần cuối: ${ago(dev.lastMotion)}` : "";
        break;
      case "door":
        f("text").textContent = s.open ? "Cửa đang mở" : "Cửa đóng";
        f("last").textContent = "";
        break;
      case "gas": {
        const th = c.threshold || 1000;
        f("ppm").textContent = s.ppm ?? "—";
        n.querySelector(".meter i").style.width = `${Math.min(100, ((s.ppm || 0) / (th * 2)) * 100)}%`;
        n.querySelector(".meter .th").title = `Ngưỡng ${th} ppm`;
        break;
      }
      case "node":
        f("ip").textContent = dev.info.ip || "—";
        f("rssi").textContent = s.rssi != null ? `${s.rssi} dBm` : "—";
        f("uptime").textContent = s.uptime != null ? fmtUptime(Math.round(s.uptime)) : "—";
        f("fw").textContent = dev.info.fw || "—";
        break;
      default:
        n.querySelector(".raw").textContent = JSON.stringify(s, null, 1);
    }

    if (flash) { n.classList.remove("flash"); void n.offsetWidth; n.classList.add("flash"); }
    renderRoomSummary(dev.room);
  }

  function renderRoomSummary(room) {
    const r = state.rooms.get(room);
    if (!r) return;
    const devs = [...state.devices.values()].filter((d) => d.room === room);
    const cl = devs.find((d) => d.type === "climate" && d.state.temperature != null);
    const on = devs.filter((d) => SWITCHABLE.has(d.type) && d.state.on && effStatus(d) !== "offline").length;
    const parts = [];
    if (cl) parts.push(`${Number(cl.state.temperature).toFixed(1)}°C · ${Math.round(cl.state.humidity)}%`);
    parts.push(`${devs.length} thiết bị${on ? `, ${on} đang bật` : ""}`);
    r.sec.querySelector(".room-sum").textContent = parts.join(" · ");
  }

  function drawSpark(dev) {
    const c = dev.el.querySelector(".spark");
    if (!c) return;
    const w = c.clientWidth || 240, h = 30, dpr = window.devicePixelRatio || 1;
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

  // =========================================================
  //  AUTOMATION: chế độ, kịch bản, luật
  // =========================================================
  function engineOnline() { return !!state.engine && state.engine.state === "online"; }

  function renderEngine() {
    const e = state.engine, on = engineOnline();
    setPill(el.enginePill, on ? "on" : e ? "off" : "", on ? "Automation online" : e ? "Automation offline" : "Automation: chưa thấy");

    const scenes = (e && e.scenes) || [];
    el.scenes.innerHTML = scenes.length
      ? scenes.map((s) => `<button class="scene" data-scene="${esc(s.id)}" ${on ? "" : "disabled"}><span>${esc(s.icon || "▶")}</span>${esc(s.name)}</button>`).join("")
      : `<span class="muted">Chạy <code>python automation/automation.py</code> để có kịch bản.</span>`;

    const rules = (e && e.rules) || [];
    el.rules.innerHTML = rules.length
      ? rules.map((r) => `<li class="${r.enabled ? "" : "disabled"}">
          <button class="sw sm" role="switch" aria-checked="${r.enabled}" data-rule="${esc(r.id)}" aria-label="Bật/tắt luật" ${on ? "" : "disabled"}><i></i></button>
          <div><b>${esc(r.name)}</b><small>${esc(r.description || "")}${r.last_fired ? ` · chạy <span data-ago="${r.last_fired}">${ago(r.last_fired)}</span>` : ""}</small></div>
        </li>`).join("")
      : `<li class="muted">Automation engine chưa chạy.</li>`;
    renderMode();
  }

  function renderMode() {
    const on = engineOnline();
    $$("button", el.modeSeg).forEach((b) => {
      b.classList.toggle("on", b.dataset.mode === state.mode);
      b.disabled = !on;
    });
    document.body.dataset.mode = state.mode || "";
  }

  // =========================================================
  //  KPI, CẢNH BÁO, LOG
  // =========================================================
  function updateKpis() {
    const all = [...state.devices.values()];
    const live = all.filter((d) => effStatus(d) !== "offline");
    const climates = live.filter((d) => d.type === "climate" && d.state.temperature != null);
    const avg = (k) => climates.reduce((a, d) => a + Number(d.state[k]), 0) / climates.length;
    el.kTemp.textContent = climates.length ? `${avg("temperature").toFixed(1)}°C` : "—";
    el.kHum.textContent = climates.length ? `${Math.round(avg("humidity"))}%` : "—";
    el.kPower.textContent = all.length ? fmtW(totalPower()) : "—";
    const lights = all.filter((d) => d.type === "light");
    el.kLights.textContent = lights.length ? `${lights.filter((d) => d.state.on && effStatus(d) !== "offline").length}/${lights.length}` : "—";
    const lock = all.find((d) => d.type === "lock"), door = all.find((d) => d.type === "door");
    el.kDoor.textContent = !lock && !door ? "—"
      : door && door.state.open ? "Đang mở" : lock && lock.state.locked === false ? "Chưa khóa" : "Đã khóa";
    el.kDoor.className = "k-val " + (door && door.state.open ? "bad" : lock && lock.state.locked === false ? "warn" : "");
    el.kOnline.textContent = `${all.filter((d) => effStatus(d) === "online").length}/${all.length}`;
    const kwh = all.reduce((a, d) => a + (Number(d.state.energy) || 0), 0);
    el.energyHint.textContent = kwh ? `ổ cắm đã dùng ${kwh.toFixed(2)} kWh` : "";
  }

  function totalPower() {
    let w = 0;
    for (const d of state.devices.values()) if (effStatus(d) !== "offline") w += Number(d.state.power) || 0;
    return w;
  }

  function addAlert(level, text, ts = Date.now()) {
    const first = el.alerts.querySelector(".muted");
    if (first) first.remove();
    const li = document.createElement("li");
    li.className = level;
    li.innerHTML = `<time>${hms(ts)}</time>${esc(text)}`;
    el.alerts.prepend(li);
    while (el.alerts.children.length > 80) el.alerts.lastChild.remove();
  }

  function toast(level, text) {
    addAlert(level, text);
    const t = document.createElement("div");
    t.className = "toast " + level;
    t.textContent = text;
    el.toasts.append(t);
    setTimeout(() => t.classList.add("out"), 6000);
    setTimeout(() => t.remove(), 6600);
  }

  function logMessage(topic, text, meta) {
    if (el.logPause.checked) return;
    const kind = topic.startsWith("$SYS") ? "sys" : topic.split("/")[3] || "";
    if (el.logHide.checked && (kind === "state" || kind === "sys")) return;
    const flt = el.logFilter.value.trim();
    if (flt && !topic.includes(flt)) return;
    const tr = document.createElement("tr");
    tr.className = kind + (text.includes('"lwt"') ? " lwt" : "");
    tr.innerHTML =
      `<td>${hms(Date.now())}</td><td class="topic">${esc(topic)}</td><td>${meta.qos ?? "-"}</td>` +
      `<td>${meta.retain ? '<span class="yes">✓</span>' : ""}</td><td class="payload" title="${esc(text)}">${esc(text || "(rỗng)")}</td>`;
    el.logBody.prepend(tr);
    while (el.logBody.children.length > 250) el.logBody.lastChild.remove();
  }

  // =========================================================
  //  BIỂU ĐỒ
  // =========================================================
  Chart.defaults.font.family = '"Be Vietnam Pro", system-ui, sans-serif';
  Chart.defaults.color = cssVar("--muted");
  Chart.defaults.borderColor = cssVar("--line");

  const timeAxis = () => ({
    type: "linear",
    ticks: { maxTicksLimit: 6, callback: (v) => hms(v).slice(0, 5) },
    grid: { display: false },
  });
  const baseOpts = (yTitle) => ({
    animation: false, responsive: true, maintainAspectRatio: false, parsing: false,
    interaction: { mode: "nearest", axis: "x", intersect: false },
    scales: { x: timeAxis(), y: { title: { display: true, text: yTitle }, grace: "10%" } },
    plugins: {
      legend: { labels: { usePointStyle: true, boxWidth: 8 } },
      tooltip: { callbacks: { title: (it) => it.length ? hms(it[0].parsed.x) : "" } },
    },
  });

  const climateChart = new Chart($("#climateChart"), { type: "line", data: { datasets: [] }, options: baseOpts("°C") });
  const powerChart = new Chart($("#powerChart"), {
    type: "line",
    data: { datasets: [{ label: "Tổng công suất (W)", data: [], borderColor: cssVar("--warn"),
      backgroundColor: cssVar("--warn") + "26", fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2, stepped: false }] },
    options: { ...baseOpts("W"), plugins: { ...baseOpts("W").plugins, legend: { display: false } } },
  });
  powerChart.options.scales.y.beginAtZero = true;

  let chartPending = false;
  function scheduleCharts() {
    if (chartPending) return;
    chartPending = true;
    requestAnimationFrame(() => { chartPending = false; drawCharts(); });
  }

  function drawCharts() {
    const now = Date.now(), min = now - state.rangeSec * 1000;
    const climates = [...state.devices.values()].filter((d) => d.type === "climate");
    climateChart.data.datasets = climates.map((d) => ({
      label: state.rooms.get(d.room)?.name || d.room,
      data: d.history.filter((p) => p.x >= min - 5000).map((p) => ({ x: p.x, y: p.t })),
      borderColor: d.color, backgroundColor: d.color, tension: 0.35, pointRadius: 0, borderWidth: 1.8,
    }));
    climateChart.options.scales.x.min = min; climateChart.options.scales.x.max = now;
    climateChart.update("none");

    powerChart.data.datasets[0].data = state.power.filter((p) => p.x >= min - 5000);
    powerChart.options.scales.x.min = min; powerChart.options.scales.x.max = now;
    powerChart.update("none");
  }

  // Mỗi giây: trượt trục thời gian, cập nhật "x giây trước", lấy mẫu công suất, kiểm tra lệnh chờ
  let tickN = 0;
  setInterval(() => {
    const now = Date.now();
    state.rxTimes = state.rxTimes.filter((t) => now - t < 60000);
    el.kRate.textContent = state.rxTimes.length;
    if (state.devices.size && (state.client?.connected || state.demo) && tickN++ % 2 === 0) {
      state.power.push({ x: now, y: Math.round(totalPower()) });
      while (state.power.length && state.power[0].x < now - HISTORY_MS) state.power.shift();
    }
    for (const d of state.devices.values()) renderDevice(d);
    $$("[data-ago]").forEach((s) => (s.textContent = ago(Number(s.dataset.ago))));
    updateKpis();
    scheduleCharts();
  }, 1000);

  // =========================================================
  //  SỰ KIỆN UI
  // =========================================================
  el.form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (state.client) { disconnectAll(); return; }
    if (typeof mqtt === "undefined") { setPill(el.pill, "off", "Không tải được MQTT.js (cần Internet cho CDN)"); return; }
    connect();
  });

  function startDemo() {
    disconnectAll();
    state.prefix = el.prefix.value.trim() || "home";
    resetAll();
    state.demo = new window.SmartHomeDemo(state.prefix, handleMessage);
    state.demo.start();
    setPill(el.pill, "demo", "Demo (giả lập trong trình duyệt)");
    el.btnDemo.textContent = "Dừng demo";
  }
  el.btnDemo.addEventListener("click", () => (state.demo ? disconnectAll() : startDemo()));

  el.modeSeg.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-mode]");
    if (b && !b.disabled) send(`${state.prefix}/_auto/mode/set`, { mode: b.dataset.mode });
  });
  el.scenes.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-scene]");
    if (b && !b.disabled) send(`${state.prefix}/_auto/scene/set`, { scene: b.dataset.scene });
  });
  el.rules.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-rule]");
    if (b && !b.disabled) send(`${state.prefix}/_auto/rule/set`, { id: b.dataset.rule, enabled: b.getAttribute("aria-checked") !== "true" });
  });
  el.tabs.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-room]");
    if (!b) return;
    state.roomFilter = b.dataset.room;
    renderTabs();
  });
  el.rangeSeg.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    $$("button", el.rangeSeg).forEach((x) => x.classList.toggle("on", x === b));
    state.rangeSec = Number(b.dataset.range);
    scheduleCharts();
  });
  el.logClear.addEventListener("click", () => (el.logBody.innerHTML = ""));
  el.alertClear.addEventListener("click", () => (el.alerts.innerHTML = '<li class="muted">Chưa có thông báo.</li>'));

  resetAll();
  // Bản công khai trên GitHub Pages không có broker riêng -> tự chạy demo (trừ khi truyền ?broker=...)
  const PUBLIC_DEMO = location.hostname.endsWith("github.io") && !qs.get("broker");
  if (qs.get("demo") === "1" || PUBLIC_DEMO) startDemo();
  else if (typeof mqtt !== "undefined") connect();
})();
