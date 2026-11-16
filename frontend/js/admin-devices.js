/* Trang quản trị — Quản lý thiết bị.
 *   #/devices        danh sách: tìm kiếm, lọc (phòng, loại, nguồn, trạng thái), khóa/mở khóa, xóa, thêm mới
 *   #/devices/<id>   trang chi tiết: xem thông tin → "Cập nhật" để sửa toàn bộ, "Hủy" để quay lại danh sách
 * Viền đầu dòng: tím nhạt = thiết bị giả lập, cam = thiết bị thật.
 * Khóa thiết bị: automation bỏ qua và dashboard người dùng chặn điều khiển (API phát home/_admin/locked/state). */
(() => {
  const { call, esc, toast, fmtTime, live, liveState, PREFIX } = window.Admin;
  const $ = (id) => document.getElementById(id);

  const svg = (d) => `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const ICON_SHIELD = svg('<path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"/><path d="M9 12l2 2 4-4"/>');
  const ICON_LOCK = svg('<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>');
  const ICON_UNLOCK = svg('<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.8-1.2"/>');
  const ICON_TRASH = svg('<path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/>');
  const LIVE_TAG = {
    online: '<span class="tag ok">Online</span>',
    offline: '<span class="tag bad">Offline</span>',
    unknown: '<span class="tag idle">Chưa thấy trên broker</span>',
  };
  const statusTag = (d) => `<span class="tag ${d.is_active ? "ok" : "bad"}">${d.is_active ? "Hoạt động" : "Khóa"}</span>`;

  let devices = [];              // thiết bị đã đăng ký (API)
  let options = { rooms: [], types: [] };
  let detail = null;             // thiết bị đang xem ở trang chi tiết

  // =========================================================
  //  DANH SÁCH
  // =========================================================
  const F = { q: $("devSearch"), house: $("devHouseFilter"), room: $("devRoomFilter"), type: $("devTypeFilter"),
              source: $("devSourceFilter"), status: $("devStatusFilter") };
  const filtersOn = () => Object.values(F).some((x) => x.value.trim());

  function fillSelect(sel, items) {
    const current = sel.value;
    sel.innerHTML = '<option value="">Tất cả</option>' +
      items.map((x) => `<option value="${esc(x.code)}">${esc(x.name)}</option>`).join("");
    sel.value = current;
  }

  function filtered() {
    const q = F.q.value.trim().toLowerCase();
    return devices.filter((d) =>
      (!q || d.code.toLowerCase().includes(q) || d.name.toLowerCase().includes(q) || d.key.includes(q)) &&
      Admin.houseMatches(d.house_id, F.house.value) &&
      (!F.room.value || d.room === F.room.value) &&
      (!F.type.value || d.type === F.type.value) &&
      (!F.source.value || (F.source.value === "sim") === d.is_simulated) &&
      (!F.status.value || (F.status.value === "active") === d.is_active));
  }

  function renderList() {
    const rows = filtered();
    $("devicesNote").textContent = `${rows.length} thiết bị` + (filtersOn() ? " khớp bộ lọc" : "") + " ·";
    $("devicesBody").innerHTML = rows.length ? rows.map((d) => `<tr class="src-row ${d.is_simulated ? "sim" : "real"} ${d.is_active ? "" : "disabled"}">
      <td><code>${esc(d.code)}</code><small>${esc(PREFIX)}/${esc(d.key)}</small></td>
      <td>${esc(d.name)}</td>
      <td class="wrap addr">${Admin.houseCell(d.house_id)}</td>
      <td>${esc(d.room_name)}</td>
      <td>${esc(d.type_name)}</td>
      <td>${statusTag(d)}</td>
      <td class="actions">
        <button type="button" class="icon-btn" data-detail="${d.id}" title="Xem chi tiết" aria-label="Xem chi tiết ${esc(d.key)}">${ICON_SHIELD}</button>
        <button type="button" class="icon-btn ${d.is_active ? "" : "warn"}" data-lock="${d.id}" title="${d.is_active ? "Khóa" : "Mở khóa"}"
          aria-label="${d.is_active ? "Khóa" : "Mở khóa"} ${esc(d.key)}">${d.is_active ? ICON_LOCK : ICON_UNLOCK}</button>
        <button type="button" class="icon-btn danger" data-del="${d.id}" title="Xóa" aria-label="Xóa ${esc(d.key)}">${ICON_TRASH}</button>
      </td></tr>`).join("")
      : `<tr><td colspan="7" class="muted">${filtersOn() ? "Không có thiết bị nào khớp bộ lọc." : "Chưa có thiết bị nào."}</td></tr>`;
    renderUnknown();
  }

  /* Thiết bị đã gửi status lên broker nhưng chưa đăng ký (ví dụ ESP32 mới). */
  function renderUnknown() {
    const known = new Set(devices.map((d) => d.key));
    const unknown = [...live.entries()].filter(([k]) => !known.has(k)).sort(([a], [b]) => a.localeCompare(b));
    $("unknownPanel").hidden = !unknown.length || !!detail;
    $("unknownBody").innerHTML = unknown.map(([k, s]) => `<tr>
      <td><code>${esc(PREFIX)}/${esc(k)}</code></td>
      <td>${esc(s.name || "")}</td>
      <td>${esc(s.type || "")}</td>
      <td class="actions"><button type="button" class="btn sm primary" data-register="${esc(k)}">Đăng ký</button></td></tr>`).join("");
  }

  async function loadAll() {
    [devices, options] = await Promise.all([call("/api/admin/devices"), call("/api/admin/device-options"), Admin.loadHouses()]);
    Admin.setBadge("devices", devices.length);
    fillSelect(F.room, options.rooms);
    fillSelect(F.type, options.types);
  }

  let searchTimer = null;
  [F.q, F.house].forEach((x) => x.addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(renderList, 150); }));
  [F.room, F.type, F.source, F.status].forEach((s) => s.addEventListener("change", renderList));
  $("deviceFilter").addEventListener("submit", (e) => { e.preventDefault(); renderList(); });
  $("btnClearDeviceFilter").addEventListener("click", () => {
    Object.values(F).forEach((x) => (x.value = ""));
    renderList();
  });

  async function toggleLock(d) {
    const active = !d.is_active;
    const ok = await Admin.confirm(active
      ? { title: "Mở khóa thiết bị", ok: "Mở khóa",
          message: `Mở khóa “${d.name}” (${d.key})? Automation và người dùng sẽ điều khiển được thiết bị này trở lại.` }
      : { title: "Khóa thiết bị", kind: "warn", ok: "Khóa",
          message: `Khóa “${d.name}” (${d.key})? Automation sẽ bỏ qua thiết bị này và người dùng không điều khiển được nữa.` });
    if (!ok) return false;
    try {
      await call(`/api/admin/devices/${d.id}/active`, "PUT", { is_active: active });
      toast(active ? `Đã mở khóa ${d.key}` : `Đã khóa ${d.key}`);
      return true;
    } catch (err) {
      toast(err.message, "bad");
      return false;
    }
  }

  async function remove(d) {
    const ok = await Admin.confirm({ title: "Xóa thiết bị", kind: "danger", ok: "Xóa",
      message: `Xóa “${d.name}” (${d.key}) khỏi danh sách đã đăng ký?` });
    if (!ok) return false;
    try {
      await call(`/api/admin/devices/${d.id}`, "DELETE");
      toast(`Đã xóa ${d.key}`);
      return true;
    } catch (err) {
      toast(err.message, "bad");
      return false;
    }
  }

  $("deviceListPanel").addEventListener("click", async (e) => {
    const det = e.target.closest("[data-detail]");
    const lock = e.target.closest("[data-lock]");
    const del = e.target.closest("[data-del]");
    const find = (b, attr) => devices.find((d) => d.id === Number(b.dataset[attr]));
    if (det) location.hash = `#/devices/${det.dataset.detail}`;
    if (lock && await toggleLock(find(lock, "lock"))) { await loadAll(); renderList(); }
    if (del && await remove(find(del, "del"))) { await loadAll(); renderList(); }
  });

  // ---------------- thêm mới / đăng ký (hộp thoại) ----------------
  const form = {
    dialog: $("deviceDialog"), title: $("deviceTitle"), error: $("deviceError"), room: $("devRoom"),
    code: $("devCode"), name: $("devName"), type: $("devType"), source: $("devSource"), topic: $("devTopic"),
  };
  const roomOptions = () => options.rooms.map((r) => `<option value="${esc(r.code)}">${esc(r.name)} (${esc(r.code)})</option>`).join("");
  const typeOptions = () => options.types.map((t) => `<option value="${esc(t.code)}">${esc(t.name)} (${esc(t.code)})</option>`).join("");

  function updateTopic() {
    form.topic.textContent = `${PREFIX}/${form.room.value || "…"}/${form.code.value.trim() || "…"}/status`;
  }
  form.room.addEventListener("change", updateTopic);
  form.code.addEventListener("input", updateTopic);

  function openAdd(preset = {}) {
    form.title.textContent = preset.code ? `Đăng ký ${preset.room}/${preset.code}` : "Thêm thiết bị";
    form.error.hidden = true;
    form.room.innerHTML = roomOptions();
    form.type.innerHTML = typeOptions();
    Admin.fillHouseSelect($("devHouse"));
    form.room.value = preset.room || F.room.value || options.rooms[0]?.code || "";
    form.code.value = preset.code || "";
    form.name.value = preset.name || "";
    form.type.value = preset.type || F.type.value || options.types[0]?.code || "";
    form.source.value = preset.sim ? "sim" : "real";
    updateTopic();
    form.dialog.showModal();
    (preset.code ? form.name : form.code).focus();
  }

  $("deviceForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = { room: form.room.value, code: form.code.value.trim(), name: form.name.value.trim(),
                   type: form.type.value, is_simulated: form.source.value === "sim", ...Admin.readHouse($("devHouse")) };
    $("deviceSubmit").disabled = true;
    try {
      await call("/api/admin/devices", "POST", body);
      form.dialog.close();
      toast(`Đã đăng ký ${body.room}/${body.code}`);
      await loadAll();
      renderList();
    } catch (err) {
      form.error.textContent = err.message;
      form.error.hidden = false;
    }
    $("deviceSubmit").disabled = false;
  });

  $("btnAddDevice").addEventListener("click", () => openAdd());

  $("unknownPanel").addEventListener("click", (e) => {
    const reg = e.target.closest("[data-register]");
    if (!reg) return;
    const key = reg.dataset.register;
    const [r, code] = key.split("/");
    const s = live.get(key) || {};
    if (!options.rooms.some((x) => x.code === r)) {
      toast(`Phòng “${r}” chưa có trong hệ thống — không đăng ký được`, "bad");
      return;
    }
    openAdd({ room: r, code, name: s.name || code, type: options.types.some((t) => t.code === s.type) ? s.type : "", sim: !!s.sim });
  });

  // =========================================================
  //  TRANG CHI TIẾT
  // =========================================================
  const E = { code: $("deCode"), name: $("deName"), type: $("deType"), room: $("deRoom"), source: $("deSource"),
              status: $("deStatus"), topic: $("deTopic") };

  function showDetailError(msg) {
    $("detailError").textContent = msg;
    $("detailError").hidden = !msg;
  }

  function renderDetail() {
    const d = detail;
    $("detailTitle").textContent = d.name;
    $("detailSub").textContent = `Thiết bị #${d.id} · ${d.is_simulated ? "Giả lập" : "Thiết bị thật"}`;
    $("deviceDetail").classList.toggle("sim", d.is_simulated);
    $("deviceDetail").classList.toggle("real", !d.is_simulated);
    $("dvCode").textContent = d.code;
    $("dvName").textContent = d.name;
    $("dvType").textContent = `${d.type_name} (${d.type})`;
    $("dvRoom").textContent = `${d.room_name} (${d.room})`;
    $("dvHouse").textContent = Admin.houseLabel(d.house_id);
    const cu = d.connected_users || [];
    $("dvUsers").innerHTML = cu.length
      ? cu.map((u) => `${esc(u.full_name)} · ${esc(u.email)} <span class="muted">(${esc(fmtTime(u.connected_at))})</span>`).join("<br>")
      : '<span class="muted">Chưa có người dùng nào nhập mã kết nối thiết bị này</span>';
    $("dvTopic").textContent = `${PREFIX}/${d.key}`;
    $("dvSource").textContent = d.is_simulated ? "Giả lập (run_simulator.py)" : "Thiết bị thật (ESP32…)";
    $("dvCreator").textContent = d.created_by ? `#${d.created_by} · ${d.created_by_email || "tài khoản đã xóa"}` : "Hệ thống (dữ liệu seed)";
    $("dvCreated").textContent = d.created_by ? fmtTime(d.created_at) : "—";          // thiết bị seed: không có ngày thêm thật
    $("dvStatus").innerHTML = statusTag(d);
    $("dvLive").innerHTML = LIVE_TAG[liveState(d.key)];
    Admin.setCrumb(`Thiết bị / ${d.key}`);
  }

  function setEditing(on) {
    $("detailView").hidden = on;
    $("detailForm").hidden = !on;
    showDetailError("");
    if (!on) return;
    const d = detail;
    E.room.innerHTML = roomOptions();
    E.type.innerHTML = typeOptions();
    E.code.value = d.code;
    E.name.value = d.name;
    E.type.value = d.type;
    E.room.value = d.room;
    Admin.fillHouseSelect($("deHouse"), { selected: d.house_id });
    E.source.value = d.is_simulated ? "sim" : "real";
    E.status.value = d.is_active ? "1" : "0";
    updateEditTopic();
    E.name.focus();
  }
  function updateEditTopic() { E.topic.textContent = `${PREFIX}/${E.room.value}/${E.code.value.trim() || "…"}`; }
  E.room.addEventListener("change", updateEditTopic);
  E.code.addEventListener("input", updateEditTopic);

  async function openDetail(id) {
    $("deviceListPanel").hidden = true;
    $("unknownPanel").hidden = true;
    $("deviceDetail").hidden = false;
    $("detailView").hidden = false;
    $("detailForm").hidden = true;
    showDetailError("");
    try {
      await loadAll();
      detail = await call(`/api/admin/devices/${id}`);
      renderDetail();
    } catch (err) {
      detail = null;
      $("detailTitle").textContent = "Không mở được thiết bị";
      $("detailSub").textContent = "";
      showDetailError(err.message);
    }
  }

  function closeDetail() {
    detail = null;
    $("deviceDetail").hidden = true;
    $("deviceListPanel").hidden = false;
  }

  $("btnDetailCancel").addEventListener("click", () => { location.hash = "#/devices"; });
  $("btnDetailEdit").addEventListener("click", () => detail && setEditing(true));
  $("btnEditCancel").addEventListener("click", () => setEditing(false));

  $("detailForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = { code: E.code.value.trim(), name: E.name.value.trim(), type: E.type.value, room: E.room.value,
                   is_simulated: E.source.value === "sim", is_active: E.status.value === "1", ...Admin.readHouse($("deHouse")) };
    $("btnEditSave").disabled = true;
    try {
      await call(`/api/admin/devices/${detail.id}`, "PUT", body);
      detail = await call(`/api/admin/devices/${detail.id}`);              // tải lại kèm người dùng đã kết nối
      toast(`Đã cập nhật ${detail.key}`);
      setEditing(false);
      renderDetail();
    } catch (err) {
      showDetailError(err.message);
    }
    $("btnEditSave").disabled = false;
  });

  // =========================================================
  //  ĐIỀU HƯỚNG & TRẠNG THÁI BROKER
  // =========================================================
  document.addEventListener("admin:route", async (e) => {
    const { page, sub } = e.detail;
    if (page !== "devices") return;
    if (sub) { openDetail(Number(sub)); return; }
    closeDetail();
    try { await loadAll(); renderList(); }
    catch (err) { $("devicesBody").innerHTML = `<tr><td colspan="7" class="muted">${esc(err.message)}</td></tr>`; }
  });

  let timer = null;              // status tới dồn dập lúc mới kết nối → gom lại vẽ 1 lần
  document.addEventListener("admin:status", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (Admin.page() !== "devices") return;
      if (detail) $("dvLive").innerHTML = LIVE_TAG[liveState(detail.key)];
      else renderUnknown();
    }, 200);
  });
})();
