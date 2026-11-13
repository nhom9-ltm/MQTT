/* Phiên đăng nhập ở trình duyệt: lưu token, gọi API và chuyển trang theo vai trò.
 * Lưu trong sessionStorage nên đóng tab là phải đăng nhập lại.
 *
 * Nạp trong <head> với thuộc tính data-guard:
 *   data-guard="user"   trang của người dùng (index.html) — tài khoản admin mở vào sẽ bị đưa về admin.html
 *   data-guard="admin"  trang quản trị (admin.html) — tài khoản user mở vào sẽ bị đưa về index.html
 * Đây chỉ là điều hướng giao diện; quyền thật do API kiểm tra (backend/controllers/auth_controller.py). */
(() => {
  const qs = new URLSearchParams(location.search);
  const guard = document.currentScript && document.currentScript.dataset.guard;
  const store = {
    get: (k) => { try { return sessionStorage.getItem(k); } catch { return null; } },
    set: (k, v) => { try { sessionStorage.setItem(k, v); } catch { /* trình duyệt chặn lưu trữ */ } },
    del: (k) => { try { sessionStorage.removeItem(k); } catch { /* trình duyệt chặn lưu trữ */ } },
  };

  if (qs.get("api")) store.set("sh.api", qs.get("api"));
  const web = location.protocol === "http:" || location.protocol === "https:";
  const apiBase = (store.get("sh.api") || (web ? `${location.protocol}//${location.hostname}:8001` : "http://localhost:8001"))
    .replace(/\/$/, "");

  const token = () => store.get("sh.token");
  const user = () => { try { return JSON.parse(store.get("sh.user")); } catch { return null; } };
  // Người dùng vào bảng điều khiển (kết nối broker thật); quản trị viên vào trang quản trị
  const homeOf = (u) => (u && u.role === "admin" ? "admin.html" : "index.html");

  function save(data) {
    store.set("sh.token", data.token);
    store.set("sh.user", JSON.stringify(data.user));
  }
  function clear() {
    store.del("sh.token");
    store.del("sh.user");
  }
  function toLogin() {
    clear();
    document.documentElement.style.visibility = "hidden";
    location.replace("login.html");
  }

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (token()) headers.Authorization = `Bearer ${token()}`;
    return fetch(apiBase + path, { ...options, headers });
  }

  async function logout() {
    try { await api("/api/auth/logout", { method: "POST" }); } catch { /* API tắt: vẫn xóa phiên ở trình duyệt */ }
    toLogin();
  }

  window.Session = { api, save, clear, token, user, homeOf, logout, toLogin };

  // Bản công khai trên GitHub Pages không có API để đăng nhập nên bỏ qua kiểm tra
  const publicDemo = location.hostname.endsWith("github.io") && !qs.get("broker");
  if (!guard || (guard === "user" && publicDemo)) return;

  if (!token()) { toLogin(); return; }
  // Mỗi vai trò chỉ có MỘT trang: admin → admin.html, user → index.html. Mở nhầm trang thì đưa về đúng trang của mình.
  const home = homeOf(user());
  if (!user() || (guard === "admin") !== (user().role === "admin")) {
    document.documentElement.style.visibility = "hidden";
    if (user()) location.replace(home); else toLogin();
    return;
  }

  // Phiên có thể đã hết hạn ở server. API không phản hồi thì giữ nguyên trang, không đẩy người dùng ra ngoài.
  api("/api/auth/me").then((r) => { if (r.status === 401) toLogin(); }).catch(() => {});

  function renderTopbar() {
    const box = document.getElementById("sessionBox");
    if (!box) return;
    const u = user();
    document.getElementById("sessionEmail").textContent = u ? u.email : "";
    document.getElementById("btnLogout").addEventListener("click", logout);
    box.hidden = false;
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", renderTopbar);
  else renderTopbar();
})();
