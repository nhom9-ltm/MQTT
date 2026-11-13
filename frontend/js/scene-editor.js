/* Thêm kịch bản mới từ dashboard.
 * Người dùng ghép các "bước" (điều khiển một thiết bị, cả nhóm thiết bị, đổi chế độ, chờ, thông báo); form gửi
 *   home/_auto/scene/set  {"add": {name, icon, actions:[…]}}
 * Automation engine kiểm tra lại (backend/services/scene_validation.py), lưu vào backend/config/scenes.custom.json rồi phát lại
 * danh sách kịch bản, nên nút kịch bản mới tự xuất hiện ở Trang chủ, Thiết bị và Kịch bản.
 * Dùng chung kết nối và danh sách thiết bị của app.js qua window.SmartHomeApp. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const dlg = $("sceneDialog");
  const btnOpen = $("btnAddScene");
  if (!dlg || !btnOpen) return;

  const form = $("sceneForm"), steps = $("sceneSteps"), errBox = $("sceneErr"), btnSave = $("sceneSave");
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const TYPE_LABEL = { light: "Đèn", fan: "Quạt", ac: "Điều hòa", curtain: "Rèm", lock: "Khóa cửa", plug: "Ổ cắm" };
  const MODES = { home: "Ở nhà", away: "Vắng nhà", night: "Ban đêm" };
  const BOOL = (on, off) => ({ kind: "bool", on, off });
  // Thông số điều khiển được của từng loại thiết bị (phải khớp SET_SPEC ở backend/services/scene_validation.py)
  const PARAMS = {
    light: [{ k: "on", label: "Trạng thái", ...BOOL("Bật", "Tắt") }, { k: "brightness", label: "Độ sáng (%)", kind: "num", min: 1, max: 100 }],
    fan: [{ k: "on", label: "Trạng thái", ...BOOL("Bật", "Tắt") }, { k: "speed", label: "Tốc độ (1–3)", kind: "num", min: 1, max: 3 }],
    ac: [{ k: "on", label: "Trạng thái", ...BOOL("Bật", "Tắt") },
      { k: "mode", label: "Chế độ", kind: "enum", options: [["cool", "Làm lạnh"], ["dry", "Hút ẩm"], ["fan", "Quạt"]] },
      { k: "target", label: "Nhiệt độ đặt (°C)", kind: "num", min: 16, max: 30 }],
    curtain: [{ k: "position", label: "Độ mở (%)", kind: "num", min: 0, max: 100 }],
    lock: [{ k: "locked", label: "Trạng thái", ...BOOL("Khóa", "Mở khóa") }],
    plug: [{ k: "on", label: "Trạng thái", ...BOOL("Bật", "Tắt") }],
  };
  const KINDS = [["device", "Điều khiển một thiết bị"], ["group", "Điều khiển cả nhóm thiết bị"],
    ["mode", "Đổi chế độ nhà"], ["delay", "Chờ"], ["notify", "Gửi thông báo"]];

  // ---------------------------------------------------------------- dựng form
  const app = () => window.SmartHomeApp;
  const controllable = () => (app()?.devices() || []).filter((d) => PARAMS[d.type]);

  function paramFields(type) {
    return (PARAMS[type] || []).map((p) => {
      if (p.kind === "bool") return `<label class="sd-field">${p.label}<select data-k="${p.k}"><option value="">— không đổi —</option><option value="1">${p.on}</option><option value="0">${p.off}</option></select></label>`;
      if (p.kind === "enum") return `<label class="sd-field">${p.label}<select data-k="${p.k}"><option value="">— không đổi —</option>${p.options.map(([v, t]) => `<option value="${v}">${t}</option>`).join("")}</select></label>`;
      return `<label class="sd-field">${p.label}<input type="number" data-k="${p.k}" min="${p.min}" max="${p.max}" placeholder="không đổi"></label>`;
    }).join("");
  }

  function kindFields(kind, li) {
    if (kind === "device") {
      const byRoom = {};
      for (const d of controllable()) (byRoom[d.roomName] ||= []).push(d);
      const opts = Object.entries(byRoom).map(([room, list]) =>
        `<optgroup label="${esc(room)}">${list.map((d) => `<option value="${esc(d.key)}" data-type="${d.type}">${esc(d.name)} (${TYPE_LABEL[d.type]})</option>`).join("")}</optgroup>`).join("");
      return `<label class="sd-field sd-grow">Thiết bị<select data-role="target">${opts || '<option value="">Chưa phát hiện thiết bị nào</option>'}</select></label><div class="sd-params"></div>`;
    }
    if (kind === "group") {
      const rooms = [...new Map(controllable().map((d) => [d.room, d.roomName]))];
      return `<label class="sd-field">Loại<select data-role="gtype">${Object.entries(TYPE_LABEL).map(([t, l]) => `<option value="${t}">${l}</option>`).join("")}</select></label>
        <label class="sd-field">Phòng<select data-role="groom"><option value="">Tất cả phòng</option>${rooms.map(([r, n]) => `<option value="${esc(r)}">${esc(n)}</option>`).join("")}</select></label><div class="sd-params"></div>`;
    }
    if (kind === "mode") return `<label class="sd-field sd-grow">Chuyển sang<select data-role="mode">${Object.entries(MODES).map(([v, t]) => `<option value="${v}">${t}</option>`).join("")}</select></label>`;
    if (kind === "delay") return `<label class="sd-field">Số giây<input type="number" data-role="delay" min="1" max="3600" value="3"></label>`;
    return `<label class="sd-field sd-grow">Nội dung<input data-role="text" maxlength="200" placeholder="Nội dung thông báo"></label>
      <label class="sd-field">Mức<select data-role="level"><option value="info">Thông tin</option><option value="warn">Cảnh báo</option><option value="critical">Nghiêm trọng</option></select></label>`;
  }

  function refreshParams(li) {
    const box = li.querySelector(".sd-params");
    if (!box) return;
    const kind = li.dataset.kind;
    const type = kind === "device" ? li.querySelector("[data-role=target] option:checked")?.dataset.type
      : li.querySelector("[data-role=gtype]")?.value;
    box.innerHTML = paramFields(type);
  }

  function addStep(kind = "device") {
    const li = document.createElement("li");
    li.className = "sd-step";
    li.innerHTML = `<div class="sd-step-bar">
        <span class="sd-num"></span>
        <select class="sd-kind" aria-label="Loại bước">${KINDS.map(([v, t]) => `<option value="${v}">${t}</option>`).join("")}</select>
        <span class="sd-tools">
          <button type="button" class="btn ghost sm" data-act="up" aria-label="Lên" title="Chuyển lên">↑</button>
          <button type="button" class="btn ghost sm" data-act="down" aria-label="Xuống" title="Chuyển xuống">↓</button>
          <button type="button" class="btn ghost sm" data-act="del" aria-label="Xóa bước" title="Xóa bước">✕</button>
        </span></div><div class="sd-fields"></div>`;
    li.querySelector(".sd-kind").value = kind;
    steps.append(li);
    setKind(li, kind);
    renumber();
    return li;
  }

  function setKind(li, kind) {
    li.dataset.kind = kind;
    li.querySelector(".sd-fields").innerHTML = kindFields(kind, li);
    refreshParams(li);
  }

  function renumber() {
    [...steps.children].forEach((li, i) => { li.querySelector(".sd-num").textContent = i + 1; });
  }

  steps.addEventListener("change", (e) => {
    const li = e.target.closest(".sd-step");
    if (!li) return;
    if (e.target.classList.contains("sd-kind")) setKind(li, e.target.value);
    else if (e.target.matches("[data-role=target], [data-role=gtype]")) refreshParams(li);
  });
  steps.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-act]");
    if (!b) return;
    const li = b.closest(".sd-step");
    if (b.dataset.act === "del") li.remove();
    else if (b.dataset.act === "up" && li.previousElementSibling) li.previousElementSibling.before(li);
    else if (b.dataset.act === "down" && li.nextElementSibling) li.nextElementSibling.after(li);
    renumber();
  });
  $("sceneAddStep").addEventListener("click", () => addStep().querySelector("select, input")?.focus());

  // ---------------------------------------------------------------- đọc form -> dữ liệu kịch bản
  class FormError extends Error {}

  function readSet(li, type, n) {
    const set = {};
    for (const p of PARAMS[type] || []) {
      const field = li.querySelector(`.sd-params [data-k="${p.k}"]`);
      const v = field ? field.value.trim() : "";
      if (v === "") continue;
      if (p.kind === "bool") set[p.k] = v === "1";
      else if (p.kind === "enum") set[p.k] = v;
      else {
        const num = Number(v);
        if (!Number.isFinite(num) || num < p.min || num > p.max) throw new FormError(`Bước ${n}: “${p.label}” phải từ ${p.min} đến ${p.max}`);
        set[p.k] = num;
      }
    }
    if (!Object.keys(set).length) throw new FormError(`Bước ${n}: hãy chọn ít nhất một thông số cần đặt`);
    return set;
  }

  function readScene() {
    const name = $("sceneName").value.trim().replace(/\s+/g, " ");
    if (!name) throw new FormError("Hãy nhập tên kịch bản");
    const existing = (app()?.scenes() || []).find((s) => s.name.toLowerCase() === name.toLowerCase());
    if (existing) throw new FormError(`Đã có kịch bản tên “${existing.name}”`);
    const rows = [...steps.children];
    if (!rows.length) throw new FormError("Hãy thêm ít nhất một bước");
    const actions = rows.map((li, i) => {
      const n = i + 1, kind = li.dataset.kind, q = (r) => li.querySelector(`[data-role="${r}"]`);
      if (kind === "device") {
        const key = q("target")?.value;
        if (!key) throw new FormError(`Bước ${n}: chưa chọn thiết bị`);
        return { device: key, set: readSet(li, q("target").selectedOptions[0].dataset.type, n) };
      }
      if (kind === "group") {
        const a = { type: q("gtype").value, set: readSet(li, q("gtype").value, n) };
        if (q("groom").value) a.room = q("groom").value;
        return a;
      }
      if (kind === "mode") return { mode: q("mode").value };
      if (kind === "delay") {
        const s = Number(q("delay").value);
        if (!(s > 0 && s <= 3600)) throw new FormError(`Bước ${n}: thời gian chờ phải từ 1 đến 3600 giây`);
        return { delay: s };
      }
      const text = q("text").value.trim();
      if (!text) throw new FormError(`Bước ${n}: hãy nhập nội dung thông báo`);
      return { notify: text, level: q("level").value };
    });
    if (actions.every((a) => "delay" in a)) throw new FormError("Kịch bản chỉ có bước chờ thì không làm gì cả");
    return { name, icon: $("sceneIcon").value.trim() || "▶", actions };
  }

  // ---------------------------------------------------------------- mở / đóng / gửi
  function showError(msg) {
    errBox.textContent = msg;
    errBox.hidden = !msg;
  }

  function open() {
    form.reset();
    steps.innerHTML = "";
    showError("");
    btnSave.disabled = false;
    btnSave.textContent = "Lưu kịch bản";
    addStep("device");
    if (!app() || !app().engineOnline()) showError("Automation engine chưa chạy (python backend/run_automation.py) nên chưa thể thêm kịch bản.");
    if (!dlg.open) dlg.showModal();
    $("sceneName").focus();
  }

  form.addEventListener("input", () => { if (!errBox.hidden && !btnSave.disabled) showError(""); });   // bắt đầu sửa thì xóa lỗi cũ
  form.addEventListener("change", () => { if (!errBox.hidden && !btnSave.disabled) showError(""); });
  const close = () => dlg.open && dlg.close();
  btnOpen.addEventListener("click", open);
  dlg.addEventListener("click", (e) => { if (e.target === dlg || e.target.closest("[data-sd-close]")) close(); });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    let scene;
    try { scene = readScene(); } catch (err) {
      if (err instanceof FormError) return showError(err.message);
      throw err;
    }
    if (!app()?.engineOnline()) return showError("Automation engine chưa chạy nên chưa thể thêm kịch bản.");
    const alertList = $("alerts"), marker = alertList.firstElementChild;     // thông báo mới được thêm lên đầu danh sách
    if (!app().send("_auto/scene/set", { add: scene })) return showError("Chưa kết nối broker — không gửi được.");
    showError("");
    btnSave.disabled = true;
    btnSave.textContent = "Đang lưu…";
    // Chờ engine phản hồi: kịch bản mới xuất hiện trong danh sách = thành công; thông báo "Không thêm được…" = bị từ chối
    const started = Date.now();
    const timer = setInterval(() => {
      const added = (app().scenes() || []).some((s) => s.name.toLowerCase() === scene.name.toLowerCase());
      const fresh = [];
      for (let li = alertList.firstElementChild; li && li !== marker; li = li.nextElementSibling) fresh.push(li.textContent);
      const rejected = fresh.find((t) => /Không thêm được kịch bản|Không lưu được kịch bản/.test(t));
      if (added) { clearInterval(timer); close(); return; }
      if (rejected) { clearInterval(timer); btnSave.disabled = false; btnSave.textContent = "Lưu kịch bản"; showError(rejected.replace(/^\d\d:\d\d:\d\d/, "").trim()); return; }
      if (Date.now() - started > 6000) {
        clearInterval(timer); btnSave.disabled = false; btnSave.textContent = "Lưu kịch bản";
        showError("Chưa thấy engine phản hồi. Kiểm tra mục Thông báo hoặc thử lại.");
      }
    }, 150);
  });
})();
