/* Đăng nhập broker khi bật xác thực (xem docs/MO_RONG.md, mục 2).
 * Không có gì thay đổi nếu broker cho anonymous: file này chỉ thêm username/password vào
 * mqtt.connect() khi có tài khoản.
 *
 * Cách đưa tài khoản (lưu trong sessionStorage, đóng tab là mất):
 *   http://localhost:8080/?user=dashboard&pass=MẬT_KHẨU
 * Mật khẩu bị xóa khỏi thanh địa chỉ ngay sau khi đọc.
 */
(() => {
  const qs = new URLSearchParams(location.search);
  if (qs.has("user")) {
    sessionStorage.setItem("mqtt_user", qs.get("user"));
    sessionStorage.setItem("mqtt_pass", qs.get("pass") || "");
    qs.delete("user"); qs.delete("pass");
    const rest = qs.toString();
    history.replaceState(null, "", location.pathname + (rest ? "?" + rest : "") + location.hash);
  }

  const user = sessionStorage.getItem("mqtt_user");
  if (!user || typeof mqtt === "undefined") return;

  // mqtt.connect có thể là thuộc tính chỉ đọc, nên thay cả đối tượng thay vì gán đè
  const orig = mqtt;
  window.mqtt = Object.assign({}, orig, {
    connect: (url, opts = {}) =>
      orig.connect(url, { ...opts, username: user, password: sessionStorage.getItem("mqtt_pass") || "" }),
  });
})();
