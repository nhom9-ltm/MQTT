/* Trang người dùng → Thiết bị: nút "Kết nối thiết bị". Người dùng nhập mã thiết bị do quản trị viên tạo; API so mã với
 * các thiết bị thuộc địa chỉ nhà của người dùng (POST /api/devices/connect) và báo thành công / lý do thất bại. */
(() => {
  const $ = (id) => document.getElementById(id);
  const dlg = $("connectDialog");
  if (!dlg || !window.Session) return;
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function msg(kind, text) {
    const m = $("connectMsg");
    m.className = "form-msg " + kind;
    m.textContent = text;
    m.hidden = !text;
  }

  async function request(path, options) {
    let r;
    try { r = await Session.api(path, options); }
    catch { throw new Error("Không kết nối được máy chủ. Hãy chạy: python backend/run_api.py"); }
    if (r.status === 401) { Session.toLogin(); throw new Error("Hết phiên đăng nhập"); }
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Máy chủ trả lỗi ${r.status}`);
    return data;
  }

  async function loadConnected() {
    try {
      const list = await request("/api/devices/mine");
      $("connectedCount").textContent = `(${list.length})`;
      $("connectedList").innerHTML = list.length
        ? list.map((d) => `<li><b>${esc(d.name)}</b> <code>${esc(d.key)}</code><span class="muted"> · ${esc(d.room_name)}</span></li>`).join("")
        : '<li class="muted">Chưa kết nối thiết bị nào.</li>';
    } catch (err) {
      $("connectedList").innerHTML = `<li class="muted">${esc(err.message)}</li>`;
    }
  }

  $("btnConnectDevice").addEventListener("click", () => {
    msg("", "");
    $("connectCode").value = "";
    dlg.showModal();
    $("connectCode").focus();
    loadConnected();
  });
  $("btnConnectClose").addEventListener("click", () => dlg.close());

  $("connectForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const code = $("connectCode").value.trim();
    if (!code) { msg("bad", "Nhập mã thiết bị."); $("connectCode").focus(); return; }
    const btn = $("btnConnectSubmit");
    btn.disabled = true;
    btn.textContent = "Đang kiểm tra…";
    try {
      const d = await request("/api/devices/connect", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }),
      });
      msg("ok", `Kết nối thiết bị thành công: ${d.name} (${d.key}) · ${d.room_name}. Thiết bị đã được thêm vào danh sách.`);
      $("connectCode").value = "";
      loadConnected();
      if (window.SmartHomeApp && SmartHomeApp.refreshMyDevices) SmartHomeApp.refreshMyDevices();   // hiện thẻ ngay
    } catch (err) {
      msg("bad", err.message);
      $("connectCode").select();
    }
    btn.disabled = false;
    btn.textContent = "Kết nối";
  });
})();
