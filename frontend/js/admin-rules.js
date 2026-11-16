/* Trang quản trị — Quản lý luật tự động (API ghi backend/config/rules.json, automation tự nạp lại).
 *   #/rules         danh sách: tìm kiếm, lọc, điều kiện viết bằng lời, số thiết bị liên quan, khóa (bật/tắt), xóa
 *   #/rules/<mã>    chi tiết: đọc dễ hiểu → "Cập nhật" sửa thông tin chính + điều kiện kích hoạt
 *                   (điều kiện phụ và hành động giữ nguyên)
 * Form "Thêm luật" dựng điều kiện và hành động bằng các dòng chọn sẵn, không phải gõ JSON. */
(() => {
  const { call, esc, toast } = window.Admin;
  const $ = (id) => document.getElementById(id);

  const svg = (d) => `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const ICON_SHIELD = svg('<path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"/><path d="M9 12l2 2 4-4"/>');
  const ICON_LOCK = svg('<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>');
  const ICON_UNLOCK = svg('<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.8-1.2"/>');
  const ICON_TRASH = svg('<path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/>');
  const ICON_X = svg('<path d="M18 6L6 18M6 6l12 12"/>');

  let rules = [];
  let devices = [];              // thiết bị đã đăng ký
  let devMap = new Map();        // "phòng/mã" -> thiết bị
  let rooms = [], types = [];
  let opts = { scenes: [], modes: {} };
  let detail = null;             // luật đang xem ở trang chi tiết
  let formHouse = null;          // địa chỉ nhà của form đang mở: dropdown thiết bị chỉ gồm thiết bị của nhà này
  const houseName = (id) => Admin.houseLabel(id);

  // =========================================================
  //  DIỄN GIẢI LUẬT THÀNH LỜI
  // =========================================================
  const NUM_FIELD = {
    temperature: ["Nhiệt độ", "°C"], humidity: ["Độ ẩm", "%"], ppm: ["Nồng độ gas", " ppm"], power: ["Công suất", " W"],
    position: ["Độ mở rèm", "%"], brightness: ["Độ sáng", "%"], target: ["Nhiệt độ đặt", "°C"], speed: ["Tốc độ quạt", ""],
  };
  const BOOL_FIELD = {
    on: ["đang bật", "đang tắt"], motion: ["có chuyển động", "không có chuyển động"], open: ["đang mở", "đang đóng"],
    locked: ["đã khóa", "chưa khóa"], alarm: ["đang báo động", "hết báo động"],
  };
  const TYPE_FIELDS = {
    climate: ["temperature", "humidity"], light: ["on", "brightness"], fan: ["on", "speed"], ac: ["on", "target"],
    plug: ["on", "power"], curtain: ["position"], lock: ["locked"], door: ["open"], motion: ["motion"], gas: ["alarm", "ppm"],
  };
  const COMMANDS = {
    light: [["Bật", { on: true }], ["Tắt", { on: false }]],
    fan: [["Bật", { on: true }], ["Tắt", { on: false }]],
    ac: [["Bật", { on: true }], ["Tắt", { on: false }]],
    plug: [["Bật", { on: true }], ["Tắt", { on: false }]],
    lock: [["Khóa", { locked: true }], ["Mở khóa", { locked: false }]],
    curtain: [["Mở rèm", { position: 100 }], ["Đóng rèm", { position: 0 }], ["Mở một nửa", { position: 50 }]],
  };
  const FIELD_LABEL = { on: "Bật/tắt", motion: "Chuyển động", open: "Mở/đóng", locked: "Khóa cửa", alarm: "Báo động gas",
    ...Object.fromEntries(Object.entries(NUM_FIELD).map(([k, [l]]) => [k, l])) };
  const OP_TEXT = { "==": "=", "!=": "≠", ">": ">", ">=": "≥", "<": "<", "<=": "≤" };
  const LEVEL_TEXT = { info: "thông tin", warn: "cảnh báo", critical: "nghiêm trọng" };
  const AC_MODE = { cool: "làm lạnh", dry: "hút ẩm", fan: "quạt" };

  const devLabel = (key) => { const d = devMap.get(key); return d ? `${d.name} (${d.room_name})` : key; };
  const roomName = (code) => (rooms.find((r) => r.code === code) || {}).name || code;
  const typeName = (code) => (types.find((t) => t.code === code) || {}).name || code;
  const modeName = (m) => opts.modes[m] || m;
  const sceneName = (id) => (opts.scenes.find((s) => s.id === id) || {}).name || id;
  const duration = (s) => (s % 60 === 0 && s >= 60 ? `${s / 60} phút` : `${s} giây`);

  function compareText(c) {
    if (BOOL_FIELD[c.field] && typeof c.value === "boolean" && (c.op === "==" || c.op === "!=" || !c.op)) {
      const truth = c.op === "!=" ? !c.value : c.value;
      return `${devLabel(c.device)} ${BOOL_FIELD[c.field][truth ? 0 : 1]}`;
    }
    const [label, unit] = NUM_FIELD[c.field] || [c.field, ""];
    const d = devMap.get(c.device);
    const subject = d && d.type === "climate" ? `${label} ${d.room_name}` : `${label} ${devLabel(c.device)}`;
    return `${subject} ${OP_TEXT[c.op || "=="] || c.op} ${c.value}${unit}`;
  }

  function triggerText(t) {
    if (!t) return "";
    if (t.at) return `Lúc ${t.at}`;
    return compareText(t) + (t.for ? ` liên tục ${duration(t.for)}` : "");
  }

  function condText(c) {
    if (c.device) return compareText(c);
    if (c.mode) return `Chế độ nhà: ${[].concat(c.mode).map(modeName).join(" hoặc ")}`;
    if (c.time) return `Trong khung giờ ${c.time.after}–${c.time.before}`;
    if (c.at) return `Lúc ${c.at}`;
    return JSON.stringify(c);
  }

  function setText(set) {
    let verb = "Điều khiển";
    const extra = [];
    for (const [k, v] of Object.entries(set)) {
      if (k === "on") verb = v ? "Bật" : "Tắt";
      else if (k === "locked") verb = v ? "Khóa" : "Mở khóa";
      else if (k === "position") verb = v >= 100 ? "Mở" : v <= 0 ? "Đóng" : `Mở ${v}%`;
      else if (k === "brightness") extra.push(`độ sáng ${v}%`);
      else if (k === "target") extra.push(`${v}°C`);
      else if (k === "speed") extra.push(`tốc độ ${v}`);
      else if (k === "mode") extra.push(AC_MODE[v] || v);
      else extra.push(`${k} = ${JSON.stringify(v)}`);
    }
    return [verb, extra];
  }

  function actionText(a) {
    if (a.set) {
      const [verb, extra] = setText(a.set);
      const target = a.device ? devLabel(a.device)
        : `tất cả ${typeName(a.type).toLowerCase()}${a.room ? ` ở ${roomName(a.room)}` : ""}` +
          (a.except && a.except.length ? ` (trừ ${a.except.map(devLabel).join(", ")})` : "");
      return `${verb} ${target}${extra.length ? " · " + extra.join(", ") : ""}`;
    }
    if (a.notify) return `Gửi thông báo ${LEVEL_TEXT[a.level] || a.level || "thông tin"}: “${a.notify}”`;
    if (a.delay) return `Chờ ${duration(a.delay)}`;
    if (a.scene) return `Chạy kịch bản “${sceneName(a.scene)}”`;
    if (a.mode) return `Chuyển sang chế độ ${modeName(a.mode)}`;
    return JSON.stringify(a);
  }

  /* Các thiết bị luật dùng tới: kích hoạt, điều kiện, hành động (hành động theo loại tính các thiết bị cùng loại). */
  function relatedDevices(rule) {
    const keys = new Set();
    const t = rule.trigger || {};
    if (t.device) keys.add(t.device);
    (rule.conditions || []).forEach((c) => c.device && keys.add(c.device));
    (rule.actions || []).forEach((a) => {
      if (a.device) keys.add(a.device);
      else if (a.type) devices.filter((d) => d.type === a.type && (!a.room || d.room === a.room) && !(a.except || []).includes(d.key))
        .forEach((d) => keys.add(d.key));
    });
    return [...keys].sort();
  }

  // =========================================================
  //  DANH SÁCH
  // =========================================================
  const F = { q: $("ruleSearch"), house: $("ruleHouseFilter"), kind: $("ruleKindFilter"), room: $("ruleRoomFilter"), status: $("ruleStatusFilter") };
  const filtersOn = () => Object.values(F).some((x) => x.value.trim());

  function filtered() {
    const q = F.q.value.trim().toLowerCase();
    return rules.filter((r) => {
      const on = r.enabled !== false;
      return (!q || r.name.toLowerCase().includes(q) || r.id.includes(q)) &&
        Admin.houseMatches(r.house_id, F.house.value) &&
        (!F.kind.value || (F.kind.value === "at") === !!(r.trigger || {}).at) &&
        (!F.status.value || (F.status.value === "on") === on) &&
        (!F.room.value || relatedDevices(r).some((k) => k.startsWith(F.room.value + "/")));
    });
  }

  function renderList() {
    const rows = filtered();
    $("rulesNote").textContent = `${rows.length} luật` + (filtersOn() ? " khớp bộ lọc" : "") + " ·";
    $("rulesBody").innerHTML = rows.length ? rows.map((r) => {
      const on = r.enabled !== false;
      const rel = relatedDevices(r);
      return `<tr class="${on ? "" : "disabled"}">
        <td class="wrap">${esc(r.name)}<small>${esc(r.id)}</small></td>
        <td class="wrap addr">${Admin.houseCell(r.house_id)}</td>
        <td class="wrap cond-cell"><span class="cond-main"><b>Khi</b> ${esc(triggerText(r.trigger))}</span>
          ${(r.conditions || []).map((c) => `<span class="cond-sub"><b>và</b> ${esc(condText(c))}</span>`).join("")}</td>
        <td class="num"><span class="rel-count" title="${esc(rel.map(devLabel).join("\n"))}">${rel.length}</span></td>
        <td><span class="tag ${on ? "ok" : "bad"}">${on ? "Đang bật" : "Đã tắt"}</span></td>
        <td class="actions">
          <button type="button" class="icon-btn" data-detail="${esc(r.id)}" title="Xem chi tiết" aria-label="Xem chi tiết ${esc(r.name)}">${ICON_SHIELD}</button>
          <button type="button" class="icon-btn ${on ? "" : "warn"}" data-toggle="${esc(r.id)}" title="${on ? "Tắt luật" : "Bật luật"}"
            aria-label="${on ? "Tắt" : "Bật"} luật ${esc(r.name)}">${on ? ICON_LOCK : ICON_UNLOCK}</button>
          <button type="button" class="icon-btn danger" data-del="${esc(r.id)}" title="Xóa" aria-label="Xóa luật ${esc(r.name)}">${ICON_TRASH}</button>
        </td></tr>`;
    }).join("") : `<tr><td colspan="6" class="muted">${filtersOn() ? "Không có luật nào khớp bộ lọc." : "Chưa có luật nào."}</td></tr>`;
  }

  async function loadAll() {
    const [r, d, o, ro] = await Promise.all([call("/api/admin/rules"), call("/api/admin/devices"),
      call("/api/admin/device-options"), call("/api/admin/rule-options"), Admin.loadHouses()]);
    rules = r; devices = d; rooms = o.rooms; types = o.types; opts = ro;
    devMap = new Map(devices.map((x) => [x.key, x]));
    Admin.setBadge("rules", rules.length);
    const cur = F.room.value;
    F.room.innerHTML = '<option value="">Tất cả</option>' + rooms.map((x) => `<option value="${esc(x.code)}">${esc(x.name)}</option>`).join("");
    F.room.value = cur;
  }

  let searchTimer = null;
  [F.q, F.house].forEach((x) => x.addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(renderList, 150); }));
  [F.kind, F.room, F.status].forEach((s) => s.addEventListener("change", renderList));
  $("ruleFilter").addEventListener("submit", (e) => { e.preventDefault(); renderList(); });
  $("btnClearRuleFilter").addEventListener("click", () => { Object.values(F).forEach((x) => (x.value = "")); renderList(); });

  async function toggleRule(r) {
    const enabled = r.enabled === false;
    const ok = await Admin.confirm(enabled
      ? { title: "Bật luật", ok: "Bật", message: `Bật luật “${r.name}”? Automation sẽ chạy luật này khi đủ điều kiện.` }
      : { title: "Tắt luật", kind: "warn", ok: "Tắt", message: `Tắt luật “${r.name}”? Automation sẽ ngừng chạy luật này cho tới khi bật lại.` });
    if (!ok) return false;
    try {
      await call(`/api/admin/rules/${encodeURIComponent(r.id)}/enabled`, "PUT", { enabled });
      toast(`${enabled ? "Đã bật" : "Đã tắt"} luật “${r.name}”`);
      return true;
    } catch (err) { toast(err.message, "bad"); return false; }
  }

  async function removeRule(r) {
    const ok = await Admin.confirm({ title: "Xóa luật tự động", kind: "danger", ok: "Xóa",
      message: `Xóa luật “${r.name}”? Automation sẽ ngừng chạy luật này ngay.` });
    if (!ok) return false;
    try {
      await call(`/api/admin/rules/${encodeURIComponent(r.id)}`, "DELETE");
      toast(`Đã xóa luật “${r.name}”`);
      return true;
    } catch (err) { toast(err.message, "bad"); return false; }
  }

  $("ruleListPanel").addEventListener("click", async (e) => {
    const det = e.target.closest("[data-detail]");
    const tog = e.target.closest("[data-toggle]");
    const del = e.target.closest("[data-del]");
    const find = (id) => rules.find((r) => r.id === id);
    if (det) location.hash = `#/rules/${encodeURIComponent(det.dataset.detail)}`;
    if (tog && await toggleRule(find(tog.dataset.toggle))) { await loadAll(); renderList(); }
    if (del && await removeRule(find(del.dataset.del))) { await loadAll(); renderList(); }
  });

  // =========================================================
  //  Ô NHẬP SO SÁNH TRẠNG THÁI THIẾT BỊ (dùng cho kích hoạt và điều kiện)
  // =========================================================
  const deviceOptions = (filter = () => true, selected = "") =>
    devices.filter((d) => (formHouse === null || d.house_id === formHouse) && filter(d)).map((d) => `<option value="${esc(d.key)}" ${d.key === selected ? "selected" : ""}>${esc(d.name)} — ${esc(d.room_name)} (${esc(d.key)})</option>`).join("");
  const SENSING = (d) => !!TYPE_FIELDS[d.type];

  /* Dựng các ô: thiết bị → trường (theo loại) → giá trị. Trường đúng/sai chọn bằng câu (vd "đang bật"),
   * trường số chọn phép so sánh + số. Trả về hàm get() đọc ra {device, field, op, value}. */
  function compareEditor(box, init = {}) {
    box.innerHTML = `
      <div class="field cmp-dev"><label>Thiết bị</label><select data-k="device">${deviceOptions(SENSING, init.device)}</select></div>
      <div class="field"><label>Trạng thái</label><select data-k="field"></select></div>
      <div class="field cmp-val"></div>`;
    const dev = box.querySelector('[data-k="device"]');
    const field = box.querySelector('[data-k="field"]');
    const valBox = box.querySelector(".cmp-val");

    function fillFields(keep) {
      const d = devMap.get(dev.value);
      const list = [...(TYPE_FIELDS[d && d.type] || [])];
      if (keep && !list.includes(keep)) list.push(keep);
      field.innerHTML = list.map((f) => `<option value="${f}">${esc(FIELD_LABEL[f] || f)}</option>`).join("");
      if (keep) field.value = keep;
    }
    function fillValue(initVal) {
      const f = field.value;
      if (BOOL_FIELD[f]) {
        const truth = initVal.value === undefined ? true : (initVal.op === "!=" ? !initVal.value : !!initVal.value);
        valBox.innerHTML = `<label>Giá trị</label><select data-k="bool">
          <option value="1">${esc(BOOL_FIELD[f][0])}</option><option value="0">${esc(BOOL_FIELD[f][1])}</option></select>`;
        valBox.querySelector("select").value = truth ? "1" : "0";
      } else {
        const unit = (NUM_FIELD[f] || [])[1] || "";
        valBox.innerHTML = `<label>Giá trị${unit ? ` (${esc(unit.trim())})` : ""}</label><div class="inline">
          <select data-k="op">${Object.keys(OP_TEXT).map((o) => `<option value="${o}">${esc(OP_TEXT[o])}</option>`).join("")}</select>
          <input data-k="num" type="number" step="any"></div>`;
        valBox.querySelector('[data-k="op"]').value = initVal.op || ">";
        valBox.querySelector('[data-k="num"]').value = typeof initVal.value === "number" ? initVal.value : "";
      }
    }
    fillFields(init.field);
    fillValue(init.field === field.value ? init : {});
    dev.addEventListener("change", () => { fillFields(); fillValue({}); });
    field.addEventListener("change", () => fillValue({}));

    return () => {
      const f = field.value;
      if (!dev.value || !f) throw new Error("Chọn thiết bị và trạng thái cần kiểm tra");
      if (BOOL_FIELD[f]) return { device: dev.value, field: f, op: "==", value: valBox.querySelector("select").value === "1" };
      const num = valBox.querySelector('[data-k="num"]').value;
      if (num === "") throw new Error(`Nhập giá trị cho “${(NUM_FIELD[f] || [f])[0]}”`);
      return { device: dev.value, field: f, op: valBox.querySelector('[data-k="op"]').value, value: Number(num) };
    };
  }

  /* Khối "Khi" (điều kiện kích hoạt): theo trạng thái thiết bị hoặc theo giờ. Trả về hàm get(). */
  function triggerEditor(fieldset, init = {}) {
    fieldset.innerHTML = `<legend>Khi (điều kiện kích hoạt)</legend>
      <div class="seg trig-kind"><button type="button" data-kind="device">Trạng thái thiết bị</button><button type="button" data-kind="at">Đến giờ</button></div>
      <div class="form-grid trig-dev"></div>
      <div class="form-grid trig-at"><div class="field"><label>Giờ</label><input type="time" data-k="at"></div></div>
      <div class="form-grid trig-for"><div class="field"><label>Giữ liên tục (giây, tùy chọn)</label><input type="number" min="0" data-k="for" placeholder="0"></div></div>`;
    const getCmp = compareEditor(fieldset.querySelector(".trig-dev"), init.at ? {} : init);
    let kind = init.at ? "at" : "device";
    const setKind = (k) => {
      kind = k;
      fieldset.querySelectorAll(".trig-kind button").forEach((b) => b.classList.toggle("on", b.dataset.kind === k));
      fieldset.querySelector(".trig-dev").hidden = fieldset.querySelector(".trig-for").hidden = k !== "device";
      fieldset.querySelector(".trig-at").hidden = k !== "at";
    };
    fieldset.querySelector(".trig-kind").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) setKind(b.dataset.kind); });
    fieldset.querySelector('[data-k="at"]').value = init.at || "";
    fieldset.querySelector('[data-k="for"]').value = init.for || "";
    setKind(kind);
    return () => {
      if (kind === "at") {
        const at = fieldset.querySelector('[data-k="at"]').value;
        if (!at) throw new Error("Chọn giờ kích hoạt");
        return { at };
      }
      const t = getCmp();
      const sec = Number(fieldset.querySelector('[data-k="for"]').value);
      return sec > 0 ? { ...t, for: sec } : t;
    };
  }

  // =========================================================
  //  TRANG CHI TIẾT + SỬA
  // =========================================================
  let getEditTrigger = null;

  function showRdError(msg) { $("rdError").textContent = msg; $("rdError").hidden = !msg; }

  function renderDetail() {
    const r = detail, on = r.enabled !== false, rel = relatedDevices(r);
    $("rdTitle").textContent = r.name;
    $("rdSub").textContent = `Luật ${r.id} · ${(r.actions || []).length} hành động · ${rel.length} thiết bị liên quan`;
    $("rdCode").textContent = r.id;
    $("rdStatus").innerHTML = `<span class="tag ${on ? "ok" : "bad"}">${on ? "Đang bật" : "Đã tắt"}</span>`;
    $("rdCooldown").textContent = r.cooldown ? duration(r.cooldown) : "Không";
    $("rdHouse").textContent = houseName(r.house_id);
    $("rdDesc").textContent = r.description || "—";
    $("rdConds").innerHTML = [`<li><b>Khi</b> ${esc(triggerText(r.trigger))}</li>`]
      .concat((r.conditions || []).map((c) => `<li><b>và</b> ${esc(condText(c))}</li>`)).join("");
    $("rdActions").innerHTML = (r.actions || []).map((a) => `<li>${esc(actionText(a))}</li>`).join("");
    $("rdDevices").innerHTML = rel.length
      ? rel.map((k) => `<span class="chip ${devMap.get(k)?.is_simulated === false ? "real" : "sim"}">${esc(devLabel(k))}</span>`).join("")
      : '<span class="muted">Không có</span>';
    Admin.setCrumb(`Luật tự động / ${r.id}`);
  }

  function setEditing(on) {
    $("rdView").hidden = on;
    $("rdForm").hidden = !on;
    showRdError("");
    if (!on) return;
    const r = detail;
    $("reName").value = r.name;
    $("reDesc").value = r.description || "";
    $("reCooldown").value = r.cooldown || "";
    $("reEnabled").value = r.enabled === false ? "0" : "1";
    Admin.fillHouseSelect($("reHouse"), { selected: r.house_id });
    formHouse = Number($("reHouse").value) || null;
    getEditTrigger = triggerEditor($("reTrigger"), r.trigger || {});
    $("reName").focus();
  }

  async function openDetail(id) {
    $("ruleListPanel").hidden = true;
    $("ruleDetail").hidden = false;
    $("rdView").hidden = false;
    $("rdForm").hidden = true;
    showRdError("");
    try {
      await loadAll();
      detail = rules.find((r) => r.id === id);
      if (!detail) throw new Error(`Không tìm thấy luật “${id}”`);
      renderDetail();
    } catch (err) {
      detail = null;
      $("rdTitle").textContent = "Không mở được luật";
      $("rdSub").textContent = "";
      showRdError(err.message);
    }
  }

  $("btnRdCancel").addEventListener("click", () => { location.hash = "#/rules"; });
  $("btnRdEdit").addEventListener("click", () => detail && setEditing(true));
  $("btnReCancel").addEventListener("click", () => setEditing(false));

  $("rdForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("btnReSave").disabled = true;
    try {
      const body = {
        ...detail,                                   // giữ nguyên điều kiện phụ và hành động
        name: $("reName").value.trim(),
        description: $("reDesc").value.trim(),
        enabled: $("reEnabled").value === "1",
        house_id: Number($("reHouse").value),
        trigger: getEditTrigger(),
        cooldown: Number($("reCooldown").value) > 0 ? Number($("reCooldown").value) : undefined,
      };
      detail = await call(`/api/admin/rules/${encodeURIComponent(detail.id)}`, "PUT", body);
      toast(`Đã cập nhật luật “${detail.name}”`);
      await loadAll();
      setEditing(false);
      renderDetail();
    } catch (err) {
      showRdError(err.message);
    }
    $("btnReSave").disabled = false;
  });

  // =========================================================
  //  FORM THÊM LUẬT (dựng điều kiện và hành động bằng các dòng chọn sẵn)
  // =========================================================
  let getAddTrigger = null;
  const condGetters = new Map();     // dòng -> hàm đọc giá trị
  const actGetters = new Map();

  function addRow(container, getters, kinds, kindLabel) {
    const row = document.createElement("div");
    row.className = "builder-row";
    row.innerHTML = `<select class="row-kind" aria-label="${esc(kindLabel)}">${Object.entries(kinds).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join("")}</select>
      <div class="row-body form-grid"></div>
      <button type="button" class="icon-btn danger row-del" title="Bỏ dòng này" aria-label="Bỏ dòng này">${ICON_X}</button>`;
    const kindSel = row.querySelector(".row-kind");
    const body = row.querySelector(".row-body");
    const build = () => getters.set(row, kinds[kindSel.value].build(body));
    kindSel.addEventListener("change", build);
    row.querySelector(".row-del").addEventListener("click", () => { getters.delete(row); row.remove(); });
    container.append(row);
    build();
  }

  const CONDITION_KINDS = {
    mode: { label: "Chế độ nhà", build(body) {
      body.innerHTML = `<div class="field full"><label>Chế độ đang là (chọn một hoặc nhiều)</label><div class="check-row">${
        Object.entries(opts.modes).map(([k, v]) => `<label class="check-field"><input type="checkbox" value="${esc(k)}"> ${esc(v)}</label>`).join("")}</div></div>`;
      return () => {
        const modes = [...body.querySelectorAll("input:checked")].map((x) => x.value);
        if (!modes.length) throw new Error("Điều kiện “Chế độ nhà”: chọn ít nhất một chế độ");
        return { mode: modes };
      };
    } },
    device: { label: "Trạng thái thiết bị", build(body) { return compareEditor(body); } },
    time: { label: "Khung giờ", build(body) {
      body.innerHTML = `<div class="field"><label>Từ</label><input type="time" data-k="after"></div>
        <div class="field"><label>Đến (qua nửa đêm được)</label><input type="time" data-k="before"></div>`;
      return () => {
        const after = body.querySelector('[data-k="after"]').value, before = body.querySelector('[data-k="before"]').value;
        if (!after || !before) throw new Error("Điều kiện “Khung giờ”: chọn đủ giờ bắt đầu và kết thúc");
        return { time: { after, before } };
      };
    } },
  };

  const ACTION_KINDS = {
    device: { label: "Điều khiển thiết bị", build(body) {
      body.innerHTML = `<div class="field"><label>Thiết bị</label><select data-k="device">${deviceOptions((d) => !!COMMANDS[d.type])}</select></div>
        <div class="field"><label>Lệnh</label><select data-k="cmd"></select></div>`;
      const dev = body.querySelector('[data-k="device"]'), cmd = body.querySelector('[data-k="cmd"]');
      const fill = () => { cmd.innerHTML = (COMMANDS[devMap.get(dev.value)?.type] || []).map(([l], i) => `<option value="${i}">${esc(l)}</option>`).join(""); };
      dev.addEventListener("change", fill);
      fill();
      return () => {
        if (!dev.value) throw new Error("Hành động “Điều khiển thiết bị”: chọn thiết bị");
        return { device: dev.value, set: COMMANDS[devMap.get(dev.value).type][Number(cmd.value)][1] };
      };
    } },
    notify: { label: "Gửi thông báo", build(body) {
      body.innerHTML = `<div class="field full"><label>Nội dung (có thể chèn {temperature}, {ppm}…)</label><input data-k="text" autocomplete="off"></div>
        <div class="field"><label>Mức độ</label><select data-k="level"><option value="info">Thông tin</option><option value="warn">Cảnh báo</option><option value="critical">Nghiêm trọng</option></select></div>`;
      return () => {
        const text = body.querySelector('[data-k="text"]').value.trim();
        if (!text) throw new Error("Hành động “Gửi thông báo”: nhập nội dung");
        return { notify: text, level: body.querySelector('[data-k="level"]').value };
      };
    } },
    delay: { label: "Chờ", build(body) {
      body.innerHTML = '<div class="field"><label>Số giây</label><input type="number" min="1" max="3600" data-k="sec" value="30"></div>';
      return () => {
        const s = Number(body.querySelector('[data-k="sec"]').value);
        if (!(s > 0)) throw new Error("Hành động “Chờ”: nhập số giây lớn hơn 0");
        return { delay: s };
      };
    } },
    mode: { label: "Đổi chế độ nhà", build(body) {
      body.innerHTML = `<div class="field"><label>Chế độ</label><select data-k="mode">${Object.entries(opts.modes).map(([k, v]) => `<option value="${esc(k)}">${esc(v)}</option>`).join("")}</select></div>`;
      return () => ({ mode: body.querySelector('[data-k="mode"]').value });
    } },
    scene: { label: "Chạy kịch bản", build(body) {
      body.innerHTML = `<div class="field"><label>Kịch bản</label><select data-k="scene">${opts.scenes.map((s) => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join("")}</select></div>`;
      return () => ({ scene: body.querySelector('[data-k="scene"]').value });
    } },
  };

  /* Dựng lại phần "Khi / Và chỉ khi / Thì làm" theo địa chỉ nhà đang chọn (đổi nhà thì thiết bị cũng đổi). */
  function resetAddBuilders() {
    formHouse = Number($("ruleHouse").value) || null;
    getAddTrigger = triggerEditor($("ruleTrigger"));
    $("condRows").innerHTML = ""; condGetters.clear();
    $("actRows").innerHTML = ""; actGetters.clear();
    addRow($("actRows"), actGetters, ACTION_KINDS, "Loại hành động");
  }
  $("ruleHouse").addEventListener("change", resetAddBuilders);
  // Form sửa: đổi địa chỉ nhà thì chọn lại thiết bị kích hoạt (điều kiện phụ/hành động phải thuộc nhà mới, server sẽ kiểm tra)
  $("reHouse").addEventListener("change", () => {
    formHouse = Number($("reHouse").value) || null;
    getEditTrigger = triggerEditor($("reTrigger"), {});
  });

  function openAdd() {
    $("ruleError").hidden = true;
    ["ruleId", "ruleName", "ruleDesc", "ruleCooldown"].forEach((id) => ($(id).value = ""));
    $("ruleEnabled").checked = true;
    Admin.fillHouseSelect($("ruleHouse"));
    resetAddBuilders();
    $("ruleDialog").showModal();
    $("ruleId").focus();
  }

  $("btnAddRule").addEventListener("click", async () => {
    try { if (!devices.length) await loadAll(); openAdd(); } catch (err) { toast(err.message, "bad"); }
  });
  $("btnAddCond").addEventListener("click", () => addRow($("condRows"), condGetters, CONDITION_KINDS, "Loại điều kiện"));
  $("btnAddAct").addEventListener("click", () => addRow($("actRows"), actGetters, ACTION_KINDS, "Loại hành động"));

  $("ruleForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("ruleError").hidden = true;
    $("ruleSubmit").disabled = true;
    try {
      const actions = [...actGetters.values()].map((g) => g());
      if (!actions.length) throw new Error("Luật cần ít nhất một hành động");
      const body = {
        id: $("ruleId").value.trim(),
        name: $("ruleName").value.trim(),
        description: $("ruleDesc").value.trim(),
        enabled: $("ruleEnabled").checked,
        house_id: Number($("ruleHouse").value),
        trigger: getAddTrigger(),
        conditions: [...condGetters.values()].map((g) => g()),
        actions,
        ...(Number($("ruleCooldown").value) > 0 ? { cooldown: Number($("ruleCooldown").value) } : {}),
      };
      await call("/api/admin/rules", "POST", body);
      $("ruleDialog").close();
      toast(`Đã thêm luật “${body.name}”`);
      await loadAll();
      renderList();
    } catch (err) {
      $("ruleError").textContent = err.message;
      $("ruleError").hidden = false;
      $("ruleError").scrollIntoView({ block: "nearest" });
    }
    $("ruleSubmit").disabled = false;
  });

  // =========================================================
  //  ĐIỀU HƯỚNG
  // =========================================================
  document.addEventListener("admin:route", async (e) => {
    const { page, sub } = e.detail;
    if (page !== "rules") return;
    if (sub) { openDetail(decodeURIComponent(sub)); return; }
    detail = null;
    $("ruleDetail").hidden = true;
    $("ruleListPanel").hidden = false;
    try { await loadAll(); renderList(); }
    catch (err) { $("rulesBody").innerHTML = `<tr><td colspan="6" class="muted">${esc(err.message)}</td></tr>`; }
  });
})();
