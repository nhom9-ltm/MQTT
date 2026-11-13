/* Trang quản trị — Thiết bị: thêm / sửa / xóa thiết bị đã đăng ký (API), lọc theo phòng,
 * trạng thái thật trên broker (Admin.live do admin.js cập nhật). Thiết bị gửi status mà chưa đăng ký
 * hiện ở bảng riêng để quản trị viên bấm đăng ký. */
(() => {
  const { call, esc, toast, live, liveState, PREFIX } = window.Admin;
  const $ = (id) => document.getElementById(id);

  let devices = [];              // thiết bị đã đăng ký (API)
  let options = { rooms: [], types: [] };
  let room = "all";              // phòng đang lọc
  let editing = null;            // id thiết bị đang sửa, null = thêm mới
  let loaded = false;

  const STATE_TAG = {
    online: '<span class="tag ok">Online</span>',
    offline: '<span class="tag bad">Offline</span>',
    unknown: '<span class="tag idle">Chưa thấy</span>',
  };

  // ---------------- bảng ----------------
  function renderFilter() {
    const count = (code) => devices.filter((d) => code === "all" || d.room === code).length;
    const items = [{ code: "all", name: "Tất cả" }, ...options.rooms];
    $("roomFilter").innerHTML = items.map((r) =>
      `<button type="button" data-room="${esc(r.code)}" class="${r.code === room ? "on" : ""}">${esc(r.name)} <b>${count(r.code)}</b></button>`).join("");
  }

  function render() {
    if (!loaded || Admin.page() !== "devices") return;
    const shown = devices.filter((d) => room === "all" || d.room === room);
    $("devicesBody").innerHTML = shown.length ? shown.map((d) => `<tr>
      <td>${STATE_TAG[liveState(d.key)]}</td>
      <td>${esc(d.room_name)}</td>
      <td><code>${esc(PREFIX)}/${esc(d.key)}</code></td>
      <td>${esc(d.name)}</td>
      <td>${esc(d.type_name)}</td>
      <td>${d.is_simulated ? "Giả lập" : "Thiết bị thật"}</td>
      <td class="actions">
        <button type="button" class="btn sm" data-edit="${d.id}">Sửa</button>
        <button type="button" class="btn sm danger" data-del="${d.id}">Xóa</button>
      </td></tr>`).join("") : '<tr><td colspan="7" class="muted">Chưa có thiết bị nào.</td></tr>';

    const known = new Set(devices.map((d) => d.key));
    const unknown = [...live.entries()].filter(([k]) => !known.has(k)).sort(([a], [b]) => a.localeCompare(b));
    $("unknownPanel").hidden = !unknown.length;
    $("unknownBody").innerHTML = unknown.map(([k, s]) => `<tr>
      <td><code>${esc(PREFIX)}/${esc(k)}</code></td>
      <td>${esc(s.name || "")}</td>
      <td>${esc(s.type || "")}</td>
      <td class="actions"><button type="button" class="btn sm primary" data-register="${esc(k)}">Đăng ký</button></td></tr>`).join("");
  }

  async function load() {
    try {
      [devices, options] = await Promise.all([call("/api/admin/devices"), call("/api/admin/device-options")]);
      loaded = true;
      Admin.setBadge("devices", devices.length);
      renderFilter();
      render();
    } catch (e) {
      $("devicesBody").innerHTML = `<tr><td colspan="7" class="muted">${esc(e.message)}</td></tr>`;
    }
  }

  $("roomFilter").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-room]");
    if (!b) return;
    room = b.dataset.room;
    renderFilter();
    render();
  });

  // ---------------- form ----------------
  const form = {
    dialog: $("deviceDialog"), title: $("deviceTitle"), error: $("deviceError"), room: $("devRoom"),
    code: $("devCode"), name: $("devName"), type: $("devType"), source: $("devSource"), topic: $("devTopic"),
  };

  function updateTopic() {
    form.topic.textContent = `${PREFIX}/${form.room.value || "…"}/${form.code.value.trim() || "…"}/status`;
  }
  form.room.addEventListener("change", updateTopic);
  form.code.addEventListener("input", updateTopic);

  function openForm(dev, preset = {}) {
    editing = dev ? dev.id : null;
    form.title.textContent = dev ? `Sửa thiết bị ${dev.key}` : "Thêm thiết bị";
    form.error.hidden = true;
    form.room.innerHTML = options.rooms.map((r) => `<option value="${esc(r.code)}">${esc(r.name)} (${esc(r.code)})</option>`).join("");
    form.type.innerHTML = options.types.map((t) => `<option value="${esc(t.code)}">${esc(t.name)} (${esc(t.code)})</option>`).join("");
    const v = dev ? { room: dev.room, code: dev.code, name: dev.name, type: dev.type, sim: dev.is_simulated }
                  : { room: room !== "all" ? room : "", ...preset };
    form.room.value = v.room || options.rooms[0]?.code || "";
    form.code.value = v.code || "";
    form.name.value = v.name || "";
    form.type.value = v.type || options.types[0]?.code || "";
    form.source.value = v.sim ? "sim" : "real";
    updateTopic();
    form.dialog.showModal();
    (dev ? form.name : form.code).focus();
  }

  $("deviceForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = { room: form.room.value, code: form.code.value.trim(), name: form.name.value.trim(),
                   type: form.type.value, is_simulated: form.source.value === "sim" };
    $("deviceSubmit").disabled = true;
    try {
      if (editing) await call(`/api/admin/devices/${editing}`, "PUT", body);
      else await call("/api/admin/devices", "POST", body);
      form.dialog.close();
      toast(editing ? "Đã lưu thiết bị" : `Đã đăng ký ${body.room}/${body.code}`);
      await load();
    } catch (err) {
      form.error.textContent = err.message;
      form.error.hidden = false;
    }
    $("deviceSubmit").disabled = false;
  });

  $("btnAddDevice").addEventListener("click", () => openForm(null));

  $("admin-devices").addEventListener("click", async (e) => {
    const edit = e.target.closest("[data-edit]");
    const del = e.target.closest("[data-del]");
    const reg = e.target.closest("[data-register]");
    if (edit) openForm(devices.find((d) => d.id === Number(edit.dataset.edit)));
    if (reg) {
      const key = reg.dataset.register;
      const [r, code] = key.split("/");
      const s = live.get(key) || {};
      if (!options.rooms.some((x) => x.code === r)) {
        toast(`Phòng “${r}” chưa có trong hệ thống — không đăng ký được`, "bad");
        return;
      }
      openForm(null, { room: r, code, name: s.name || code,
                       type: options.types.some((t) => t.code === s.type) ? s.type : "", sim: !!s.sim });
    }
    if (del) {
      const dev = devices.find((d) => d.id === Number(del.dataset.del));
      if (!dev || !(await Admin.confirm({ title: "Xóa thiết bị", kind: "danger", ok: "Xóa",
        message: `Xóa thiết bị “${dev.name}” (${dev.key}) khỏi danh sách đã đăng ký?` }))) return;
      try {
        await call(`/api/admin/devices/${dev.id}`, "DELETE");
        toast(`Đã xóa ${dev.key}`);
        await load();
      } catch (err) {
        toast(err.message, "bad");
      }
    }
  });

  // Status từ broker tới dồn dập lúc mới kết nối → gom lại vẽ 1 lần
  let timer = null;
  document.addEventListener("admin:status", () => { clearTimeout(timer); timer = setTimeout(render, 200); });
  document.addEventListener("admin:page", (e) => { if (e.detail === "devices") load(); });
})();
