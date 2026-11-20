/* Trang Lịch sử (#/history trong index.html): gọi API (backend/run_api.py) và vẽ biểu đồ bằng Chart.js.
 * API mặc định http://<host của trang>:8011 ; đổi bằng ?api=http://host:8011
 * Dữ liệu chỉ được nạp khi người dùng mở trang này (nav.js phát sự kiện "sh:history-show"). */
(() => {
  const $ = (id) => document.getElementById(id);
  if (!$("page-history")) return;
  const qs = new URLSearchParams(location.search);
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const PALETTE = ["#3fb6a8", "#ff8a3d", "#4aa8ff", "#c084fc", "#f5b942", "#ff5d8f", "#3ccf7e", "#a78bfa"];

  const el = { api: $("apiUrl"), range: $("histRange"), room: $("histRoom"), pill: $("apiPill"),
    kpis: $("histKpis"), alerts: $("histAlerts") };
  // Mở bằng file:// thì không có hostname/giao thức http -> dùng thẳng localhost
  const web = location.protocol === "http:" || location.protocol === "https:";
  el.api.value = qs.get("api") || (web ? `${location.protocol}//${location.hostname}:8011` : "http://localhost:8011");
  if (qs.get("hours")) el.range.value = qs.get("hours");

  const charts = {};
  const fmtTime = (t, hours) => new Date(t).toLocaleString("vi-VN",
    hours > 24 ? { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }
               : { hour: "2-digit", minute: "2-digit" });

  function setPill(kind, text) {
    el.pill.className = "pill " + kind;
    el.pill.querySelector("span").textContent = text;
  }

  async function get(path) {
    const r = await fetch(el.api.value.replace(/\/$/, "") + path);
    if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 120)}`);
    return r.json();
  }

  function draw(id, config) {
    charts[id]?.destroy();
    // Giá trị giống hệt app.js để không làm đổi giao diện các biểu đồ ở Trang chủ (Chart.defaults là toàn cục)
    Chart.defaults.color = css("--muted");
    Chart.defaults.borderColor = css("--line");
    Chart.defaults.font.family = '"Be Vietnam Pro", system-ui, sans-serif';
    charts[id] = new Chart($(id), { ...config, options: {
      responsive: true, maintainAspectRatio: false, animation: false, ...config.options } });
  }

  function empty(id, msg = "Chưa có dữ liệu trong khoảng này") {
    charts[id]?.destroy();
    const box = $(id).parentElement;
    box.querySelector(".hist-empty")?.remove();
    $(id).style.display = "none";
    box.insertAdjacentHTML("beforeend", `<div class="hist-empty">${msg}</div>`);
  }
  function unempty(id) {
    $(id).style.display = "";
    $(id).parentElement.querySelector(".hist-empty")?.remove();
  }

  const bar = (id, labels, data, color, horizontal = false) => {
    if (!data.length) return empty(id);
    unempty(id);
    draw(id, { type: "bar", data: { labels, datasets: [{ data, backgroundColor: color, borderRadius: 4 }] },
      options: { indexAxis: horizontal ? "y" : "x", layout: { padding: { left: 16 } },
        plugins: { legend: { display: false } } } });
  };

  const kpi = (value, label) => `<div class="kpi"><span class="k-label">${label}</span><span class="k-val">${value}</span></div>`;
  const LEVEL_CLASS = { critical: "bad", warn: "warn", info: "info", rule: "rule" };

  async function loadClimate(hours) {
    if (!el.room.value) return empty("cClimate");
    const d = await get(`/api/climate?room=${encodeURIComponent(el.room.value)}&hours=${hours}`);
    if (!d.points.length) return empty("cClimate");
    unempty("cClimate");
    draw("cClimate", { type: "line", data: {
      labels: d.points.map((p) => fmtTime(p.t, hours)),
      datasets: [
        { label: "Nhiệt độ (°C)", data: d.points.map((p) => p.temperature), borderColor: css("--temp"),
          backgroundColor: css("--temp"), yAxisID: "y", pointRadius: 0, tension: .3, borderWidth: 2 },
        { label: "Độ ẩm (%)", data: d.points.map((p) => p.humidity), borderColor: css("--hum"),
          backgroundColor: css("--hum"), yAxisID: "y2", pointRadius: 0, tension: .3, borderWidth: 2 },
      ] }, options: { interaction: { mode: "index", intersect: false },
        scales: { x: { ticks: { maxTicksLimit: 8 } },
                  y: { position: "left", title: { display: true, text: "°C" } },
                  y2: { position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "%" } } } } });
  }

  // ---------- Tiền điện theo tháng (GET /api/energy/report) ----------
  const vnd = (n) => Math.round(n).toLocaleString("vi-VN") + " đ";
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const BUDGET_TEXT = { ok: "trong ngân sách", warn: "sắp chạm / dự báo vượt ngân sách", over: "đã VƯỢT ngân sách" };
  const pad = (n) => String(n).padStart(2, "0");
  const thisMonth = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}`; };
  $("billMonth").value = thisMonth();
  $("billMonth").max = thisMonth();

  async function loadBill() {
    const r = await get(`/api/energy/report?month=${$("billMonth").value || thisMonth()}`);
    const b = r.budget, p = r.projected;
    const kp = (value, label, sub = "", cls = "") =>
      `<div class="kpi"><span class="k-label">${label}</span><span class="k-val ${cls}">${value}</span>${sub ? `<span class="k-sub">${sub}</span>` : ""}</div>`;
    const cls = { warn: "warn", over: "bad" }[b.status] || "";
    $("billKpis").innerHTML = [
      kp(r.kwh.toFixed(1) + " kWh", "Điện đã dùng", r.finished ? "cả tháng" : "tính tới hiện tại"),
      kp(vnd(r.bill.total), "Tiền điện", `chưa VAT ${vnd(r.bill.subtotal)}`, cls),
      kp(p ? vnd(p.total) : "—", r.finished ? "Tổng cả tháng" : "Dự báo cuối tháng",
        p ? `≈ ${p.kwh.toFixed(0)} kWh` : "cần ít nhất 1 giờ dữ liệu", b.status === "warn" && p && p.total >= b.vnd ? "warn" : ""),
      kp(b.vnd ? vnd(b.vnd) : "Chưa đặt", "Ngân sách", b.vnd ? `${Math.round(b.used_ratio * 100)}% · ${BUDGET_TEXT[b.status]}` : "budget_vnd trong energy.json"),
    ].join("");

    const box = $("billBudget");
    box.dataset.status = b.status;
    const pct = (v) => Math.min(100, b.vnd ? v / b.vnd * 100 : 0) + "%";
    $("billBarNow").style.width = pct(r.bill.total);
    $("billBarProj").style.width = pct(p ? p.total : 0);
    $("billBudgetText").textContent = b.vnd
      ? `Đã dùng ${vnd(r.bill.total)} / ${vnd(b.vnd)}` + (p && !r.finished ? ` · vạch gạch: dự báo ${vnd(p.total)}` : "")
      : "";

    // Bậc giá: chỉ hiện các bậc đã dùng tới
    $("billTiers").innerHTML = r.bill.tiers.map((t) =>
      `<tr><td>Bậc ${t.tier} <span class="hint">(${t.from}–${t.to ?? "∞"} kWh · ${t.price.toLocaleString("vi-VN")} đ)</span></td>` +
      `<td class="n">${t.kwh.toFixed(1)} kWh</td><td class="n">${vnd(t.vnd)}</td></tr>`).join("") +
      `<tr><td>VAT</td><td></td><td class="n">${vnd(r.bill.vat)}</td></tr>` +
      `<tr class="total"><td>Tổng</td><td class="n">${r.kwh.toFixed(1)} kWh</td><td class="n">${vnd(r.bill.total)}</td></tr>`;
    $("billDevices").innerHTML = r.by_device.length ? r.by_device.slice(0, 8).map((d) =>
      `<tr><td class="bill-dev">${esc(d.device)}<span class="bill-share" style="width:${(d.share * 100).toFixed(1)}%"></span></td>` +
      `<td class="n">${(d.share * 100).toFixed(0)}%</td><td class="n">${vnd(d.vnd)}</td></tr>`).join("")
      : `<tr><td class="hint">Chưa có thiết bị đo điện trong tháng này</td></tr>`;

    // Biểu đồ: chi phí lũy kế theo ngày + đường dự báo tới cuối tháng + đường ngân sách
    const [y, m] = r.month.split("-").map(Number);
    const nDays = new Date(y, m, 0).getDate();
    const labels = Array.from({ length: nDays }, (_, i) => `${pad(i + 1)}/${pad(m)}`);
    const cum = new Array(nDays).fill(null);
    const byDay = Object.fromEntries(r.by_day.map((d) => [+d.day.slice(8), d.cum_vnd]));
    const days = Object.keys(byDay).map(Number);
    const last = days.length ? Math.max(...days) - 1 : -1;
    let carry = 0;
    for (let i = days.length ? Math.min(...days) : 1; i <= last + 1; i++) {   // ngày thiếu dữ liệu giữ nguyên tổng lũy kế
      if (byDay[i] != null) carry = byDay[i];
      cum[i - 1] = carry;
    }
    const proj = new Array(nDays).fill(null);
    if (p && !r.finished && last >= 0) {
      for (let i = last; i < nDays; i++) proj[i] = cum[last] + (p.total - cum[last]) * (i - last) / (nDays - 1 - last || 1);
    }
    if (!r.by_day.length) {
      empty("cBillCum", "Chưa có dữ liệu điện năng trong tháng này");
    } else {
      unempty("cBillCum");
      const ds = [
        { label: "Đã dùng", data: cum, borderColor: css("--accent"), backgroundColor: css("--accent"), pointRadius: 2, borderWidth: 2, tension: .2 },
        { label: "Dự báo", data: proj, borderColor: css("--muted"), borderDash: [5, 4], pointRadius: 0, borderWidth: 1.5 },
      ];
      if (b.vnd) ds.push({ label: "Ngân sách", data: labels.map(() => b.vnd), borderColor: css("--bad"),
        borderDash: [2, 3], pointRadius: 0, borderWidth: 1.5 });
      draw("cBillCum", { type: "line", data: { labels, datasets: ds }, options: {
        interaction: { mode: "index", intersect: false }, spanGaps: false,
        plugins: { tooltip: { callbacks: { label: (c) => c.raw == null ? null : `${c.dataset.label}: ${vnd(c.raw)}` } } },
        scales: { x: { ticks: { maxTicksLimit: 10 } },
                  y: { beginAtZero: true, ticks: { callback: (v) => (v / 1000).toLocaleString("vi-VN") + "k" } } } } });
    }
    const partial = r.finished && r.by_day.length && r.coverage < 0.9
      ? `Logger bắt đầu ghi muộn (chỉ phủ ${Math.round(r.coverage * 100)}% tháng) nên số liệu thấp hơn thực tế. ` : "";
    $("billNote").textContent = partial + "Tiền mỗi thiết bị chia theo tỉ lệ kWh. " + (r.price_note || "");
  }

  async function loadAll() {
    const hours = +el.range.value;
    setPill("wait", "Đang tải…");
    try {
      const [sum, energy, cmd, alerts] = await Promise.all([
        get(`/api/summary?hours=${hours}`), get(`/api/energy?days=${Math.max(1, Math.ceil(hours / 24))}`),
        get(`/api/commands?hours=${hours}`), get("/api/alerts?limit=15")]);

      // phòng: giữ lựa chọn cũ nếu còn
      const keep = el.room.value;
      el.room.innerHTML = sum.rooms.map((r) => `<option>${r}</option>`).join("");
      if (sum.rooms.includes(keep)) el.room.value = keep;

      const kwh = energy.by_day.reduce((a, x) => a + x.kwh, 0);
      el.kpis.innerHTML = [
        kpi(sum.messages_total.toLocaleString("vi-VN"), "Bản ghi đã lưu"),
        kpi(sum.commands, `Lệnh trong ${hours >= 24 ? hours / 24 + " ngày" : hours + " giờ"}`),
        kpi(kwh.toFixed(1), "kWh ước tính"),
        kpi(sum.alerts, "Cảnh báo critical"),
      ].join("");

      await loadClimate(hours);
      await showBill();
      bar("cEnergyDay", energy.by_day.map((x) => x.day.slice(5)), energy.by_day.map((x) => x.kwh), css("--accent"));
      bar("cEnergyDev", energy.by_device.slice(0, 8).map((x) => x.device), energy.by_device.slice(0, 8).map((x) => x.kwh), css("--c-plug"), true);

      if (cmd.by_source.length) {
        unempty("cCmdSrc");
        draw("cCmdSrc", { type: "doughnut", data: { labels: cmd.by_source.map((x) => x.source),
          datasets: [{ data: cmd.by_source.map((x) => x.n), backgroundColor: PALETTE, borderWidth: 0 }] },
          options: { plugins: { legend: { position: "right" } } } });
      } else empty("cCmdSrc");
      bar("cCmdDev", cmd.by_device.map((x) => x.device), cmd.by_device.map((x) => x.n), css("--c-ac"), true);

      el.alerts.innerHTML = alerts.length ? alerts.map((a) =>
        `<li class="${LEVEL_CLASS[a.level] || "info"}"><time>${new Date(a.t).toLocaleString("vi-VN")}</time><span></span></li>`).join("")
        : `<li class="muted">Chưa có cảnh báo</li>`;
      [...el.alerts.querySelectorAll("li span")].forEach((s, i) => { s.textContent = alerts[i].text; });  // textContent: tránh chèn HTML

      setPill("ok", "API OK");
    } catch (e) {
      console.error(e);
      setPill("bad", "Lỗi API");
      el.kpis.innerHTML = kpi("⚠", "");
      el.kpis.querySelector(".k-label").textContent =
        `Không gọi được ${el.api.value}: ${e.message}. Đã chạy "python backend/run_api.py" chưa?`;
    }
  }

  // Lỗi riêng của khung tiền điện (ví dụ energy.json sai) không làm hỏng các biểu đồ khác
  async function showBill() {
    try {
      await loadBill();
    } catch (e) {
      console.error(e);
      empty("cBillCum", `Không tải được báo cáo tiền điện: ${esc(e.message)}`);
      $("billKpis").innerHTML = "";
    }
  }

  $("billMonth").addEventListener("change", showBill);
  $("histForm").addEventListener("submit", (e) => { e.preventDefault(); loadAll(); });
  el.range.addEventListener("change", loadAll);
  el.room.addEventListener("change", () => loadClimate(+el.range.value).catch(console.error));
  // Nạp dữ liệu mỗi lần người dùng mở trang Lịch sử (đợi 1 khung hình để trang đã hiển thị, biểu đồ đo đúng kích thước)
  window.addEventListener("sh:history-show", () => requestAnimationFrame(loadAll));
})();
