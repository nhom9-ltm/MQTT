/* =========================================================
 *  Chế độ Demo — giả lập broker + toàn bộ thiết bị + automation engine
 *  ngay trong trình duyệt (dự phòng khi thuyết trình mà mạng/broker trục trặc).
 *
 *  Đây là bản rút gọn của BE/mock/ (house.py, devices.py) và BE/service/automation_service.py:
 *  cùng topic, cùng payload, cùng định dạng luật — dashboard không phân biệt được.
 * ========================================================= */
(() => {
  "use strict";

  const HOUSE = [
    ["living", "Phòng khách", [
      ["climate", "climate", "Nhiệt độ & độ ẩm", { base_t: 28, base_h: 62 }],
      ["light", "light", "Đèn trần", { watt: 18, dimmable: true }],
      ["fan", "fan", "Quạt đứng", {}],
      ["ac", "ac", "Điều hòa", {}],
      ["curtain", "curtain", "Rèm cửa sổ", {}],
      ["plug", "tv-plug", "Ổ cắm TV", { watt: 95, on: true }],
      ["motion", "motion", "Cảm biến chuyển động", { rate: 1 / 90 }],
    ]],
    ["bedroom", "Phòng ngủ", [
      ["climate", "climate", "Nhiệt độ & độ ẩm", { base_t: 27, base_h: 60 }],
      ["light", "light", "Đèn ngủ", { watt: 12, dimmable: true }],
      ["ac", "ac", "Điều hòa", {}],
      ["curtain", "curtain", "Rèm cửa sổ", {}],
    ]],
    ["kitchen", "Nhà bếp", [
      ["climate", "climate", "Nhiệt độ & độ ẩm", { base_t: 30, base_h: 70 }],
      ["light", "light", "Đèn bếp", { watt: 15 }],
      ["fan", "hood-fan", "Quạt hút mùi", {}],
      ["plug", "stove-plug", "Bếp điện", { watt: 1200, cycle: true }],
      ["gas", "gas", "Cảm biến khí gas", {}],
    ]],
    ["entrance", "Lối vào", [
      ["lock", "lock", "Khóa cửa chính", {}],
      ["door", "door", "Cảm biến cửa chính", {}],
      ["motion", "motion", "Cảm biến chuyển động", { rate: 1 / 150 }],
      ["light", "porch-light", "Đèn hiên", { watt: 10 }],
    ]],
  ];

  // Bản sao (rút gọn) của BE/config/rules.json và scenes.json
  const RULES = [
    { id: "living_hot", name: "Phòng khách nóng → bật điều hòa", description: "Nhiệt độ > 31°C khi có người ở nhà và điều hòa đang tắt",
      trigger: { device: "living/climate", field: "temperature", op: ">", value: 31 },
      conditions: [{ mode: ["home"] }, { device: "living/ac", field: "on", op: "==", value: false }],
      actions: [{ device: "living/ac", set: { on: true, mode: "cool", target: 26 } },
        { notify: "Phòng khách {temperature}°C — đã bật điều hòa 26°C", level: "info" }], cooldown: 120 },
    { id: "gas_leak", name: "Rò rỉ gas → ngắt bếp, bật quạt hút", description: "Cảm biến gas nhà bếp báo động",
      trigger: { device: "kitchen/gas", field: "alarm", op: "==", value: true },
      actions: [{ device: "kitchen/stove-plug", set: { on: false } }, { device: "kitchen/hood-fan", set: { on: true, speed: 3 } },
        { notify: "Phát hiện khí gas {ppm} ppm ở nhà bếp! Đã ngắt bếp điện và bật quạt hút", level: "critical" }] },
    { id: "porch_light", name: "Có người ở cửa buổi tối → bật đèn hiên 2 phút", description: "Cảm biến chuyển động lối vào, từ 17:30 đến 06:00",
      trigger: { device: "entrance/motion", field: "motion", op: "==", value: true },
      conditions: [{ time: { after: "17:30", before: "06:00" } }],
      actions: [{ device: "entrance/porch-light", set: { on: true } }, { delay: 120 }, { device: "entrance/porch-light", set: { on: false } }] },
    { id: "intrusion_door", name: "Cửa mở khi vắng nhà / ban đêm → báo động", description: "Bật toàn bộ đèn và gửi cảnh báo",
      trigger: { device: "entrance/door", field: "open", op: "==", value: true }, conditions: [{ mode: ["away", "night"] }],
      actions: [{ notify: "Cửa chính bị mở khi đang ở chế độ an ninh!", level: "critical" }, { type: "light", set: { on: true, brightness: 100 } }] },
    { id: "intrusion_motion", name: "Chuyển động khi vắng nhà → báo động", description: "Cảm biến chuyển động phòng khách khi không có ai ở nhà",
      trigger: { device: "living/motion", field: "motion", op: "==", value: true }, conditions: [{ mode: ["away"] }],
      actions: [{ notify: "Phát hiện chuyển động trong phòng khách khi vắng nhà!", level: "critical" },
        { device: "living/light", set: { on: true, brightness: 100 } }], cooldown: 60 },
    { id: "living_idle", name: "Không ai trong phòng khách 2 phút → tắt đèn, quạt", description: "Tiết kiệm điện khi không có chuyển động",
      trigger: { device: "living/motion", field: "motion", op: "==", value: false, for: 120 },
      conditions: [{ device: "living/light", field: "on", op: "==", value: true }],
      actions: [{ device: "living/light", set: { on: false } }, { device: "living/fan", set: { on: false } },
        { notify: "Phòng khách không có người 2 phút — đã tắt đèn và quạt", level: "info" }] },
    { id: "night_lock", name: "23:00 tự khóa cửa nếu quên", description: "Kiểm tra khóa cửa chính lúc 23:00",
      trigger: { at: "23:00" }, conditions: [{ device: "entrance/lock", field: "locked", op: "==", value: false }],
      actions: [{ device: "entrance/lock", set: { locked: true } }, { notify: "23:00 — cửa chính chưa khóa, đã tự động khóa", level: "warn" }] },
  ];
  const SCENES = [
    { id: "home", name: "Về nhà", icon: "🏠", actions: [{ mode: "home" }, { device: "entrance/lock", set: { locked: false } },
      { device: "living/light", set: { on: true, brightness: 80 } }, { device: "living/curtain", set: { position: 100 } },
      { device: "living/ac", set: { on: true, mode: "cool", target: 26 } }] },
    { id: "away", name: "Ra khỏi nhà", icon: "🚪", actions: [{ type: "light", set: { on: false } }, { type: "fan", set: { on: false } },
      { type: "ac", set: { on: false } }, { device: "living/tv-plug", set: { on: false } }, { type: "curtain", set: { position: 0 } },
      { type: "lock", set: { locked: true } }, { delay: 3 }, { mode: "away" }] },
    { id: "sleep", name: "Đi ngủ", icon: "🌙", actions: [{ mode: "night" }, { type: "light", except: ["bedroom/light"], set: { on: false } },
      { device: "bedroom/light", set: { on: true, brightness: 10 } }, { device: "bedroom/ac", set: { on: true, mode: "cool", target: 27 } },
      { device: "living/ac", set: { on: false } }, { device: "living/tv-plug", set: { on: false } },
      { type: "curtain", set: { position: 0 } }, { type: "lock", set: { locked: true } }] },
    { id: "morning", name: "Buổi sáng", icon: "☀️", actions: [{ mode: "home" }, { type: "curtain", set: { position: 100 } },
      { device: "bedroom/light", set: { on: true, brightness: 80 } }, { device: "bedroom/ac", set: { on: false } }] },
    { id: "movie", name: "Xem phim", icon: "🎬", actions: [{ device: "living/light", set: { on: true, brightness: 15 } },
      { device: "living/curtain", set: { position: 0 } }, { device: "living/tv-plug", set: { on: true } },
      { device: "living/ac", set: { on: true, mode: "cool", target: 25 } }] },
  ];
  const MODES = { home: "Ở nhà", away: "Vắng nhà", night: "Ban đêm" };
  const OPS = { "==": (a, b) => a === b, "!=": (a, b) => a !== b, ">": (a, b) => a > b, ">=": (a, b) => a >= b, "<": (a, b) => a < b, "<=": (a, b) => a <= b };

  const rnd = (a, b) => a + Math.random() * (b - a);
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const hm = () => { const d = new Date(); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
  const daily = (now) => { const d = new Date(now); return Math.sin((d.getHours() + d.getMinutes() / 60 - 9) / 24 * 2 * Math.PI); };
  const isDay = (now) => { const h = new Date(now).getHours(); return h >= 6 && h < 18; };
  const fill = (text, ctx) => text.replace(/\{(\w+)\}/g, (m, k) => (ctx[k] ?? m));
  const FAN_W = [0, 18, 28, 40];

  // ---------------- thiết bị: state ban đầu, caps, lệnh, mô phỏng ----------------
  const T = {
    climate: {
      report: true,
      init: (d) => { const k = daily(Date.now()); d.t = d.o.base_t + 2.5 * k; d.h = d.o.base_h - 6 * k; d.bat = rnd(80, 100); return snapClimate(d); },
      caps: () => ({ temperature: "°C", humidity: "%" }),
      trigger: (d) => { d.t += 6; d.state = snapClimate(d); },
      update(d, dt, now, sim) {
        let gt = d.o.base_t + 2.5 * daily(now), gh = d.o.base_h - 6 * daily(now), kt = 0.004, kh = 0.004;
        const fan = sim.find(d.room, "fan"), cur = sim.find(d.room, "curtain"), ac = sim.find(d.room, "ac");
        if (fan && fan.state.on) gt -= 0.4 * fan.state.speed;
        if (cur && isDay(now) && cur.state.position > 50) gt += 1;
        if (ac && ac.state.on && ac.state.mode === "cool") { gt = ac.state.target; kt = 0.02; gh -= 8; }
        if (ac && ac.state.on && ac.state.mode === "dry") { gt -= 1; gh = 50; kh = 0.02; }
        d.t += (gt - d.t) * kt * dt + rnd(-0.05, 0.05);
        d.h += (gh - d.h) * kh * dt + rnd(-0.15, 0.15);
        d.bat = Math.max(0, d.bat - 0.0005 * dt);
        d.state = snapClimate(d);
      },
    },
    light: {
      init: () => ({ on: false, brightness: 100, power: 0 }),
      caps: (d) => ({ dimmable: !!d.o.dimmable, watt: d.o.watt }),
      apply(d, c) {
        applyOn(d, c);
        if ("brightness" in c && d.o.dimmable) { d.state.brightness = Math.round(clamp(c.brightness, 1, 100)); if (!("on" in c)) d.state.on = true; }
        d.state.power = d.state.on ? +(d.o.watt * d.state.brightness / 100).toFixed(1) : 0;
      },
    },
    fan: {
      init: () => ({ on: false, speed: 2, power: 0 }),
      caps: () => ({ speeds: 3 }),
      apply(d, c) {
        applyOn(d, c);
        if ("speed" in c) d.state.speed = clamp(Math.round(c.speed), 1, 3);
        d.state.power = d.state.on ? FAN_W[d.state.speed] : 0;
      },
    },
    ac: {
      report: true,
      init: () => ({ on: false, mode: "cool", target: 26, power: 0 }),
      caps: () => ({ modes: ["cool", "dry", "fan"], min: 16, max: 30 }),
      apply(d, c, sim) {
        applyOn(d, c);
        if (["cool", "dry", "fan"].includes(c.mode)) d.state.mode = c.mode;
        if ("target" in c) d.state.target = clamp(Math.round(c.target), 16, 30);
        T.ac.update(d, 0, Date.now(), sim);
      },
      update(d, dt, now, sim) {
        const s = d.state, was = s.power;
        if (!s.on) s.power = 0;
        else if (s.mode === "fan") s.power = 45;
        else { const cl = sim.find(d.room, "climate"); s.power = Math.round(320 + clamp(cl ? cl.t - s.target : 2, 0, 4) * 220 + rnd(-15, 15)); }
        return was === 0 && s.power > 0;
      },
    },
    curtain: {
      init: (d) => { d.target = 0; return { position: 0, moving: false }; },
      caps: () => ({ position: true }),
      apply(d, c) {
        if ("position" in c) d.target = clamp(Math.round(c.position), 0, 100);
        if ("open" in c) d.target = c.open ? 100 : 0;
        if (c.toggle) d.target = d.state.position >= 50 ? 0 : 100;
        if (c.stop) d.target = d.state.position;
        d.state.moving = d.target !== d.state.position;
      },
      update(d, dt) {
        const s = d.state;
        if (d.target === s.position) return false;
        const diff = d.target - s.position, step = 10 * dt;
        s.position = Math.round(Math.abs(diff) <= step ? d.target : s.position + Math.sign(diff) * step);
        s.moving = s.position !== d.target;
        return true;
      },
    },
    lock: {
      init: () => ({ locked: true, battery: Math.round(rnd(70, 100)), by: null }),
      apply(d, c) {
        if (c.toggle) d.state.locked = !d.state.locked;
        if ("locked" in c) d.state.locked = !!c.locked;
        d.state.by = c.from || null;
      },
    },
    plug: {
      report: true,
      init: (d) => { d.heat = true; d.heatNext = 0; return { on: !!d.o.on, power: 0, energy: +rnd(1, 40).toFixed(3), voltage: 220 }; },
      caps: (d) => ({ watt: d.o.watt, metering: true }),
      apply(d, c, sim) { applyOn(d, c); T.plug.update(d, 0, Date.now(), sim); },
      update(d, dt, now) {
        const s = d.state;
        let p = 0;
        if (s.on && d.o.cycle) {
          if (now >= d.heatNext) { d.heat = !d.heat; d.heatNext = now + rnd(8000, 20000); }
          p = d.heat ? d.o.watt * rnd(0.95, 1.02) : 2;
        } else if (s.on) p = d.o.watt * rnd(0.9, 1.1);
        s.power = +p.toFixed(1);
        s.energy = +(s.energy + p * dt / 3600000).toFixed(4);
        s.voltage = +rnd(218, 226).toFixed(1);
      },
    },
    motion: {
      init: (d) => { d.last = 0; return { motion: false, last_motion: null }; },
      trigger: (d) => { d.last = Date.now(); d.state.motion = true; d.state.last_motion = d.last; },
      update(d, dt, now) {
        if (Math.random() < d.o.rate * dt) { const was = d.state.motion; T.motion.trigger(d); return !was; }
        if (d.state.motion && now - d.last > 15000) { d.state.motion = false; return true; }
        return false;
      },
    },
    door: {
      init: (d) => { d.closeAt = 0; return { open: false }; },
      trigger: (d) => { d.state.open = true; d.closeAt = Date.now() + 8000; },
      update(d, dt, now) {
        if (d.state.open && d.closeAt && now >= d.closeAt) { d.state.open = false; d.closeAt = 0; return true; }
        return false;
      },
    },
    gas: {
      report: true,
      init: (d) => { d.leakUntil = 0; return { ppm: 180, alarm: false }; },
      caps: () => ({ threshold: 1000 }),
      trigger: (d) => { d.leakUntil = Date.now() + 40000; },
      update(d, dt, now) {
        const goal = now < d.leakUntil ? 2200 : 180;
        d.state.ppm = Math.max(0, Math.round(d.state.ppm + (goal - d.state.ppm) * 0.15 * dt + rnd(-10, 10)));
        const alarm = d.state.ppm > 1000, changed = alarm !== d.state.alarm;
        d.state.alarm = alarm;
        return changed;
      },
    },
  };
  function snapClimate(d) { return { temperature: +d.t.toFixed(2), humidity: +clamp(d.h, 0, 100).toFixed(1), battery: +d.bat.toFixed(1) }; }
  function applyOn(d, c) { if (c.toggle) d.state.on = !d.state.on; if ("on" in c) d.state.on = !!c.on; }

  // =========================================================
  class SmartHomeDemo {
    constructor(prefix, emit) {
      this.p = prefix;
      this.emit = emit;            // giống broker giao message cho subscriber (dashboard)
      this.timers = [];
      this.devices = [];
      for (const [room, roomName, items] of HOUSE) {
        for (const [type, id, name, o] of items) {
          const d = { room, roomName, type, id, name, o, key: `${room}/${id}`, online: true, lastReport: 0, deadUntil: 0 };
          d.state = T[type].init(d);
          if (type === "light" || type === "fan") T[type].apply(d, {}, this);
          this.devices.push(d);
        }
      }
      this.mode = "home";
      this.rules = RULES.map((r) => ({ ...r, enabled: true }));
      this.rt = Object.fromEntries(RULES.map((r) => [r.id, { since: null, fired: false, last: 0, lastMs: null }]));
      this.msgs = 24817;
      this.up = 5 * 3600 + 1234;
    }

    find(room, type) { return this.devices.find((d) => d.room === room && d.type === type); }
    get(key) { return this.devices.find((d) => d.key === key); }
    topic(d, kind) { return `${this.p}/${d.room}/${d.id}/${kind}`; }

    // ---------------- "broker" ----------------
    deliver(topic, obj, retain = false, silent = false) {
      this.msgs++;
      this.emit(topic, typeof obj === "string" ? obj : JSON.stringify(obj), { qos: 1, retain, silent });
    }
    publish(topic, body) {                       // dashboard publish -> broker -> các subscriber
      this.deliver(topic, body);
      let data = {};
      try { data = JSON.parse(body); } catch { return; }
      const [, room, id, kind] = topic.split("/");
      if (kind !== "set") return;
      setTimeout(() => (room === "_auto" ? this.control(id, data) : this.command(`${room}/${id}`, data)), 120);
    }

    // ---------------- thiết bị ----------------
    status(d, st, reason, retain = false) {
      const body = st === "offline" && reason === "lwt" ? { state: "offline", reason: "lwt" }
        : { state: st, type: d.type, name: d.name, room_name: d.roomName, caps: T[d.type].caps ? T[d.type].caps(d) : {},
          sim: true, fw: "demo-2.0", ip: "demo", ts: Date.now(), ...(reason ? { reason } : {}) };
      this.deliver(this.topic(d, "status"), body, retain);
    }
    report(d, retain = false) {
      d.lastReport = Date.now();
      this.deliver(this.topic(d, "state"), { ...d.state, ts: Date.now() }, retain);
      this.evaluate();
    }
    command(key, c) {
      const d = this.get(key);
      if (!d || !d.online) return;               // thiết bị offline: lệnh QoS 1 tới client clean session bị mất
      if (c.action === "crash") return this.crash(d);
      if (c.action === "trigger") { if (T[d.type].trigger) T[d.type].trigger(d); }
      else if (T[d.type].apply) T[d.type].apply(d, c, this);
      this.report(d);
    }
    crash(d) {
      d.online = false;
      d.deadUntil = Date.now() + 20000;
      // broker chỉ phát hiện client chết sau ~1.5 × keep-alive (10s) rồi mới publish LWT
      this.timers.push(setTimeout(() => this.status(d, "offline", "lwt"), 6000));
    }

    tick(dt) {
      const now = Date.now();
      for (const d of this.devices) {
        if (!d.online) {
          if (now >= d.deadUntil) { d.online = true; this.status(d, "online"); this.report(d); }
          continue;
        }
        const t = T[d.type];
        const changed = t.update ? t.update(d, dt, now, this) : false;
        if (changed || (t.report && now - d.lastReport >= 5000)) this.report(d);
      }
      this.evaluate();
    }

    // ---------------- automation engine ----------------
    online(key) { const d = this.get(key); return !!d && d.online; }
    check(c) {
      if (c.device) {
        const d = this.get(c.device);
        if (!d || !d.online || d.state[c.field] == null) return false;
        return OPS[c.op || "=="](d.state[c.field], c.value);
      }
      if (c.mode) return [].concat(c.mode).includes(this.mode);
      if (c.time) { const n = hm(), { after: a, before: b } = c.time; return a <= b ? n >= a && n < b : n >= a || n < b; }
      if (c.at) return hm() === c.at;
      return false;
    }
    evaluate() {
      const now = Date.now();
      for (const r of this.rules) {
        const rt = this.rt[r.id];
        if (!r.enabled || !this.check(r.trigger)) { rt.since = null; rt.fired = false; continue; }
        if (rt.since == null) rt.since = now;
        if (rt.fired || now - rt.since < (r.trigger.for || 0) * 1000) continue;
        rt.fired = true;
        if (now < this.warmUntil && !r.trigger.for) continue;
        if (now - rt.last < (r.cooldown || 0) * 1000) continue;
        if ((r.conditions || []).every((c) => this.check(c))) this.fire(r);
      }
    }
    fire(r) {
      const rt = this.rt[r.id];
      rt.last = rt.lastMs = Date.now();
      const td = r.trigger.device ? this.get(r.trigger.device) : null;
      const ctx = td ? { ...td.state, value: td.state[r.trigger.field] } : {};
      this.notify("rule", `Luật “${r.name}” đã chạy`, `rule:${r.id}`);
      this.engineStatus();
      this.run(r.actions, ctx, `rule:${r.id}`);
    }
    async run(actions, ctx, via) {
      for (const a of actions) {
        if (this.stopped) return;
        if (a.delay) { await new Promise((ok) => this.timers.push(setTimeout(ok, a.delay * 1000))); continue; }
        if (a.set) {
          const keys = a.device ? [a.device] : this.devices
            .filter((d) => d.type === a.type && d.online && !(a.except || []).includes(d.key) && (!a.room || d.room === a.room))
            .map((d) => d.key);
          for (const k of keys) {
            const body = JSON.stringify({ ...a.set, from: "automation", via, ts: Date.now() });
            const [room, id] = k.split("/");
            this.publish(`${this.p}/${room}/${id}/set`, body);
          }
        } else if (a.scene) this.scene(a.scene, via);
        else if (a.mode) this.setMode(a.mode, via);
        else if (a.notify) this.notify(a.level || "info", fill(a.notify, ctx), via);
      }
    }
    control(what, d) {
      if (what === "mode") this.setMode(d.mode, d.from || "?");
      else if (what === "scene") this.scene(d.scene, d.from || "?");
      else if (what === "rule") {
        const r = this.rules.find((x) => x.id === d.id);
        if (r) { r.enabled = !!d.enabled; this.engineStatus(); }
      }
    }
    scene(id, src) {
      const s = SCENES.find((x) => x.id === id);
      if (!s) return;
      this.notify("info", `Chạy kịch bản “${s.name}”`, src);
      this.run(s.actions, {}, `scene:${id}`);
    }
    setMode(m, src) {
      if (!MODES[m]) return;
      const changed = m !== this.mode;
      this.mode = m;
      this.deliver(`${this.p}/_auto/mode/state`, { mode: m, by: src, ts: Date.now() }, false);
      if (changed) { this.notify("info", `Chuyển sang chế độ “${MODES[m]}”`, src); this.evaluate(); }
    }
    notify(level, text, source) { this.deliver(`${this.p}/_auto/notify/event`, { level, text, source, ts: Date.now() }); }
    engineStatus(retain = false) {
      this.deliver(`${this.p}/_auto/engine/status`, {
        state: "online", ts: Date.now(), modes: MODES,
        rules: this.rules.map((r) => ({ id: r.id, name: r.name, description: r.description, enabled: r.enabled, last_fired: this.rt[r.id].lastMs })),
        scenes: SCENES.map((s) => ({ id: s.id, name: s.name, icon: s.icon })),
      }, retain);
    }

    // ---------------- vòng đời ----------------
    start() {
      // lịch sử 5 phút cho biểu đồ (không ghi log)
      const now = Date.now();
      for (const d of this.devices.filter((x) => x.type === "climate")) {
        const save = { t: d.t, h: d.h };
        for (let at = now - 300000; at < now - 5000; at += 5000) {
          d.t += rnd(-0.08, 0.08); d.h += rnd(-0.3, 0.3);
          this.emit(this.topic(d, "state"), JSON.stringify({ ...snapClimate(d), ts: at }), { qos: 1, retain: false, silent: true });
        }
        Object.assign(d, save);
      }
      // giống broker thật: subscriber mới nhận ngay các retained message
      this.warmUntil = now + 3000;
      this.engineStatus(true);
      this.deliver(`${this.p}/_auto/mode/state`, { mode: this.mode, ts: now }, true);
      for (const d of this.devices) { this.status(d, "online", null, true); this.report(d, true); }
      let last = Date.now();
      this.timers.push(setInterval(() => { const t = Date.now(); this.tick((t - last) / 1000); last = t; }, 1000));
      this.timers.push(setInterval(() => {
        this.up += 5;
        this.emit("$SYS/broker/clients/connected", String(this.devices.filter((d) => d.online).length + 3), { qos: 0, retain: true });
        this.emit("$SYS/broker/messages/received", String(this.msgs), { qos: 0, retain: true });
      }, 5000));
    }
    stop() {
      this.stopped = true;
      this.timers.forEach((t) => { clearTimeout(t); clearInterval(t); });
    }
  }

  window.SmartHomeDemo = SmartHomeDemo;
})();
