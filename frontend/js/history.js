/* Trang Lịch sử (#/history trong index.html): gọi API (backend/run_api.py) và vẽ biểu đồ bằng Chart.js.
 * API mặc định http://<host của trang>:8001 ; đổi bằng ?api=http://host:8001
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
  el.api.value = qs.get("api") || (web ? `${location.protocol}//${location.hostname}:8001` : "http://localhost:8001");
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

  $("histForm").addEventListener("submit", (e) => { e.preventDefault(); loadAll(); });
  el.range.addEventListener("change", loadAll);
  el.room.addEventListener("change", () => loadClimate(+el.range.value).catch(console.error));
  // Nạp dữ liệu mỗi lần người dùng mở trang Lịch sử (đợi 1 khung hình để trang đã hiển thị, biểu đồ đo đúng kích thước)
  window.addEventListener("sh:history-show", () => requestAnimationFrame(loadAll));
})();
