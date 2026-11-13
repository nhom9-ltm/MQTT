/* Trang quản trị — Quản lý người dùng: Tài khoản (tìm kiếm, lọc, thêm/sửa/xóa) và Vai trò (admin, user).
 * Ràng buộc an toàn (không tự xóa/khóa/hạ quyền, luôn còn ≥ 1 admin) do server kiểm tra; ở đây chỉ hiện thông báo. */
(() => {
  const { call, esc, toast, fmtTime } = window.Admin;
  const $ = (id) => document.getElementById(id);
  const me = () => (window.Session && Session.user()) || {};

  const svg = (d) => `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const ICON_EDIT = svg('<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>');
  const ICON_TRASH = svg('<path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/>');

  // Đang hoạt động → icon ổ khóa đóng (bấm để khóa); đang khóa → ổ khóa mở (bấm để mở khóa)
  const ICON_LOCK = svg('<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>');
  const ICON_UNLOCK = svg('<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.8-1.2"/>');

  const ICON_SHIELD = svg('<path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"/><path d="M9 12l2 2 4-4"/>');
  const ICON_CHECK = svg('<polyline points="20 6 9 17 4 12"/>');

  let users = [];
  let roles = [];
  let editing = null;            // id tài khoản đang sửa, null = thêm mới

  // ---------------- vai trò ----------------
  async function loadRoles() {
    roles = await call("/api/admin/roles");
    const current = $("userRoleFilter").value;
    $("userRoleFilter").innerHTML = '<option value="">Tất cả</option>' +    // tên vai trò lấy từ API (đổi tên được)
      roles.map((r) => `<option value="${esc(r.code)}">${esc(r.name)}</option>`).join("");
    $("userRoleFilter").value = current;
    return roles;
  }

  function renderRoles() {
    $("rolesNote").textContent = `${roles.length} vai trò`;
    $("rolesBody").innerHTML = roles.map((r) => `<tr>
      <td>${esc(r.name)}</td>
      <td><code>${esc(r.code)}</code></td>
      <td class="num">${esc(r.users_total)}</td>
      <td class="num">${esc(r.users_active)}</td>
      <td class="num">${esc(r.permissions.length)}</td>
      <td><a href="#/accounts" class="text-link" data-show-role="${esc(r.code)}">Xem tài khoản</a></td>
      <td class="actions">
        <button type="button" class="icon-btn" data-perms="${esc(r.code)}" title="Xem quyền" aria-label="Xem quyền của ${esc(r.name)}">${ICON_SHIELD}</button>
        <button type="button" class="icon-btn" data-rename="${esc(r.code)}" title="Đổi tên" aria-label="Đổi tên ${esc(r.name)}">${ICON_EDIT}</button>
      </td></tr>`).join("");
  }

  async function showRoles() {
    try { await loadRoles(); renderRoles(); }
    catch (e) { $("rolesBody").innerHTML = `<tr><td colspan="7" class="muted">${esc(e.message)}</td></tr>`; }
  }

  function showPermissions(role) {
    $("permsTitle").textContent = `Quyền của vai trò “${role.name}”`;
    $("permsCode").textContent = role.code;
    $("permsList").innerHTML = role.permissions.map((p) => `<li>${ICON_CHECK}<span>${esc(p)}</span></li>`).join("");
    $("permsDialog").showModal();
  }

  $("rolesBody").addEventListener("click", (e) => {
    const show = e.target.closest("[data-show-role]");
    if (show) {                         // chuyển sang trang Tài khoản, lọc sẵn theo vai trò
      $("userRoleFilter").value = show.dataset.showRole;
      return;                           // href="#/accounts" lo việc chuyển trang
    }
    const perms = e.target.closest("[data-perms]");
    if (perms) { showPermissions(roles.find((r) => r.code === perms.dataset.perms)); return; }
    const b = e.target.closest("[data-rename]");
    if (!b) return;
    const role = roles.find((r) => r.code === b.dataset.rename);
    $("roleCode").textContent = role.code;
    $("roleName").value = role.name;
    $("roleError").hidden = true;
    $("roleDialog").showModal();
    $("roleName").select();
  });

  $("roleForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const code = $("roleCode").textContent;
    try {
      await call(`/api/admin/roles/${encodeURIComponent(code)}`, "PUT", { name: $("roleName").value.trim() });
      $("roleDialog").close();
      toast("Đã đổi tên vai trò");
      showRoles();
    } catch (err) {
      $("roleError").textContent = err.message;
      $("roleError").hidden = false;
    }
  });

  // ---------------- tài khoản: danh sách ----------------
  function render() {
    const total = users.length;
    $("usersNote").textContent = `${total} tài khoản` + (filtersOn() ? " khớp bộ lọc" : "");
    const myId = me().id;
    $("usersBody").innerHTML = total ? users.map((u) => `<tr class="${u.is_active ? "" : "disabled"}">
      <td>${esc(u.email)}${u.id === myId ? ' <span class="tag idle">Bạn</span>' : ""}</td>
      <td>${esc(u.full_name)}</td>
      <td><span class="tag ${u.role === "admin" ? "warn" : "idle"}">${esc(u.role_name)}</span></td>
      <td><span class="tag ${u.is_active ? "ok" : "bad"}">${u.is_active ? "Hoạt động" : "Khóa"}</span></td>
      <td>${esc(fmtTime(u.created_at))}</td>
      <td>${esc(fmtTime(u.last_login_at))}</td>
      <td class="actions">
        <button type="button" class="icon-btn" data-edit="${u.id}" title="Sửa" aria-label="Sửa ${esc(u.email)}">${ICON_EDIT}</button>
        <button type="button" class="icon-btn ${u.is_active ? "" : "warn"}" data-lock="${u.id}" ${u.id === myId
          ? 'disabled title="Không thể tự khóa tài khoản đang đăng nhập"'
          : `title="${u.is_active ? "Khóa" : "Mở khóa"}" aria-label="${u.is_active ? "Khóa" : "Mở khóa"} ${esc(u.email)}"`}>${u.is_active ? ICON_LOCK : ICON_UNLOCK}</button>
        <button type="button" class="icon-btn danger" data-del="${u.id}" ${u.id === myId
          ? 'disabled title="Không thể xóa tài khoản đang đăng nhập"'
          : `title="Xóa" aria-label="Xóa ${esc(u.email)}"`}>${ICON_TRASH}</button>
      </td></tr>`).join("") : `<tr><td colspan="7" class="muted">${filtersOn() ? "Không có tài khoản nào khớp bộ lọc." : "Chưa có tài khoản."}</td></tr>`;
  }

  const filtersOn = () => !!($("userSearch").value.trim() || $("userRoleFilter").value || $("userStatusFilter").value);

  async function loadUsers() {
    const p = new URLSearchParams();
    if ($("userSearch").value.trim()) p.set("q", $("userSearch").value.trim());
    if ($("userRoleFilter").value) p.set("role", $("userRoleFilter").value);
    if ($("userStatusFilter").value) p.set("status", $("userStatusFilter").value);
    try {
      users = await call("/api/admin/users" + (p.toString() ? "?" + p : ""));
      render();
    } catch (e) {
      $("usersBody").innerHTML = `<tr><td colspan="7" class="muted">${esc(e.message)}</td></tr>`;
    }
  }

  let searchTimer = null;            // gõ tới đâu lọc tới đó, chờ 250ms để không gọi API mỗi phím
  $("userSearch").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadUsers, 250); });
  $("userRoleFilter").addEventListener("change", loadUsers);
  $("userStatusFilter").addEventListener("change", loadUsers);
  $("userFilter").addEventListener("submit", (e) => { e.preventDefault(); loadUsers(); });
  $("btnClearFilter").addEventListener("click", () => {
    $("userSearch").value = ""; $("userRoleFilter").value = ""; $("userStatusFilter").value = "";
    loadUsers();
  });

  // ---------------- tài khoản: form ----------------
  const f = {
    dialog: $("userDialog"), title: $("userTitle"), error: $("userError"), email: $("userEmail"), name: $("userName"),
    role: $("userRole"), active: $("userActive"), password: $("userPassword"), pwLabel: $("userPasswordLabel"),
    hint: $("userHint"),
  };

  const pwToggle = $("btnToggleUserPw");
  function setPwVisible(show) {
    f.password.type = show ? "text" : "password";
    pwToggle.setAttribute("aria-pressed", String(show));
    pwToggle.setAttribute("aria-label", show ? "Ẩn mật khẩu" : "Hiện mật khẩu");
    pwToggle.querySelector(".eye-open").toggleAttribute("hidden", show);
    pwToggle.querySelector(".eye-closed").toggleAttribute("hidden", !show);
  }
  pwToggle.addEventListener("click", () => { setPwVisible(f.password.type === "password"); f.password.focus(); });

  function openForm(user) {
    editing = user ? user.id : null;
    const self = user && user.id === me().id;
    f.title.textContent = user ? `Sửa tài khoản ${user.email}` : "Thêm tài khoản";
    f.error.hidden = true;
    f.role.innerHTML = roles.map((r) => `<option value="${esc(r.code)}">${esc(r.name)}</option>`).join("");
    f.email.value = user?.email || "";
    f.name.value = user?.full_name || "";
    f.role.value = user?.role || "user";
    f.active.value = !user || user.is_active ? "1" : "0";
    f.role.disabled = f.active.disabled = !!self;          // không tự hạ quyền / tự khóa
    f.password.value = "";
    setPwVisible(false);
    f.pwLabel.textContent = user ? "Mật khẩu mới (để trống nếu giữ nguyên)" : "Mật khẩu";
    f.hint.textContent = self
      ? "Đây là tài khoản bạn đang đăng nhập: không đổi được vai trò và trạng thái."
      : "Mật khẩu ít nhất 6 ký tự. Email phải là @gmail.com. Đổi mật khẩu hoặc khóa sẽ đăng xuất người đó.";
    f.dialog.showModal();
    (user ? f.name : f.email).focus();
  }

  $("userForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = { email: f.email.value.trim(), full_name: f.name.value.trim(), role: f.role.value,
                   is_active: f.active.value === "1" };
    if (f.password.value) body.password = f.password.value;
    $("userSubmit").disabled = true;
    try {
      if (editing) await call(`/api/admin/users/${editing}`, "PUT", body);
      else await call("/api/admin/users", "POST", body);
      f.dialog.close();
      toast(editing ? `Đã lưu ${body.email}` : `Đã tạo tài khoản ${body.email}`);
      loadUsers();
    } catch (err) {
      f.error.textContent = err.message;
      f.error.hidden = false;
    }
    $("userSubmit").disabled = false;
  });

  $("btnAddUser").addEventListener("click", () => openForm(null));

  $("usersBody").addEventListener("click", async (e) => {
    const edit = e.target.closest("[data-edit]");
    const del = e.target.closest("[data-del]");
    const lock = e.target.closest("[data-lock]");
    if (edit) openForm(users.find((u) => u.id === Number(edit.dataset.edit)));
    if (lock) {
      const u = users.find((x) => x.id === Number(lock.dataset.lock));
      const active = !u.is_active;
      const ok = await Admin.confirm(active
        ? { title: "Mở khóa tài khoản", ok: "Mở khóa",
            message: `Mở khóa ${u.email}? Người này sẽ đăng nhập lại được.` }
        : { title: "Khóa tài khoản", kind: "warn", ok: "Khóa",
            message: `Khóa ${u.email}? Người này bị đăng xuất ngay và không đăng nhập được cho tới khi được mở khóa.` });
      if (!ok) return;
      try {
        await call(`/api/admin/users/${u.id}/active`, "PUT", { is_active: active });
        toast(active ? `Đã mở khóa ${u.email}` : `Đã khóa ${u.email}`);
        loadUsers();
      } catch (err) {
        toast(err.message, "bad");
      }
    }
    if (del) {
      const u = users.find((x) => x.id === Number(del.dataset.del));
      if (!u || !(await Admin.confirm({ title: "Xóa tài khoản", kind: "danger", ok: "Xóa",
        message: `Xóa ${u.email} khỏi hệ thống? Người này sẽ không đăng nhập được nữa. Nếu chỉ muốn tạm chặn, hãy dùng nút khóa.` }))) return;
      try {
        await call(`/api/admin/users/${u.id}`, "DELETE");
        toast(`Đã xóa ${u.email}`);
        loadUsers();
      } catch (err) {
        toast(err.message, "bad");
      }
    }
  });

  document.addEventListener("admin:page", async (e) => {
    if (e.detail === "accounts") {
      try { await loadRoles(); } catch { /* lỗi sẽ hiện ở bảng khi tải tài khoản */ }
      loadUsers();
    }
    if (e.detail === "roles") showRoles();
  });
})();
