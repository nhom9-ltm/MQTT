/* Khung An ninh trên Trang chủ + banner báo động + hộp nhập PIN.
 *
 * Nhận trạng thái từ app.js (sự kiện "sh:security" khi có message home/_auto/security/state, retained) và gửi lệnh
 * home/_auto/security/set qua window.SmartHomeApp.send:
 *   {"action": "disarm", "pin": "1234", "mode": "home"}   tắt an ninh rồi chuyển chế độ (mặc định Ở nhà)
 *   {"action": "panic"}                                   báo động ngay
 * Mã PIN do automation engine kiểm tra (backend/services/security_service.py); trang này không biết PIN đúng. */
(() => {
  const $ = (id) => document.getElementById(id);
  if (!$("secBox")) return;

  const ACTIVE = ["arming", "armed_away", "pending", "triggered"];   // đổi chế độ (trừ Vắng nhà) phải nhập PIN
  const MODE_NAME = { home: "Ở nhà", away: "Vắng nhà", night: "Ban đêm" };
  const el = { box: $("secBox"), label: $("secLabel"), detail: $("secDetail"), disarm: $("secDisarm"), panic: $("secPanic"),
    banner: $("secBanner"), bannerText: $("secBannerText"), bannerPin: $("secBannerPin"),
    dialog: $("pinDialog"), form: $("pinForm"), input: $("pinInput"), hint: $("pinHint"), pad: $("pinPad"), cancel: $("pinCancel") };

  let sec = null;          // payload mới nhất của home/_auto/security/state (null = chưa kết nối / chưa có)
  let gotAt = 0;           // thời điểm nhận (đồng hồ trình duyệt) để đếm ngược "remaining"
  let target = "home";     // chế độ chuyển sang sau khi tắt an ninh
  let timer = null;

  const send = (obj) => window.SmartHomeApp && window.SmartHomeApp.send("_auto/security/set", obj);
  const hhmm = (ms) => new Date(ms).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
  const left = () => (sec && sec.remaining != null ? Math.max(0, Math.ceil(sec.remaining - (Date.now() - gotAt) / 1000)) : null);

  function text() {
    const s = sec.state, n = left(), who = sec.trigger ? sec.trigger.name : "";
    switch (s) {
      case "disarmed": return ["An ninh: Tắt", "Tự bật khi chuyển sang Vắng nhà / Ban đêm"];
      case "arming": return [`Đang bật an ninh — còn ${n}s`, "Hãy ra khỏi nhà và đóng cửa"];
      case "armed_away": return ["Đang canh gác — vắng nhà", `Từ ${hhmm(sec.since)} · cửa, chuyển động trong nhà`];
      case "armed_night": return ["Đang canh gác — ban đêm", `Từ ${hhmm(sec.since)} · chỉ canh cửa chính`];
      case "pending": return [`${who || "Cửa"} mở — nhập PIN trong ${n}s`, "Không nhập kịp sẽ báo động"];
      case "triggered": return [`BÁO ĐỘNG: ${who || "?"}`, `Từ ${hhmm(sec.since)} · nhập PIN để tắt`];
      default: return [sec.label || s, ""];
    }
  }

  function render() {
    clearInterval(timer);
    if (!sec) {
      el.box.dataset.state = "unknown";
      el.label.textContent = "An ninh: chưa có dữ liệu";
      el.detail.textContent = "Cần automation engine đang chạy";
      el.disarm.hidden = true;
      el.panic.disabled = true;
      el.banner.hidden = true;
      document.body.dataset.security = "";
      return;
    }
    const [label, detail] = text();
    el.box.dataset.state = sec.state;
    el.label.textContent = label;
    el.detail.textContent = detail + (sec.locked_until && sec.locked_until > Date.now()
      ? ` · khóa nhập PIN tới ${new Date(sec.locked_until).toLocaleTimeString("vi-VN")}` : "");
    el.disarm.hidden = sec.state === "disarmed";
    el.disarm.textContent = sec.state === "triggered" ? "Tắt báo động" : "Tắt an ninh";
    el.panic.disabled = sec.state === "triggered";
    const alarm = sec.state === "pending" || sec.state === "triggered";
    el.banner.hidden = !alarm;
    el.banner.dataset.state = sec.state;
    if (alarm) el.bannerText.textContent = label;
    document.body.dataset.security = sec.state;
    if (sec.state === "arming" || sec.state === "pending") timer = setInterval(() => {
      const [l] = text();
      el.label.textContent = l;
      if (alarm) el.bannerText.textContent = l;
      if (left() === 0) clearInterval(timer);
    }, 1000);
  }

  function openPin(mode = "home") {
    target = MODE_NAME[mode] ? mode : "home";
    el.hint.textContent = `Tắt an ninh rồi chuyển sang chế độ ${MODE_NAME[target]}`;
    el.input.value = "";
    if (!el.dialog.open) el.dialog.showModal();
    el.input.focus();
  }

  window.addEventListener("sh:security", (e) => {
    const prev = sec && sec.state;
    sec = e.detail && e.detail.state ? e.detail : null;
    gotAt = Date.now();
    render();
    // Vừa mở cửa khi đang canh gác: tự mở hộp PIN cho người vừa về nhà
    if (sec && sec.state === "pending" && prev && prev !== "pending") openPin("home");
    if (sec && sec.state === "disarmed" && el.dialog.open) el.dialog.close();
  });

  el.disarm.addEventListener("click", () => openPin("home"));
  el.bannerPin.addEventListener("click", () => openPin("home"));
  el.panic.addEventListener("click", () => {
    if (confirm("Phát BÁO ĐỘNG khẩn cấp ngay bây giờ?")) send({ action: "panic" });
  });
  el.pad.addEventListener("click", (e) => {
    const k = e.target.closest("button[data-k]");
    if (!k) return;
    if (k.dataset.k === "clear") el.input.value = el.input.value.slice(0, -1);
    else if (el.input.value.length < 8) el.input.value += k.dataset.k;
    el.input.focus();
  });
  el.cancel.addEventListener("click", () => el.dialog.close());
  el.form.addEventListener("submit", (e) => {
    const pin = el.input.value.trim();
    if (!/^\d{4,8}$/.test(pin)) {
      e.preventDefault();
      el.hint.textContent = "PIN gồm 4–8 chữ số";
      return;
    }
    send({ action: "disarm", pin, mode: target });
    el.input.value = "";
  });

  // app.js hỏi trước khi gửi lệnh đổi chế độ: true = đã chặn lại để hỏi PIN
  window.SmartHomeSecurity = {
    interceptMode(mode) {
      if (!sec || !ACTIVE.includes(sec.state) || mode === "away") return false;
      openPin(mode);
      return true;
    },
  };
  render();
})();
