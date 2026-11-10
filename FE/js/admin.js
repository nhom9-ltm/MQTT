/* Trang quản trị: đọc số liệu từ /api/admin/* và hiển thị. */
(() => {
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtTime = (t) => (t ? new Date(t).toLocaleString("vi-VN") : "Chưa có");

  function setStatus(kind, text) {
    $("adminPill").className = "pill sm " + kind;
    $("adminPill").querySelector("span").textContent = text;
  }

  async function get(path) {
    const r = await Session.api(path);
    if (r.status === 401) { Session.toLogin(); throw new Error("Hết phiên đăng nhập"); }
    if (r.status === 403) { location.replace("index.html"); throw new Error("Không có quyền"); }
    if (r.status === 503) throw new Error("Database chưa sẵn sàng");
    if (!r.ok) throw new Error(`API trả lỗi ${r.status}`);
    return r.json();
  }

  function renderKpis(o) {
    const items = [
      ["Tài khoản", o.users_total, `${o.users_admin} quản trị viên`],
      ["Thiết bị", o.devices_total, `${o.devices_simulated} giả lập · ${o.devices_total - o.devices_simulated} ESP32`],
      ["Phòng", o.rooms_total, "Khu vực trong nhà"],
      ["Luật tự động", o.rules_total, `${o.scenes_total} kịch bản`],
      ["Phiên đang mở", o.sessions_active, "Chưa hết hạn"],
      ["Đăng nhập 24 giờ", o.logins_ok_24h, `${o.logins_failed_24h} lần thất bại`],
    ];
    $("adminKpis").innerHTML = items.map(([label, value, note]) =>
      `<div class="kpi"><span class="k-label">${esc(label)}</span><span class="k-val">${esc(value)}</span><span class="muted">${esc(note)}</span></div>`).join("");
  }

  function renderUsers(rows) {
    $("usersBody").innerHTML = rows.map((u) => `<tr>
      <td>${esc(u.email)}</td><td>${esc(u.full_name)}</td><td>${esc(u.role_name)}</td>
      <td><span class="tag ${u.is_active ? "ok" : "bad"}">${u.is_active ? "Hoạt động" : "Đã khóa"}</span></td>
      <td>${esc(fmtTime(u.last_login_at))}</td></tr>`).join("");
  }

  function renderRooms(rows) {
    $("roomsBody").innerHTML = rows.map((r) => `<tr>
      <td>${esc(r.name)}</td><td><code>${esc(r.code)}</code></td>
      <td class="num">${esc(r.total)}</td><td class="num">${esc(r.simulated)}</td></tr>`).join("");
  }

  function renderLogins(rows) {
    $("loginsBody").innerHTML = rows.length ? rows.map((l) => `<tr>
      <td>${esc(fmtTime(l.created_at))}</td><td>${esc(l.email)}</td>
      <td><span class="tag ${l.success ? "ok" : "bad"}">${l.success ? "Thành công" : "Thất bại"}</span></td>
      <td>${esc(l.ip_address)}</td></tr>`).join("") : '<tr><td colspan="4" class="muted">Chưa có lượt đăng nhập</td></tr>';
  }

  async function load() {
    setStatus("wait", "Đang tải");
    try {
      const [overview, users, rooms, logins] = await Promise.all([
        get("/api/admin/overview"), get("/api/admin/users"), get("/api/admin/devices-by-room"), get("/api/admin/login-history?limit=20"),
      ]);
      renderKpis(overview);
      renderUsers(users);
      renderRooms(rooms);
      renderLogins(logins);
      setStatus("on", "Đã cập nhật");
    } catch (e) {
      setStatus("off", e instanceof TypeError ? "Không kết nối được API" : e.message);
    }
  }

  $("btnRefresh").addEventListener("click", load);
  load();
})();
