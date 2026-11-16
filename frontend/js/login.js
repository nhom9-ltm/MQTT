/* Trang đăng nhập: kiểm tra định dạng tại chỗ, gọi API rồi chuyển trang theo vai trò. */
(() => {
  const INVALID = "Email hoặc mật khẩu không đúng";
  const GMAIL = /^[a-z0-9._%+-]+@gmail\.com$/;
  const $ = (id) => document.getElementById(id);
  const el = { form: $("loginForm"), email: $("email"), password: $("password"), error: $("loginError"), submit: $("btnLogin") };

  if (Session.token() && Session.user()) { location.replace(Session.homeOf(Session.user())); return; }

  // Nút con mắt: bấm để xem/ẩn mật khẩu
  const toggle = $("btnTogglePassword");
  toggle.addEventListener("click", () => {
    const show = el.password.type === "password";
    el.password.type = show ? "text" : "password";
    toggle.setAttribute("aria-pressed", String(show));
    toggle.querySelector(".eye-open").toggleAttribute("hidden", show);
    toggle.querySelector(".eye-closed").toggleAttribute("hidden", !show);
    toggle.setAttribute("aria-label", show ? "Ẩn mật khẩu" : "Hiện mật khẩu");
    el.password.focus();
  });

  function showError(text) {
    $("loginInfo").hidden = true;
    el.error.textContent = text;
    el.error.hidden = false;
  }

  // Vừa đăng ký xong (register.html chuyển sang với ?registered=<email>): điền sẵn email và báo thành công
  const registered = new URLSearchParams(location.search).get("registered");
  if (registered) {
    el.email.value = registered;
    $("loginInfo").textContent = `Đăng ký thành công tài khoản ${registered}. Hãy nhập mật khẩu để đăng nhập.`;
    $("loginInfo").hidden = false;
    el.password.focus();
  }

  el.form.addEventListener("submit", async (e) => {
    e.preventDefault();
    el.error.hidden = true;
    const email = el.email.value.trim().toLowerCase();
    const password = el.password.value;
    if (!GMAIL.test(email) || !password) { showError(INVALID); return; }

    el.submit.disabled = true;
    el.submit.textContent = "Đang đăng nhập…";
    try {
      const r = await Session.api("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (r.ok) {
        const data = await r.json();
        Session.save(data);
        location.replace(Session.homeOf(data.user));
        return;
      }
      if (r.status === 401) showError(INVALID);
      else if (r.status === 503) showError("Database chưa sẵn sàng. Hãy bật Docker rồi chạy: docker compose up -d database");
      else showError(`Máy chủ trả lỗi ${r.status}. Kiểm tra backend/run_api.py đã chạy chưa.`);
    } catch {
      showError("Không kết nối được máy chủ. Hãy chạy: python backend/run_api.py");
    }
    el.submit.disabled = false;
    el.submit.textContent = "Đăng nhập";
  });
})();
