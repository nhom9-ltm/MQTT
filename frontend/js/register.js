/* Trang đăng ký: SĐT + họ tên → OTP 6 số (giả lập) → email, địa chỉ nhà, mật khẩu.
 * API: POST /api/auth/register/otp, /register/verify, /register (backend/services/registration_service.py).
 * Mọi kết quả (thành công / thất bại) đều hiện ở khung thông báo phía trên form. */
(() => {
  const $ = (id) => document.getElementById(id);
  const GMAIL = /^[a-z0-9._%+-]+@gmail\.com$/;
  const PHONE = /^0\d{9}$/;

  if (Session.token() && Session.user()) { location.replace(Session.homeOf(Session.user())); return; }

  const state = { phone: "", name: "", token: "", resendTimer: null };
  const boxes = [...document.querySelectorAll("#otpBoxes input")];

  // ---------------- thông báo ----------------
  function msg(kind, text) {
    const m = $("regMsg");
    m.className = "form-msg " + kind;          // ok | bad | info
    m.textContent = text;
    m.hidden = !text;
  }

  function showStep(n) {
    [1, 2, 3].forEach((i) => ($("step" + i).hidden = i !== n));
    document.querySelectorAll(".steps li").forEach((li) => {
      const s = Number(li.dataset.step);
      li.classList.toggle("on", s === n);
      li.classList.toggle("done", s < n);
    });
    $("mockSms").hidden = n !== 2;
  }

  async function post(path, body) {
    let r;
    try {
      r = await Session.api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    } catch {
      throw new Error("Không kết nối được máy chủ. Hãy chạy: python backend/run_api.py");
    }
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Máy chủ trả lỗi ${r.status}`);
    return data;
  }

  async function busy(btn, label, fn) {
    const old = btn.textContent;
    btn.disabled = true;
    btn.textContent = label;
    try { await fn(); } finally { btn.disabled = false; btn.textContent = old; }
  }

  // ---------------- bước 1: gửi OTP ----------------
  function startResendCountdown(seconds) {
    clearInterval(state.resendTimer);
    let left = seconds;
    const btn = $("btnResend");
    const tick = () => {
      btn.disabled = left > 0;
      btn.textContent = left > 0 ? `Gửi lại mã (${left}s)` : "Gửi lại mã";
      if (left-- <= 0) clearInterval(state.resendTimer);
    };
    tick();
    state.resendTimer = setInterval(tick, 1000);
  }

  async function sendOtp() {
    const data = await post("/api/auth/register/otp", { phone: state.phone, full_name: state.name });
    state.phone = data.phone;
    $("smsPhone").textContent = data.phone;
    $("smsCode").textContent = data.mock_sms;
    $("otpPhone").textContent = data.phone;
    boxes.forEach((b) => (b.value = ""));
    showStep(2);
    msg("ok", `Đã gửi mã OTP tới ${data.phone}. Mã có hiệu lực 5 phút.`);
    startResendCountdown(data.resend_after || 30);
    boxes[0].focus();
  }

  $("step1").addEventListener("submit", (e) => {
    e.preventDefault();
    const phone = $("regPhone").value.replace(/[\s.-]/g, "").replace(/^\+84/, "0");
    const name = $("regName").value.trim().replace(/\s+/g, " ");
    if (!PHONE.test(phone)) { msg("bad", "Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0 (vd 0901234567)."); $("regPhone").focus(); return; }
    if (name.length < 2) { msg("bad", "Nhập họ và tên (ít nhất 2 ký tự)."); $("regName").focus(); return; }
    state.phone = phone;
    state.name = name;
    busy($("btnSendOtp"), "Đang gửi mã…", () => sendOtp().catch((err) => msg("bad", err.message)));
  });

  // ---------------- bước 2: nhập OTP ----------------
  boxes.forEach((box, i) => {
    box.addEventListener("input", () => {
      box.value = box.value.replace(/\D/g, "").slice(-1);
      if (box.value && i < boxes.length - 1) boxes[i + 1].focus();
      if (boxes.every((b) => b.value)) $("step2").requestSubmit();
    });
    box.addEventListener("keydown", (e) => {
      if (e.key === "Backspace" && !box.value && i > 0) boxes[i - 1].focus();
    });
    box.addEventListener("paste", (e) => {                     // dán cả 6 số một lần
      const digits = (e.clipboardData.getData("text") || "").replace(/\D/g, "").slice(0, 6);
      if (!digits) return;
      e.preventDefault();
      digits.split("").forEach((d, k) => { if (boxes[k]) boxes[k].value = d; });
      (boxes[digits.length] || boxes[5]).focus();
      if (digits.length === 6) $("step2").requestSubmit();
    });
  });

  $("step2").addEventListener("submit", (e) => {
    e.preventDefault();
    const otp = boxes.map((b) => b.value).join("");
    if (otp.length !== 6) { msg("bad", "Nhập đủ 6 số của mã OTP."); return; }
    busy($("btnVerify"), "Đang kiểm tra…", async () => {
      try {
        const data = await post("/api/auth/register/verify", { phone: state.phone, otp });
        state.token = data.token;
        $("verifiedPhone").textContent = data.phone;
        $("verifiedName").textContent = data.full_name;
        clearInterval(state.resendTimer);
        showStep(3);
        msg("ok", "Xác thực số điện thoại thành công. Hãy điền thông tin tài khoản.");
        $("regEmail").focus();
      } catch (err) {
        msg("bad", err.message);
        boxes.forEach((b) => (b.value = ""));
        boxes[0].focus();
        if (/gửi mã mới|hết hạn|bị hủy/.test(err.message)) startResendCountdown(0);
      }
    });
  });

  $("btnResend").addEventListener("click", () =>
    busy($("btnResend"), "Đang gửi lại…", () => sendOtp().catch((err) => msg("bad", err.message))));
  $("btnChangePhone").addEventListener("click", () => {
    clearInterval(state.resendTimer);
    showStep(1);
    msg("info", "Nhập lại số điện thoại và họ tên.");
    $("regPhone").focus();
  });

  // ---------------- bước 3: hoàn tất ----------------
  document.querySelectorAll("[data-toggle]").forEach((t) => t.addEventListener("click", () => {
    const input = $(t.dataset.toggle), show = input.type === "password";
    [input, $("regPassword2")].forEach((x) => (x.type = show ? "text" : "password"));
    t.setAttribute("aria-pressed", String(show));
    t.setAttribute("aria-label", show ? "Ẩn mật khẩu" : "Hiện mật khẩu");
    t.querySelector(".eye-open").toggleAttribute("hidden", show);
    t.querySelector(".eye-closed").toggleAttribute("hidden", !show);
  }));

  $("step3").addEventListener("submit", (e) => {
    e.preventDefault();
    const email = $("regEmail").value.trim().toLowerCase();
    const address = $("regAddress").value.trim().replace(/\s+/g, " ");
    const password = $("regPassword").value;
    if (!GMAIL.test(email)) { msg("bad", "Email phải là địa chỉ @gmail.com hợp lệ."); $("regEmail").focus(); return; }
    if (address.length < 5) { msg("bad", "Nhập địa chỉ nhà (ít nhất 5 ký tự)."); $("regAddress").focus(); return; }
    if (password.length < 6) { msg("bad", "Mật khẩu phải có ít nhất 6 ký tự."); $("regPassword").focus(); return; }
    if (password !== $("regPassword2").value) { msg("bad", "Mật khẩu nhập lại không khớp."); $("regPassword2").focus(); return; }
    busy($("btnRegister"), "Đang tạo tài khoản…", async () => {
      try {
        const user = await post("/api/auth/register", { token: state.token, email, address, password });
        msg("ok", `Đăng ký thành công! Đang chuyển tới trang đăng nhập…`);
        $("step3").hidden = true;
        setTimeout(() => location.replace(`login.html?registered=${encodeURIComponent(user.email)}`), 1500);
      } catch (err) {
        msg("bad", err.message);
        if (/hết hạn/.test(err.message)) { showStep(1); }
      }
    });
  });

  showStep(1);
})();
