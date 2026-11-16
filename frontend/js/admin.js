/* Trang quản trị — phần lõi: sidebar + điều hướng theo #hash (cùng kiểu trang người dùng), gọi API,
 * kết nối broker dùng chung, thông báo nổi. Các file admin-*.js dùng lại qua window.Admin.
 *
 * Sự kiện phát trên document:
 *   admin:page    detail = mã trang vừa mở (home, devices, rules, alerts, accounts, logins)
 *   admin:status  một thiết bị vừa gửi status (Admin.live đã cập nhật)
 *   admin:notify  detail = {level, text, source, ts} thông báo trực tiếp từ automation */
(() => {
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtTime = (t) => (t ? new Date(t).toLocaleString("vi-VN") : "Chưa có");
  const emit = (name, detail) => document.dispatchEvent(new CustomEvent(name, { detail }));
  const store = {
    get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* trình duyệt chặn lưu trữ */ } },
  };

  // ---------------- tiện ích ----------------
  function toast(text, kind = "ok") {
    const t = document.createElement("div");
    t.className = "toast " + kind;
    t.textContent = text;
    $("toasts").append(t);
    setTimeout(() => t.classList.add("out"), 4000);
    setTimeout(() => t.remove(), 4600);
  }

  /* Gọi API; lỗi nghiệp vụ (400/404) ném Error với thông báo tiếng Việt từ server. */
  async function call(path, method = "GET", body) {
    const opts = { method };
    if (body !== undefined) {
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(body);
    }
    let r;
    try { r = await Session.api(path, opts); } catch { throw new Error("Không kết nối được API (python backend/run_api.py)"); }
    if (r.status === 401) { Session.toLogin(); throw new Error("Hết phiên đăng nhập"); }
    if (r.status === 403) { Session.toLogin(); throw new Error("Không có quyền"); }
    if (r.status === 204) return null;
    const data = await r.json().catch(() => null);
    if (!r.ok) {
      const d = data && data.detail;
      throw new Error(typeof d === "string" ? d : `API trả lỗi ${r.status}`);
    }
    return data;
  }

  document.querySelectorAll("dialog [data-close]").forEach((b) =>
    b.addEventListener("click", () => b.closest("dialog").close()));

  /* Hộp xác nhận theo giao diện trang (thay window.confirm). Trả Promise<boolean>.
   *   kind: "danger" (đỏ: xóa), "warn" (vàng: khóa), "" (thường: mở khóa) */
  function confirmBox({ title, message, ok = "Đồng ý", kind = "" }) {
    const dlg = $("confirmDialog");
    $("confirmTitle").textContent = title;
    $("confirmMessage").textContent = message;
    const btn = $("confirmOk");
    btn.textContent = ok;
    btn.className = "btn " + (kind === "danger" ? "danger-solid" : kind === "warn" ? "warn-solid" : "primary");
    dlg.dataset.kind = kind;
    return new Promise((resolve) => {
      const done = (value) => { dlg.removeEventListener("close", onClose); dlg.close(); resolve(value); };
      const onClose = () => done(false);                    // Esc hoặc nút Hủy
      btn.onclick = () => done(true);
      dlg.addEventListener("close", onClose);
      dlg.showModal();
      $("confirmCancel").focus();                           // mặc định chọn Hủy cho an toàn
    });
  }

  // ---------------- địa chỉ nhà (dùng chung cho thiết bị, luật, tài khoản) ----------------
  const NEW_HOUSE = "__new__";
  let housesCache = [];
  async function loadHouses() {
    housesCache = await call("/api/admin/houses");
    return housesCache;
  }
  const houses = () => housesCache;
  /* Nhãn một nhà: "Họ tên người dùng - Địa chỉ" (nhà chưa có người dùng thì ghi rõ). */
  const houseOwners = (h) => (h && h.owners) || "Chưa có người dùng";
  const houseLabel = (id) => {
    const h = housesCache.find((x) => x.id === id);
    return h ? `${houseOwners(h)} - ${h.address}` : "Chưa gắn địa chỉ";
  };
  /* Ô bảng: họ tên đậm, địa chỉ nhỏ bên dưới. */
  /* Lọc theo ô tìm "Họ tên - Địa chỉ": khớp họ tên người dùng hoặc địa chỉ (không phân biệt hoa thường). */
  const houseMatches = (id, query) => {
    const q = String(query || "").trim().toLowerCase();
    return !q || houseLabel(id).toLowerCase().includes(q);
  };
  const houseCell = (id) => {
    const h = housesCache.find((x) => x.id === id);
    return h ? `<b class="owner">${esc(houseOwners(h))}</b><small>${esc(h.address)}</small>` : '<span class="muted">—</span>';
  };

  /* Đổ danh sách địa chỉ vào <select data-house-select>. allowNew: thêm mục "+ Địa chỉ mới…" (hiện ô nhập
   * [data-house-new] cùng khung); empty: chữ cho mục rỗng (vd "Tất cả" khi lọc, "— Không —" cho admin). */
  function fillHouseSelect(sel, { selected = null, allowNew = false, empty = null } = {}) {
    sel.innerHTML = (empty !== null ? `<option value="">${esc(empty)}</option>` : "") +
      housesCache.map((h) => `<option value="${h.id}">${esc(houseOwners(h))} - ${esc(h.address)}</option>`).join("") +
      (allowNew ? `<option value="${NEW_HOUSE}">+ Địa chỉ mới…</option>` : "");
    sel.value = selected === null || selected === undefined ? "" : String(selected);
    if (!sel.value && empty === null && housesCache[0]) sel.value = String(housesCache[0].id);
    const input = sel.parentElement.querySelector("[data-house-new]");
    if (!input) return;
    input.value = "";
    input.hidden = sel.value !== NEW_HOUSE;
    if (!sel.dataset.bound) {
      sel.dataset.bound = "1";
      sel.addEventListener("change", () => { input.hidden = sel.value !== NEW_HOUSE; if (!input.hidden) input.focus(); });
    }
  }

  /* Đọc lựa chọn địa chỉ thành dữ liệu gửi API: {house_id} hoặc {new_address}. */
  function readHouse(sel) {
    if (sel.value === NEW_HOUSE) return { new_address: sel.parentElement.querySelector("[data-house-new]").value.trim() };
    return { house_id: sel.value ? Number(sel.value) : null };
  }

  // ---------------- sidebar ----------------
  const ICON = {
    home: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
    devices: '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>',
    rules: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>',
    alerts: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
    accounts: '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    roles: '<path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"/><path d="M9 12l2 2 4-4"/>',
    logins: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
  };
  const NAV = [
    { id: "home", label: "Tổng quan" },
    { id: "devices", label: "Thiết bị", badge: "devices" },
    { id: "rules", label: "Luật tự động", badge: "rules" },
    { id: "alerts", label: "Thông báo", badge: "alerts" },
    { header: "Quản lý người dùng" },
    { id: "accounts", label: "Tài khoản", title: "Quản lý người dùng / Tài khoản" },
    { id: "roles", label: "Vai trò", title: "Quản lý người dùng / Vai trò" },
    { header: "Hệ thống" },
    { id: "logins", label: "Lịch sử đăng nhập" },
  ];
  const PAGES = NAV.filter((n) => n.id).map((n) => n.id);
  const TITLES = Object.fromEntries(NAV.filter((n) => n.id).map((n) => [n.id, n.title || n.label]));
  const svg = (name) => `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICON[name]}</svg>`;

  const sidebar = $("sidebar");
  sidebar.innerHTML = `
    <div class="side-brand">
      <div class="logo" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>
      </div>
      <div class="brand-text"><h1>Trang quản trị</h1><p class="sub">Nhà thông minh MQTT</p></div>
    </div>
    <nav aria-label="Điều hướng quản trị"><ul class="nav-list">
      ${NAV.map((n) => n.header ? `<li class="nav-header">${esc(n.header)}</li>` : `
        <li><a class="nav-item" href="#/${n.id}" data-page="${n.id}">
          <span class="nav-icon" aria-hidden="true">${svg(n.id)}</span>
          <span class="nav-label">${esc(n.label)}</span>
          ${n.badge ? `<span class="nav-badge" data-badge="${n.badge}" hidden></span>` : ""}
        </a></li>`).join("")}
    </ul></nav>
    <div class="side-foot">
      <button type="button" class="side-collapse-btn" id="btnCollapseSide" title="Thu gọn / Mở rộng sidebar">
        <span class="collapse-icon">«</span><span class="collapse-text">Thu gọn</span>
      </button>
    </div>`;

  function setCollapsed(on) {
    sidebar.classList.toggle("collapsed", on);
    sidebar.querySelector(".collapse-icon").textContent = on ? "»" : "«";
    sidebar.querySelector(".collapse-text").textContent = on ? "" : "Thu gọn";
  }
  $("btnCollapseSide").addEventListener("click", () => {
    const on = !sidebar.classList.contains("collapsed");
    setCollapsed(on);
    store.set("sh.sidebar.collapsed", on ? "1" : "0");
  });
  if (store.get("sh.sidebar.collapsed") === "1" && window.innerWidth >= 1024) setCollapsed(true);

  const scrim = $("drawerScrim");
  const closeDrawer = () => { sidebar.classList.remove("drawer-open"); scrim.classList.remove("open"); };
  $("btnDrawer").addEventListener("click", () => { sidebar.classList.toggle("drawer-open"); scrim.classList.toggle("open"); });
  scrim.addEventListener("click", closeDrawer);
  window.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

  /* Số nhỏ cạnh mục menu. kind "alert" = màu đỏ. */
  function setBadge(name, value, kind = "") {
    const b = sidebar.querySelector(`[data-badge="${name}"]`);
    if (!b) return;
    b.hidden = value === "" || value === null || value === undefined;
    b.textContent = value ?? "";
    b.className = "nav-badge" + (kind ? " " + kind : "");
    if (name === "alerts") {                      // chuông trên thanh trên dùng chung số với mục Thông báo
      const bell = $("bellBadge");
      bell.hidden = b.hidden;
      bell.textContent = b.textContent;
      bell.className = "bell-badge" + (kind ? " " + kind : "");
    }
  }

  // ---------------- điều hướng ----------------
  /* #/<trang>/<phần con>, ví dụ #/devices/12 = trang chi tiết thiết bị 12.
   * admin:page  chỉ phát khi đổi sang trang khác; admin:route phát mỗi lần #hash đổi (kể cả phần con). */
  let current = null;
  function route() {
    const [id, sub = null] = (location.hash || "#/home").replace(/^#\/?/, "").split("/");
    const page = PAGES.includes(id) ? id : "home";
    if (page === current) {
      $("pageCrumb").textContent = TITLES[page];
      emit("admin:route", { page, sub });
      return;
    }
    current = page;
    document.querySelectorAll(".page").forEach((p) => p.classList.toggle("active", p.id === "admin-" + page));
    sidebar.querySelectorAll(".nav-item").forEach((a) => {
      const on = a.dataset.page === page;
      a.classList.toggle("active", on);
      if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    $("pageCrumb").textContent = TITLES[page];
    closeDrawer();
    emit("admin:page", page);
    emit("admin:route", { page, sub });
  }
  const setCrumb = (text) => { $("pageCrumb").textContent = text; };
  window.addEventListener("hashchange", route);

  // ---------------- broker (dùng chung) ----------------
  const qs = new URLSearchParams(location.search);
  const PREFIX = "home";
  const BROKER = qs.get("broker") || `${location.protocol === "https:" ? "wss" : "ws"}://${location.hostname || "localhost"}:9001`;
  const live = new Map();         // "phòng/mã" -> payload status mới nhất

  function setBroker(kind, text) {
    $("brokerPill").className = "pill sm " + kind;
    $("brokerPill").querySelector("span").textContent = text;
  }

  function connectBroker() {
    if (typeof mqtt === "undefined") { setBroker("off", "Không tải được MQTT.js"); return; }
    const client = mqtt.connect(BROKER, {
      clientId: "admin-" + Math.random().toString(16).slice(2, 8), clean: true, reconnectPeriod: 3000, connectTimeout: 5000,
    });
    client.on("connect", () => {
      setBroker("on", "Broker: đã kết nối");
      client.subscribe([`${PREFIX}/+/+/status`, `${PREFIX}/_auto/notify/event`], { qos: 1 });
    });
    client.on("reconnect", () => setBroker("wait", "Broker: đang kết nối lại…"));
    client.on("offline", () => setBroker("off", "Broker: chưa chạy"));
    client.on("message", (topic, payload) => {
      const [, room, code, kind] = topic.split("/");
      if (room === "_auto" && code === "notify") {
        try { emit("admin:notify", JSON.parse(payload.toString())); } catch { /* bỏ qua message hỏng */ }
        return;
      }
      if (kind !== "status" || room.startsWith("_")) return;      // _dashboard, _auto: không phải thiết bị
      const key = `${room}/${code}`;
      if (!payload.length) live.delete(key);                       // retained bị xóa: thiết bị bị gỡ
      else { try { live.set(key, JSON.parse(payload.toString())); } catch { return; } }
      emit("admin:status", key);
    });
  }

  /* online / offline / unknown (chưa từng thấy trên broker). Thiết bị con của bo mạch offline theo bo mạch. */
  function liveState(key) {
    const s = live.get(key);
    if (!s) return "unknown";
    if (s.state === "offline") return "offline";
    if (s.node) {
      const node = live.get(`${key.split("/")[0]}/${s.node}`);
      if (node && node.state === "offline") return "offline";
    }
    return "online";
  }

  window.Admin = { call, esc, toast, fmtTime, setBadge, setCrumb, confirm: confirmBox, loadHouses, houses, houseLabel, houseCell, houseMatches, fillHouseSelect, readHouse, live, liveState, PREFIX, page: () => current };

  // Chờ các file admin-*.js nạp xong (cuối <body>) rồi mới mở trang đầu và kết nối broker
  window.addEventListener("DOMContentLoaded", () => {
    route();
    connectBroker();
  });
})();
