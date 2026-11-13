/* Trang quản trị — Tổng quan (số tài khoản, số thiết bị, thông báo) và trang Thông báo.
 *
 * Thông báo = sự kiện automation phát trên home/_auto/notify/event:
 *   - lịch sử: GET /api/alerts (logger ghi vào SQLite, cần run_logger.py)
 *   - trực tiếp: nhận qua broker (sự kiện admin:notify từ admin.js) */
(() => {
  const { call, esc, fmtTime, setBadge, liveState } = window.Admin;
  const $ = (id) => document.getElementById(id);
  const DAY = 24 * 3600 * 1000;
  const LEVEL = {
    critical: ["Nghiêm trọng", "bad"], warn: ["Cảnh báo", "warn"], info: ["Thông tin", "ok"], rule: ["Luật chạy", "idle"],
  };

  let alerts = [];               // [{t, level, text}] mới nhất trước
  let historyNote = "";          // lý do không có lịch sử (logger chưa chạy...)
  let overview = null;
  let deviceKeys = [];
  let unread = 0, unreadCritical = false;
  let filter = "all";

  // ---------------- danh sách thông báo ----------------
  function alertItem(a) {
    const [label, cls] = LEVEL[a.level] || [a.level || "?", "idle"];
    return `<li class="lvl-${esc(a.level)}"><time>${esc(fmtTime(a.t))}</time>
      <span class="tag ${cls}">${esc(label)}</span><span class="alert-text">${esc(a.text)}</span></li>`;
  }
  const important = (a) => a.level !== "rule";
  const emptyItem = (text) => `<li class="muted">${esc(text)}</li>`;

  function renderAlerts() {
    // Tổng quan bỏ qua "Luật chạy" (rất nhiều, ít quan trọng); trang Thông báo vẫn xem được qua bộ lọc
    const recent = alerts.filter(important).slice(0, 8);
    $("recentAlerts").innerHTML = recent.length ? recent.map(alertItem).join("")
      : emptyItem(historyNote || "Chưa có thông báo.");
    const shown = alerts.filter((a) => filter === "all" || a.level === filter);
    $("allAlerts").innerHTML = (historyNote ? emptyItem(historyNote) : "") +
      (shown.length ? shown.map(alertItem).join("") : historyNote ? "" : emptyItem("Không có thông báo nào."));
  }

  // ---------------- KPI ----------------
  function renderKpis() {
    if (!overview) return;
    const online = deviceKeys.filter((k) => liveState(k) === "online").length;
    const day = alerts.filter((a) => important(a) && Date.now() - a.t < DAY);
    const critical = day.filter((a) => a.level === "critical").length;
    const items = [
      ["Tài khoản", overview.users_total, `${overview.users_admin} quản trị viên · ${overview.users_total - overview.users_admin} người dùng`, "#/accounts"],
      ["Thiết bị", overview.devices_total, `${online} đang online · ${overview.devices_total - overview.devices_simulated} thiết bị thật`, "#/devices"],
      ["Thông báo 24 giờ", day.length, critical ? `${critical} nghiêm trọng` : "Không có cảnh báo nghiêm trọng", "#/alerts"],
    ];
    $("adminKpis").innerHTML = items.map(([label, value, note, href]) =>
      `<a class="kpi kpi-link" href="${href}"><span class="k-label">${esc(label)}</span><span class="k-val">${esc(value)}</span><span class="muted">${esc(note)}</span></a>`).join("");
  }

  // ---------------- tải dữ liệu ----------------
  async function loadAlerts() {
    try {
      const rows = await call("/api/alerts?limit=200");
      const live = alerts.filter((a) => a.live);
      const seen = new Set(rows.map((r) => `${r.t}|${r.text}`));
      alerts = [...live.filter((a) => !seen.has(`${a.t}|${a.text}`)), ...rows].sort((a, b) => b.t - a.t);
      historyNote = "";
    } catch {
      historyNote = "Chưa đọc được lịch sử thông báo (cần chạy python backend/run_logger.py). Thông báo mới vẫn hiện trực tiếp.";
    }
    renderAlerts();
    renderKpis();
  }

  async function loadOverview() {
    try {
      const [o, devices] = await Promise.all([call("/api/admin/overview"), call("/api/admin/devices")]);
      overview = o;
      deviceKeys = devices.map((d) => d.key);
      setBadge("devices", devices.length);
      setBadge("rules", o.rules_total);
      renderKpis();
    } catch (e) {
      $("adminKpis").innerHTML = `<div class="panel muted">${esc(e.message)}</div>`;
    }
  }

  // ---------------- sự kiện ----------------
  document.addEventListener("admin:notify", (e) => {
    const p = e.detail || {};
    alerts.unshift({ t: p.ts || Date.now(), level: p.level, text: p.text, live: true });
    if (alerts.length > 300) alerts.length = 300;
    if (Admin.page() !== "alerts" && p.level !== "rule") {
      unread += 1;
      unreadCritical = unreadCritical || p.level === "critical";
      setBadge("alerts", unread, unreadCritical ? "alert" : "");
    }
    renderAlerts();
    renderKpis();
  });

  let kpiTimer = null;           // nhiều status tới dồn dập lúc mới kết nối → gom lại vẽ 1 lần
  document.addEventListener("admin:status", () => {
    clearTimeout(kpiTimer);
    kpiTimer = setTimeout(renderKpis, 200);
  });

  let first = true;              // trang mở đầu tiên là trang nào cũng nạp số liệu một lần (cho số trên sidebar)
  document.addEventListener("admin:page", (e) => {
    if (first || e.detail === "home") loadOverview();
    first = false;
    if (e.detail === "home") loadAlerts();
    if (e.detail === "alerts") {
      unread = 0; unreadCritical = false;
      setBadge("alerts", "");
      loadAlerts();
    }
  });

  $("alertFilter").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-level]");
    if (!b) return;
    filter = b.dataset.level;
    $("alertFilter").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    renderAlerts();
  });

  Admin.reloadOverview = loadOverview;
})();
