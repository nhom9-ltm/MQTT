/* Phiên đăng nhập ở trình duyệt: lưu token, gọi API và chuyển trang theo vai trò.
 * Lưu trong sessionStorage nên đóng tab là phải đăng nhập lại.
 *
 * Nạp trong <head> với thuộc tính data-guard:
 *   data-guard="user"   trang của người dùng (index.html) — tài khoản admin mở vào sẽ bị đưa về admin.html
 *   data-guard="admin"  trang quản trị (admin.html) — tài khoản user mở vào sẽ bị đưa về index.html
 * Đây chỉ là điều hướng giao diện; quyền thật do API kiểm tra (backend/controllers/auth_controller.py).
 *
 * Địa chỉ broker (dùng chung cho index.html và admin.html qua Session.brokerUrl()):
 *   ?broker=wss://...  chỉ định hẳn địa chỉ
 *   ?tls=1             kết nối mã hóa wss://<máy>:8443 (xem docs/TLS.md); ?tls=0 quay lại ws://<máy>:9001.
 *                      Lựa chọn được nhớ trong localStorage nên mở tab mới / đăng nhập lại vẫn giữ. */
(() => {
  const qs = new URLSearchParams(location.search);
  try {
    if (qs.has("tls")) localStorage.setItem("sh.tls", qs.get("tls") === "1" ? "1" : "0");
  } catch { /* trình duyệt chặn lưu trữ */ }
  function brokerTls() {
    if (location.protocol === "https:") return true;      // trang https chỉ được mở wss://
    try { return localStorage.getItem("sh.tls") === "1"; } catch { return false; }
  }
  function brokerUrl() {
    if (qs.get("broker")) return qs.get("broker");
    const host = location.hostname || "localhost";
    return brokerTls() ? `wss://${host}:8443` : `ws://${host}:9001`;
  }
  const guard = document.currentScript && document.currentScript.dataset.guard;
  const store = {
    get: (k) => { try { return sessionStorage.getItem(k); } catch { return null; } },
    set: (k, v) => { try { sessionStorage.setItem(k, v); } catch { /* trình duyệt chặn lưu trữ */ } },
    del: (k) => { try { sessionStorage.removeItem(k); } catch { /* trình duyệt chặn lưu trữ */ } },
  };

  if (qs.get("api")) store.set("sh.api", qs.get("api"));
  // Bản công khai trên GitHub Pages: không có broker và API riêng -> giả lập cả hai trong trình duyệt
  const publicDemo = location.hostname.endsWith("github.io") && !qs.get("broker");
  // API giả lập (mock/api.js): mặc định bật trên GitHub Pages; ?mockapi=1 / ?mockapi=0 để bật / tắt khi thử trên máy
  if (qs.has("mockapi")) store.set("sh.mockapi", qs.get("mockapi") === "1" ? "1" : "0");
  const mock = !!window.MockApi && (store.get("sh.mockapi") ? store.get("sh.mockapi") === "1" : publicDemo);
  const web = location.protocol === "http:" || location.protocol === "https:";
  const apiBase = (store.get("sh.api") || (web ? `${location.protocol}//${location.hostname}:8011` : "http://localhost:8011"))
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
    if (mock) return window.MockApi.fetch(path, { ...options, headers });
    return fetch(apiBase + path, { ...options, headers });
  }

  async function logout() {
    try { await api("/api/auth/logout", { method: "POST" }); } catch { /* API tắt: vẫn xóa phiên ở trình duyệt */ }
    toLogin();
  }

  window.Session = { api, save, clear, token, user, homeOf, logout, toLogin, brokerUrl, mock, publicDemo };

  const onReady = (fn) => (document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", fn) : fn());
  if (!guard) return;
  // Bản công khai: ai mở link cũng xem được bảng điều khiển (chế độ Demo), không bắt đăng nhập.
  // Đã đăng nhập (API giả lập) thì vẫn hiện email + nút Đăng xuất; chưa thì hiện nút Đăng nhập.
  if (guard === "user" && publicDemo) {
    const u = token() && user();
    if (u && u.role === "admin") { document.documentElement.style.visibility = "hidden"; location.replace("admin.html"); return; }
    onReady(() => renderTopbar(!!u));
    return;
  }

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

  function renderTopbar(loggedIn = true) {
    const box = document.getElementById("sessionBox");
    if (!box) return;
    const u = loggedIn ? user() : null;
    const btn = document.getElementById("btnLogout");
    document.getElementById("sessionEmail").textContent = u ? u.email : "Khách (demo)";
    if (u) btn.addEventListener("click", logout);
    else {
      btn.textContent = "Đăng nhập";
      btn.addEventListener("click", () => location.assign("login.html"));
    }
    box.hidden = false;
  }
  onReady(() => renderTopbar());
})();
