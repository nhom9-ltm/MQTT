/* Trang quản trị — Lịch sử đăng nhập (chỉ xem). Tải lại mỗi lần mở trang. */
(() => {
  const { call, esc, fmtTime } = window.Admin;
  const $ = (id) => document.getElementById(id);

  async function load() {
    try {
      const rows = await call("/api/admin/login-history?limit=100");
      $("loginsNote").textContent = `${rows.length} lượt gần nhất`;
      $("loginsBody").innerHTML = rows.length ? rows.map((l) => `<tr>
        <td>${esc(fmtTime(l.created_at))}</td><td>${esc(l.email)}</td>
        <td><span class="tag ${l.success ? "ok" : "bad"}">${l.success ? "Thành công" : "Thất bại"}</span></td>
        <td>${esc(l.ip_address)}</td></tr>`).join("") : '<tr><td colspan="4" class="muted">Chưa có lượt đăng nhập</td></tr>';
    } catch (e) {
      $("loginsBody").innerHTML = `<tr><td colspan="4" class="muted">${esc(e.message)}</td></tr>`;
    }
  }

  document.addEventListener("admin:page", (e) => { if (e.detail === "logins") load(); });
})();
