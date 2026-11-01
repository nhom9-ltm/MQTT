/**
 * FE/js/nav.js — Quản lý sidebar, định tuyến (router hash),
 * lọc phòng (Prompt 02), thông báo & chuông (Prompt 05).
 * Chạy ngầm mượt mà, không giật/chớp giao diện.
 */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const $$ = (sel, parent = document) => Array.from(parent.querySelectorAll(sel));

  // Trạng thái đếm thông báo
  let unreadAlerts = 0;
  let hasCriticalAlert = false;
  let currentRoute = "home";
  let isInternalClick = false;
  let lastSubmenuHtml = "";
  let lastScenesSignature = "";

  // Danh sách các mục menu
  const NAV_ITEMS = [
    {
      id: "home",
      hash: "#/home",
      label: "Tổng quan",
      icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>'
    },
    {
      id: "devices",
      hash: "#/devices",
      label: "Thiết bị",
      badge: "devices",
      icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/></svg>'
    },
    {
      id: "scenes",
      hash: "#/scenes",
      label: "Kịch bản & chế độ",
      icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>'
    },
    {
      id: "rules",
      hash: "#/rules",
      label: "Luật tự động",
      badge: "rules",
      icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>'
    },
    {
      id: "alerts",
      hash: "#/alerts",
      label: "Thông báo",
      badge: "alerts",
      icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>'
    },
    { type: "header", label: "Dữ liệu" },
    {
      id: "history",
      href: "history.html",
      label: "Lịch sử",
      icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
    },
    { type: "header", label: "Hệ thống" },
    {
      id: "log",
      hash: "#/log",
      label: "Message log",
      icon: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>'
    }
  ];

  /**
   * Khởi tạo HTML cho sidebar (chỉ chạy 1 lần)
   */
  function renderSidebar() {
    const sidebar = $("sidebar");
    if (!sidebar || sidebar.dataset.rendered === "1") return;
    sidebar.dataset.rendered = "1";

    let navHtml = '<nav aria-label="Điều hướng chính"><ul class="nav-list">';
    for (const item of NAV_ITEMS) {
      if (item.type === "header") {
        navHtml += `<li class="nav-header">${item.label}</li>`;
        continue;
      }

      const isLink = Boolean(item.href);
      const url = isLink ? item.href : item.hash;

      navHtml += `
        <li>
          <a class="nav-item" href="${url}" data-page="${item.id}">
            <span class="nav-icon" aria-hidden="true">${item.icon}</span>
            <span class="nav-label">${item.label}</span>
            ${item.badge ? `<span class="nav-badge" data-badge="${item.badge}" hidden></span>` : ''}
          </a>
          ${item.id === "devices" ? '<ul class="room-submenu" id="sidebarRooms"></ul>' : ''}
        </li>
      `;
    }
    navHtml += '</ul></nav>';

    const brandHtml = `
      <div class="side-brand">
        <div class="logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>
        </div>
        <div class="brand-text">
          <h1>Nhà thông minh</h1>
          <p class="sub">MQTT · Mosquitto · ESP32</p>
        </div>
      </div>
    `;

    const footHtml = `
      <div class="side-foot">
        <button type="button" class="side-collapse-btn" id="btnCollapseSide" title="Thu gọn / Mở rộng sidebar">
          <span class="collapse-icon">«</span>
          <span class="collapse-text">Thu gọn</span>
        </button>
      </div>
    `;

    sidebar.innerHTML = brandHtml + navHtml + footHtml;

    // Gắn sự kiện thu gọn sidebar
    const btnCollapse = $("btnCollapseSide");
    if (btnCollapse) {
      btnCollapse.addEventListener("click", () => {
        const isCollapsed = sidebar.classList.toggle("collapsed");
        localStorage.setItem("sh.sidebar.collapsed", isCollapsed ? "1" : "0");
        const icon = btnCollapse.querySelector(".collapse-icon");
        const text = btnCollapse.querySelector(".collapse-text");
        if (icon) icon.textContent = isCollapsed ? "»" : "«";
        if (text) text.textContent = isCollapsed ? "" : "Thu gọn";
        setTimeout(() => window.dispatchEvent(new Event("resize")), 100);
      });

      if (localStorage.getItem("sh.sidebar.collapsed") === "1" && window.innerWidth >= 1024) {
        sidebar.classList.add("collapsed");
        const icon = btnCollapse.querySelector(".collapse-icon");
        const text = btnCollapse.querySelector(".collapse-text");
        if (icon) icon.textContent = "»";
        if (text) text.textContent = "";
      }
    }
  }

  /**
   * Bộ định tuyến theo hash (Router)
   * Chỉ cập nhật khi route thực sự thay đổi, không chớp màn hình.
   */
  function handleRoute() {
    const rawHash = location.hash || "#/home";
    const parts = rawHash.replace(/^#\/?/, "").split("/").filter(Boolean);
    const pageId = parts[0] || "home";
    const subParam = parts[1] || null;

    currentRoute = pageId;

    const validPages = ["home", "devices", "scenes", "rules", "alerts", "log"];
    const targetPageId = validPages.includes(pageId) ? pageId : "home";

    const activeSection = $(`page-${targetPageId}`);
    // Chỉ đổi active class khi trang mục tiêu chưa active (tránh chớp trang)
    if (activeSection && !activeSection.classList.contains("active")) {
      $$(".page").forEach(p => {
        if (p !== activeSection) p.classList.remove("active");
      });
      activeSection.classList.add("active");
      // Cập nhật lại kích thước biểu đồ ngầm
      requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
    }

    // Cập nhật trạng thái active trên sidebar
    $$(".nav-item").forEach(item => {
      const p = item.getAttribute("data-page");
      if (p === targetPageId) {
        if (!item.classList.contains("active")) {
          item.classList.add("active");
          item.setAttribute("aria-current", "page");
        }
      } else {
        if (item.classList.contains("active")) {
          item.classList.remove("active");
          item.removeAttribute("aria-current");
        }
      }
    });

    // Cập nhật tiêu đề breadcrumb
    const pageTitleMap = {
      home: "Tổng quan",
      devices: "Thiết bị",
      scenes: "Kịch bản & chế độ",
      rules: "Luật tự động",
      alerts: "Thông báo",
      log: "Message log"
    };
    const crumbEl = $("pageCrumb");
    if (crumbEl) {
      let title = pageTitleMap[targetPageId] || "Tổng quan";
      if (targetPageId === "devices" && subParam) {
        const tabBtn = $(`roomTabs`)?.querySelector(`button[data-room="${subParam}"]`);
        const roomName = tabBtn ? tabBtn.textContent.trim() : subParam;
        title += ` / ${roomName}`;
      }
      if (crumbEl.textContent !== title) {
        crumbEl.textContent = title;
      }
    }

    if (targetPageId === "devices") {
      filterRoomFromRoute(subParam);
    }

    if (targetPageId === "alerts") {
      resetAlertCount();
    }

    // Đóng drawer trên mobile
    const sidebar = $("sidebar");
    const scrim = $("drawerScrim");
    if (sidebar && sidebar.classList.contains("drawer-open")) {
      sidebar.classList.remove("drawer-open");
      if (scrim) scrim.classList.remove("open");
    }
  }

  /**
   * Lọc phòng từ route (Prompt 02)
   */
  function filterRoomFromRoute(roomId) {
    const targetRoom = roomId || "all";
    const roomTabs = $("roomTabs");
    if (!roomTabs) return;

    const tabBtn = roomTabs.querySelector(`button[data-room="${targetRoom}"]`);
    if (tabBtn && !tabBtn.classList.contains("on")) {
      isInternalClick = true;
      tabBtn.click();
      isInternalClick = false;
    }

    // Cập nhật active trong sidebar room submenu mà không làm reload
    $$(".room-subitem").forEach(item => {
      const r = item.getAttribute("data-room");
      if (r === targetRoom) {
        item.classList.add("active");
      } else {
        item.classList.remove("active");
      }
    });
  }

  /**
   * Cập nhật danh sách phòng trên sidebar (Prompt 02 - 3.1)
   * Chạy ngầm, chỉ cập nhật khi dữ liệu có thay đổi thật sự.
   */
  function updateRoomSubmenu() {
    const list = $("sidebarRooms");
    const roomTabs = $("roomTabs");
    const roomsContainer = $("rooms");
    if (!list || !roomTabs) return;

    const tabButtons = $$("button[data-room]", roomTabs);
    if (!tabButtons.length) return;

    const isAllActive = !location.hash.includes("/") || location.hash.endsWith("/devices");
    let html = `
      <li>
        <a class="room-subitem ${isAllActive ? 'active' : ''}" href="#/devices" data-room="all">
          <span>Tất cả</span>
        </a>
      </li>
    `;

    for (const btn of tabButtons) {
      const rId = btn.getAttribute("data-room");
      if (!rId || rId === "all") continue;

      const roomName = btn.textContent.trim();
      const roomSection = roomsContainer?.querySelector(`section.room[data-room="${rId}"]`);

      let total = 0;
      let online = 0;
      if (roomSection) {
        total = $$(".dev", roomSection).length;
        online = $$(".dev:not(.offline)", roomSection).length;
      }

      const isOnline = online > 0;
      const dotCls = isOnline ? "room-dot" : "room-dot off";
      const isSelected = location.hash === `#/devices/${rId}`;

      html += `
        <li>
          <a class="room-subitem ${isSelected ? 'active' : ''}" href="#/devices/${rId}" data-room="${rId}">
            <span class="${dotCls}" aria-hidden="true"></span>
            <span>${roomName}</span>
            <span class="room-badge">${total > 0 ? (online === total ? total : `${online}/${total}`) : ''}</span>
          </a>
        </li>
      `;
    }

    // CHỈ thay đổi DOM khi HTML thực sự khác biệt (tránh chớp/giật)
    if (html !== lastSubmenuHtml) {
      lastSubmenuHtml = html;
      list.innerHTML = html;

      // Gắn sự kiện click
      $$(".room-subitem", list).forEach(item => {
        item.addEventListener("click", () => {
          const rId = item.getAttribute("data-room");
          const tabBtn = roomTabs.querySelector(`button[data-room="${rId}"]`);
          if (tabBtn) tabBtn.click();
        });
      });
    }

    // Cập nhật huy hiệu tổng mục "Thiết bị" từ #kOnline
    const kOnline = $("kOnline");
    const devBadge = document.querySelector('[data-badge="devices"]');
    if (kOnline && devBadge) {
      const txt = kOnline.textContent.trim();
      if (txt && txt !== "0/0" && txt !== "—") {
        if (devBadge.textContent !== txt) devBadge.textContent = txt;
        devBadge.hidden = false;
      } else {
        devBadge.hidden = true;
      }
    }
  }

  /**
   * Reset số lượng thông báo chưa đọc (Prompt 05)
   */
  function resetAlertCount() {
    unreadAlerts = 0;
    hasCriticalAlert = false;
    updateAlertBadgeUI();
  }

  /**
   * Cập nhật UI huy hiệu thông báo trên icon chuông và sidebar
   */
  function updateAlertBadgeUI() {
    const bellBadge = $("bellBadge");
    const sideBadge = document.querySelector('[data-badge="alerts"]');
    const btnBell = $("btnBell");

    if (unreadAlerts > 0) {
      const displayTxt = unreadAlerts > 99 ? "99+" : String(unreadAlerts);

      if (bellBadge) {
        if (bellBadge.textContent !== displayTxt) bellBadge.textContent = displayTxt;
        bellBadge.hidden = false;
        bellBadge.classList.toggle("alert", hasCriticalAlert);
      }

      if (sideBadge) {
        if (sideBadge.textContent !== displayTxt) sideBadge.textContent = displayTxt;
        sideBadge.hidden = false;
        sideBadge.classList.toggle("alert", hasCriticalAlert);
      }

      if (btnBell) {
        btnBell.setAttribute("aria-label", `Thông báo, ${unreadAlerts} chưa đọc`);
      }
    } else {
      if (bellBadge) {
        bellBadge.hidden = true;
        bellBadge.classList.remove("alert");
      }
      if (sideBadge) {
        sideBadge.hidden = true;
        sideBadge.classList.remove("alert");
      }
      if (btnBell) {
        btnBell.setAttribute("aria-label", "Thông báo");
      }
    }
  }

  /**
   * Khởi tạo theo dõi thông báo mới từ #alerts (Prompt 05)
   */
  function initAlertObserver() {
    const alertsList = $("alerts");
    if (!alertsList) return;

    const observer = new MutationObserver((mutations) => {
      let addedNew = false;
      for (const m of mutations) {
        for (const node of m.addedNodes) {
          if (node.nodeType === Node.ELEMENT_NODE && node.tagName === "LI") {
            if (node.classList.contains("muted") || node.classList.contains("rule")) {
              continue;
            }

            if (currentRoute !== "alerts") {
              unreadAlerts++;
              if (node.classList.contains("bad")) {
                hasCriticalAlert = true;
              }
              addedNew = true;
            }
          }
        }
      }

      if (addedNew) {
        updateAlertBadgeUI();
      }
    });

    observer.observe(alertsList, { childList: true });

    const btnClear = $("alertClear");
    if (btnClear) {
      btnClear.addEventListener("click", () => resetAlertCount());
    }
  }

  /**
   * Đồng bộ kịch bản nhanh trên trang chủ (Prompt 01 - B)
   * Chạy ngầm, không xóa dựng lại DOM liên tục.
   */
  function initQuickScenes() {
    const srcScenes = $("scenes");
    const quickScenes = $("quickScenes");
    if (!srcScenes || !quickScenes) return;

    function sync() {
      const btns = $$("button.scene", srcScenes);
      const signature = btns.map(b => b.getAttribute("data-scene") + ":" + b.disabled).join("|");
      if (signature === lastScenesSignature && btns.length > 0) return;
      lastScenesSignature = signature;

      quickScenes.innerHTML = "";
      if (!btns.length) {
        quickScenes.innerHTML = '<span class="muted">Chưa có kịch bản.</span>';
        return;
      }
      for (const btn of btns) {
        const clone = btn.cloneNode(true);
        clone.id = "";
        clone.addEventListener("click", () => btn.click());
        quickScenes.appendChild(clone);
      }
    }

    const obs = new MutationObserver(() => sync());
    obs.observe(srcScenes, { childList: true, subtree: true, attributes: true, attributeFilter: ["disabled", "class"] });
    sync();
  }

  /**
   * Đồng bộ nút Chế độ nhà trên thanh trên với #modeSeg
   */
  function initTopModeControls() {
    const origSeg = $("modeSeg");
    const topSeg = $("topModeSeg");
    if (!origSeg || !topSeg) return;

    $$(".top-mode-btn", topSeg).forEach(btn => {
      btn.addEventListener("click", () => {
        const mode = btn.getAttribute("data-mode");
        const origBtn = origSeg.querySelector(`button[data-mode="${mode}"]`);
        if (origBtn) origBtn.click();
      });
    });

    function syncMode() {
      const activeOrig = origSeg.querySelector("button.on");
      const currentMode = activeOrig ? activeOrig.getAttribute("data-mode") : null;
      $$(".top-mode-btn", topSeg).forEach(btn => {
        btn.classList.toggle("on", btn.getAttribute("data-mode") === currentMode);
      });
    }

    const obs = new MutationObserver(() => syncMode());
    obs.observe(origSeg, { subtree: true, attributes: true, attributeFilter: ["class", "disabled"] });
    syncMode();
  }

  /**
   * Khởi tạo Mobile Drawer
   */
  function initMobileDrawer() {
    const btnDrawer = $("btnDrawer");
    const sidebar = $("sidebar");
    const scrim = $("drawerScrim");

    if (btnDrawer && sidebar) {
      btnDrawer.addEventListener("click", () => {
        sidebar.classList.toggle("drawer-open");
        if (scrim) scrim.classList.toggle("open");
      });
    }

    if (scrim) {
      scrim.addEventListener("click", () => {
        sidebar?.classList.remove("drawer-open");
        scrim.classList.remove("open");
      });
    }

    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        sidebar?.classList.remove("drawer-open");
        scrim?.classList.remove("open");
      }
    });
  }

  /**
   * Khởi chạy khi DOM sẵn sàng
   */
  function init() {
    renderSidebar();
    handleRoute();
    window.addEventListener("hashchange", handleRoute);

    const roomTabs = $("roomTabs");
    const rooms = $("rooms");
    const kOnline = $("kOnline");

    let animFrame = null;
    const scheduleRoomUpdate = () => {
      if (animFrame) cancelAnimationFrame(animFrame);
      animFrame = requestAnimationFrame(() => {
        updateRoomSubmenu();
        animFrame = null;
      });
    };

    if (roomTabs) {
      const obsTabs = new MutationObserver(scheduleRoomUpdate);
      obsTabs.observe(roomTabs, { childList: true });
    }
    if (rooms) {
      const obsRooms = new MutationObserver(scheduleRoomUpdate);
      obsRooms.observe(rooms, { childList: true });
    }
    if (kOnline) {
      const obsOnline = new MutationObserver(scheduleRoomUpdate);
      obsOnline.observe(kOnline, { childList: true, characterData: true, subtree: true });
    }

    if (roomTabs) {
      roomTabs.addEventListener("click", (e) => {
        if (isInternalClick) return;
        const btn = e.target.closest("button[data-room]");
        if (btn) {
          const r = btn.getAttribute("data-room");
          const targetHash = r === "all" ? "#/devices" : `#/devices/${r}`;
          if (location.hash !== targetHash) {
            location.hash = targetHash;
          }
        }
      });
    }

    initAlertObserver();
    initQuickScenes();
    initTopModeControls();
    initMobileDrawer();

    scheduleRoomUpdate();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
