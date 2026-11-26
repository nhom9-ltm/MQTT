/* =========================================================
 *  API giả lập trong trình duyệt — cho bản công khai trên GitHub Pages (không có máy chủ Python).
 *
 *  Trả lời đúng các đường dẫn và đúng định dạng JSON như backend/run_api.py:
 *    /api/auth/*      đăng nhập, đăng ký (OTP giả), phiên        (backend/controllers/auth_controller.py)
 *    /api/devices/*   người dùng kết nối thiết bị                (backend/controllers/user_device_controller.py)
 *    /api/admin/*     trang quản trị: tài khoản, thiết bị, luật  (backend/controllers/admin_controller.py)
 *    /api/summary, /climate, /energy, /energy/report, /commands, /alerts   trang Lịch sử (api_controller.py)
 *
 *  Dữ liệu (tài khoản, thiết bị, luật…) lưu trong localStorage của trình duyệt: mỗi người xem có một bản riêng,
 *  không gửi đi đâu. Số liệu lịch sử được sinh tự động (giống backend/database/seed_history.py) theo giờ hiện tại.
 *  Luật, kịch bản, biểu giá điện đọc từ mock/data/*.json (workflow GitHub Pages chép từ backend/config/);
 *  thiếu file thì dùng bản dự phòng bên dưới.
 *
 *  js/session.js quyết định khi nào dùng file này (Session.mock): bản trên github.io, hoặc mở trang với ?mockapi=1.
 *  Thêm ?mockapi=0 để quay về API thật; ?mockreset=1 để xóa dữ liệu giả và nạp lại dữ liệu mẫu.
 * ========================================================= */
(() => {
  "use strict";

  const KEY = "sh.mockdb.v1";
  const SESSION_HOURS = 8;
  const GMAIL = /^[a-z0-9._%+-]+@gmail\.com$/;
  const OTP_TTL = 300, RESEND_GAP = 30, MAX_ATTEMPTS = 5, TOKEN_TTL = 900, MIN_PASSWORD = 6;
  const MODES = { home: "Ở nhà", away: "Vắng nhà", night: "Ban đêm" };

  // ---------------- dữ liệu mẫu (giống backend/database/seed.py) ----------------
  const DEFAULT_HOUSE = "Số 1 Đường Demo, Quận 1, TP. Hồ Chí Minh";
  const ROLES = [["admin", "Quản trị viên"], ["user", "Người dùng"]];
  const ROLE_PERMISSIONS = {
    admin: ["Vào trang quản trị", "Quản lý thiết bị, luật tự động", "Quản lý tài khoản và vai trò",
      "Xem thông báo, lịch sử đăng nhập", "Dùng bảng điều khiển nhà"],
    user: ["Dùng bảng điều khiển nhà", "Xem và điều khiển thiết bị", "Chạy kịch bản, đổi chế độ nhà, bật/tắt luật",
      "Xem thông báo và lịch sử"],
  };
  const USERS = [
    // email, mật khẩu, họ tên, vai trò, SĐT, gắn nhà mẫu?
    ["admmqtt@gmail.com", "Admin@1", "Quản trị viên", "admin", null, false],
    ["user1@gmail.com", "User@1", "Người dùng 1", "user", "0900000001", true],
  ];
  const ROOMS = [["living", "Phòng khách"], ["bedroom", "Phòng ngủ"], ["kitchen", "Nhà bếp"], ["entrance", "Lối vào"], ["lab", "Lab (ESP32)"]];
  const TYPES = [["climate", "Nhiệt độ & độ ẩm"], ["light", "Đèn"], ["fan", "Quạt"], ["ac", "Điều hòa"], ["curtain", "Rèm"],
    ["plug", "Ổ cắm"], ["lock", "Khóa cửa"], ["door", "Cảm biến cửa"], ["motion", "Cảm biến chuyển động"],
    ["gas", "Cảm biến gas"], ["node", "Bo mạch"]];
  const DEVICES = [
    ["living", "climate", "Nhiệt độ & độ ẩm", "climate", true], ["living", "light", "Đèn trần", "light", true],
    ["living", "fan", "Quạt đứng", "fan", true], ["living", "ac", "Điều hòa", "ac", true],
    ["living", "curtain", "Rèm cửa sổ", "curtain", true], ["living", "tv-plug", "Ổ cắm TV", "plug", true],
    ["living", "motion", "Cảm biến chuyển động", "motion", true],
    ["bedroom", "climate", "Nhiệt độ & độ ẩm", "climate", true], ["bedroom", "light", "Đèn ngủ", "light", true],
    ["bedroom", "ac", "Điều hòa", "ac", true], ["bedroom", "curtain", "Rèm cửa sổ", "curtain", true],
    ["kitchen", "climate", "Nhiệt độ & độ ẩm", "climate", true], ["kitchen", "light", "Đèn bếp", "light", true],
    ["kitchen", "hood-fan", "Quạt hút mùi", "fan", true], ["kitchen", "stove-plug", "Bếp điện", "plug", true],
    ["kitchen", "gas", "Cảm biến khí gas", "gas", true],
    ["entrance", "lock", "Khóa cửa chính", "lock", true], ["entrance", "door", "Cảm biến cửa chính", "door", true],
    ["entrance", "motion", "Cảm biến chuyển động", "motion", true], ["entrance", "porch-light", "Đèn hiên", "light", true],
    ["lab", "esp32-01", "Bo mạch ESP32", "node", false], ["lab", "climate", "DHT22", "climate", false],
    ["lab", "light", "Relay đèn", "light", false], ["lab", "fan", "Relay quạt", "fan", false],
    ["lab", "motion", "PIR", "motion", false], ["lab", "door", "Công tắc từ", "door", false], ["lab", "gas", "MQ-2", "gas", false],
  ];
  // Dự phòng khi không đọc được mock/data/energy.json (giống backend/config/energy.json)
  const ENERGY_FALLBACK = {
    _note: "Giá bán lẻ điện sinh hoạt bậc thang của EVN (đồng/kWh, CHƯA gồm VAT), áp dụng từ 10/5/2025.",
    tiers: [{ up_to: 50, price: 1984 }, { up_to: 100, price: 2050 }, { up_to: 200, price: 2380 },
      { up_to: 300, price: 2998 }, { up_to: 400, price: 3350 }, { up_to: null, price: 3460 }],
    vat: 0.08, budget_vnd: 1000000, warn_ratio: 0.8,
  };

  // ---------------- tiện ích ----------------
  class HttpError extends Error {
    constructor(status, detail) { super(detail); this.status = status; }
  }
  const bad = (detail) => new HttpError(400, detail);
  const notFound = (detail) => new HttpError(404, detail);
  const iso = (ms) => new Date(ms).toISOString();
  const now = () => Date.now();
  const has = (obj, k) => Object.prototype.hasOwnProperty.call(obj, k);
  const lower = (s) => String(s ?? "").trim().toLowerCase();
  const normAddr = (a) => String(a ?? "").replace(/\s+/g, " ").trim();

  function randomToken(bytes = 24) {
    const a = new Uint8Array(bytes);
    crypto.getRandomValues(a);
    return btoa(String.fromCharCode(...a)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  async function sha256(text) {
    if (!crypto.subtle) return "plain:" + text;      // trang http qua IP LAN không có crypto.subtle
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }
  function cleanPhone(value) {
    let phone = String(value ?? "").replace(/[\s.-]/g, "");
    if (!phone) return null;
    if (phone.startsWith("+84")) phone = "0" + phone.slice(3);
    if (!/^0\d{9}$/.test(phone)) throw bad("Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0 (vd 0901234567)");
    return phone;
  }

  // ---------------- "database" trong localStorage ----------------
  let db = null;
  const store = {
    load() { try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; } },
    save() { try { localStorage.setItem(KEY, JSON.stringify(db)); } catch { /* chế độ ẩn danh: chỉ giữ trong bộ nhớ */ } },
  };

  async function seed() {
    const t = iso(now());
    const d = { v: 1, seq: { user: 0, device: 0, house: 1, login: 0 }, roles: {}, houses: [{ id: 1, address: DEFAULT_HOUSE }],
      users: [], devices: [], userDevices: [], sessions: {}, logins: [], otps: {}, tickets: {}, rules: null };
    for (const [code, name] of ROLES) d.roles[code] = name;
    for (const [email, pw, name, role, phone, inHouse] of USERS) {
      d.users.push({ id: ++d.seq.user, email, password_hash: await sha256(pw), full_name: name, role, is_active: true,
        created_at: t, last_login_at: null, phone, house_id: inHouse ? 1 : null, deleted_at: null });
    }
    for (const [room, code, name, type, sim] of DEVICES) {
      d.devices.push({ id: ++d.seq.device, room, code, name, type, is_simulated: sim, is_active: true,
        created_by: null, created_at: t, house_id: 1 });
    }
    // user1 đã kết nối sẵn mọi thiết bị của nhà mẫu (giống seed.py)
    const u1 = d.users.find((u) => u.email === "user1@gmail.com");
    for (const dev of d.devices) d.userDevices.push({ user_id: u1.id, device_id: dev.id, connected_at: t });
    return d;
  }

  // Luật, kịch bản, biểu giá: ưu tiên file chép từ backend/config (mock/data), thiếu thì dùng bản của chế độ Demo
  async function readJson(path) {
    try {
      const r = await fetch(path, { cache: "no-store" });
      return r.ok ? await r.json() : null;
    } catch { return null; }
  }
  let scenesCache = null, energyCfg = null;
  async function loadConfig() {
    const [rules, scenes, energy] = await Promise.all(
      ["mock/data/rules.json", "mock/data/scenes.json", "mock/data/energy.json"].map(readJson));
    const Demo = window.SmartHomeDemo;
    scenesCache = scenes || (Demo && Demo.SCENES) || [];
    energyCfg = energy || ENERGY_FALLBACK;
    if (!db.rules) {
      db.rules = (rules || (Demo && Demo.RULES) || []).map((r) => ({ enabled: true, house_id: 1, ...r }));
      store.save();
    }
  }

  // Chỉ khởi tạo khi được gọi lần đầu: chạy với API thật thì file này không đọc/ghi gì
  let readyPromise = null;
  const ready = () => (readyPromise ||= (async () => {
    const qs = new URLSearchParams(location.search);
    if (qs.get("mockreset") === "1") try { localStorage.removeItem(KEY); } catch { /* bỏ qua */ }
    db = store.load();
    if (!db || db.v !== 1) { db = await seed(); store.save(); }
    await loadConfig();
  })());

  // ---------------- truy vấn ----------------
  const roomName = (code) => (ROOMS.find((r) => r[0] === code) || [, code])[1];
  const typeName = (code) => (TYPES.find((t) => t[0] === code) || [, code])[1];
  const houseOf = (id) => db.houses.find((h) => h.id === id);
  const liveUsers = () => db.users.filter((u) => !u.deleted_at);
  const userById = (id) => liveUsers().find((u) => u.id === id);

  function userRow(u) {
    return { id: u.id, email: u.email, full_name: u.full_name, role: u.role, role_name: db.roles[u.role], is_active: u.is_active,
      created_at: u.created_at, last_login_at: u.last_login_at, phone: u.phone, house_id: u.house_id,
      house_address: u.house_id ? houseOf(u.house_id)?.address ?? null : null };
  }
  const publicUser = (u) => ({ id: u.id, email: u.email, full_name: u.full_name, role: u.role });
  function deviceRow(d) {
    const by = d.created_by ? db.users.find((u) => u.id === d.created_by) : null;
    return { id: d.id, room: d.room, room_name: roomName(d.room), code: d.code, name: d.name, type: d.type,
      type_name: typeName(d.type), is_simulated: d.is_simulated, is_active: d.is_active, created_by: d.created_by,
      created_by_email: by ? by.email : null, created_at: d.created_at, house_id: d.house_id,
      house_address: houseOf(d.house_id)?.address ?? null, key: `${d.room}/${d.code}` };
  }
  function houseId(address) {
    const a = normAddr(address);
    const found = db.houses.find((h) => h.address.toLowerCase() === a.toLowerCase());
    if (found) return found.id;
    const h = { id: ++db.seq.house, address: a };
    db.houses.push(h);
    return h.id;
  }
  const emailTaken = (email, exceptId) => liveUsers().some((u) => u.email === email && u.id !== exceptId);
  const phoneTaken = (phone, exceptId) => liveUsers().some((u) => u.phone === phone && u.id !== exceptId);
  const activeAdmins = (exceptId) => liveUsers().filter((u) => u.role === "admin" && u.is_active && u.id !== exceptId).length;

  // ---------------- xác thực ----------------
  function currentUser(headers) {
    const auth = headers.Authorization || headers.authorization || "";
    const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
    const s = token && db.sessions[token];
    const u = s && s.expires > now() ? userById(s.user_id) : null;
    if (!u || !u.is_active) throw new HttpError(401, "Phiên đăng nhập không hợp lệ hoặc đã hết hạn");
    return u;
  }
  function requireAdmin(headers) {
    const u = currentUser(headers);
    if (u.role !== "admin") throw new HttpError(403, "Chỉ quản trị viên mới được truy cập");
    return u;
  }

  async function login(body) {
    const INVALID = "Email hoặc mật khẩu không đúng";
    const email = lower(body.email);
    if (email.length > 254 || !GMAIL.test(email)) throw new HttpError(401, INVALID);
    const u = liveUsers().find((x) => x.email === email);
    const ok = !!(u && u.is_active && u.password_hash === await sha256(String(body.password ?? "")));
    db.logins.push({ id: ++db.seq.login, email, user_id: u ? u.id : null, success: ok, ip_address: "trình duyệt (demo)", created_at: iso(now()) });
    if (!ok) throw new HttpError(401, INVALID);
    const token = randomToken(32);
    for (const [k, s] of Object.entries(db.sessions)) if (s.expires <= now()) delete db.sessions[k];
    db.sessions[token] = { user_id: u.id, expires: now() + SESSION_HOURS * 3600e3 };
    u.last_login_at = iso(now());
    return { token, user: publicUser(u) };
  }

  function cleanName(value) {
    const name = String(value ?? "").split(/\s+/).filter(Boolean).join(" ");
    if (name.length < 2 || name.length > 100) throw bad("Họ tên phải từ 2 đến 100 ký tự");
    return name;
  }
  function regPhone(value) {
    const phone = cleanPhone(value);
    if (!phone) throw bad("Nhập số điện thoại");
    return phone;
  }
  async function requestOtp(body) {
    const phone = regPhone(body.phone), name = cleanName(body.full_name);
    if (phoneTaken(phone)) throw bad(`Số điện thoại ${phone} đã được đăng ký. Hãy đăng nhập.`);
    const old = db.otps[phone], t = now();
    if (old && t - old.sent_at < RESEND_GAP * 1000) {
      throw new HttpError(429, `Vui lòng chờ ${Math.floor(RESEND_GAP - (t - old.sent_at) / 1000) + 1} giây rồi mới gửi lại mã`);
    }
    const code = String(Math.floor(Math.random() * 1e6)).padStart(6, "0");
    db.otps[phone] = { code_hash: await sha256(code), name, expires: t + OTP_TTL * 1000, sent_at: t, attempts: 0 };
    return { phone, expires_in: OTP_TTL, resend_after: RESEND_GAP, mock_sms: code };
  }
  async function verifyOtp(body) {
    const phone = regPhone(body.phone);
    const otp = String(body.otp ?? "").trim();
    if (!/^\d{6}$/.test(otp)) throw bad("Mã OTP gồm đúng 6 chữ số");
    const e = db.otps[phone];
    if (!e) throw bad("Chưa gửi mã cho số này hoặc mã đã bị hủy. Hãy bấm “Gửi mã OTP”.");
    if (now() > e.expires) { delete db.otps[phone]; throw bad("Mã OTP đã hết hạn. Hãy gửi mã mới."); }
    if (e.code_hash !== await sha256(otp)) {
      e.attempts++;
      const left = MAX_ATTEMPTS - e.attempts;
      if (left <= 0) { delete db.otps[phone]; throw bad("Nhập sai quá nhiều lần, mã đã bị hủy. Hãy gửi mã mới."); }
      throw bad(`Mã OTP không đúng. Còn ${left} lần thử.`);
    }
    delete db.otps[phone];
    const token = randomToken(24);
    db.tickets[token] = { phone, name: e.name, expires: now() + TOKEN_TTL * 1000 };
    return { token, phone, full_name: e.name, expires_in: TOKEN_TTL };
  }
  async function register(body) {
    const email = lower(body.email), address = normAddr(body.address), password = String(body.password ?? "");
    if (email.length > 254 || !GMAIL.test(email)) throw bad("Email phải là địa chỉ @gmail.com hợp lệ");
    if (address.length < 5 || address.length > 200) throw bad("Địa chỉ nhà phải từ 5 đến 200 ký tự");
    if (password.length < MIN_PASSWORD) throw bad(`Mật khẩu phải có ít nhất ${MIN_PASSWORD} ký tự`);
    const ticket = db.tickets[String(body.token ?? "")];
    if (!ticket || now() > ticket.expires) throw bad("Phiên đăng ký đã hết hạn. Hãy xác thực lại số điện thoại.");
    if (emailTaken(email)) throw bad(`Email ${email} đã có tài khoản. Hãy đăng nhập hoặc dùng email khác.`);
    if (phoneTaken(ticket.phone)) throw bad(`Số điện thoại ${ticket.phone} đã được đăng ký.`);
    const u = { id: ++db.seq.user, email, password_hash: await sha256(password), full_name: ticket.name, role: "user",
      is_active: true, created_at: iso(now()), last_login_at: null, phone: ticket.phone, house_id: houseId(address), deleted_at: null };
    db.users.push(u);
    delete db.tickets[String(body.token)];
    return { email: u.email, full_name: u.full_name, phone: u.phone, house_address: houseOf(u.house_id).address };
  }

  // ---------------- người dùng kết nối thiết bị ----------------
  const PUBLIC_DEVICE = ["id", "key", "code", "name", "room", "room_name", "type", "type_name", "is_active", "is_simulated", "house_address", "connected_at"];
  const pick = (obj, keys) => Object.fromEntries(keys.filter((k) => k in obj).map((k) => [k, obj[k]]));
  function myDevices(u) {
    return db.userDevices.filter((x) => x.user_id === u.id)
      .map((x) => ({ x, d: db.devices.find((d) => d.id === x.device_id) })).filter((p) => p.d)
      .sort((a, b) => b.x.connected_at.localeCompare(a.x.connected_at))
      .map(({ x, d }) => pick({ ...deviceRow(d), connected_at: x.connected_at }, PUBLIC_DEVICE));
  }
  function connectDevice(u, body) {
    const code = String(body.code ?? "").replace(/\s+/g, "").toLowerCase();
    if (!code) throw bad("Nhập mã thiết bị");
    if (code.length > 61) throw bad("Mã thiết bị quá dài");
    if (!u.house_id) throw bad("Tài khoản của bạn chưa có địa chỉ nhà nên chưa kết nối được thiết bị. Hãy liên hệ quản trị viên.");
    const found = db.devices.filter((d) => d.house_id === u.house_id && (d.code === code || `${d.room}/${d.code}` === code)).map(deviceRow);
    if (!found.length) throw bad(`Mã “${code}” không đúng hoặc không thuộc nhà của bạn. Kiểm tra lại mã quản trị viên đã cấp.`);
    if (found.length > 1) {
      throw bad(`Có ${found.length} thiết bị cùng mã “${code}” (${found.map((d) => d.key).join(", ")}). Hãy nhập đầy đủ dạng phòng/mã, vd ${found[0].key}.`);
    }
    const dev = found[0];
    if (!dev.is_active) throw bad(`Thiết bị “${dev.name}” đang bị quản trị viên khóa, chưa kết nối được.`);
    if (db.userDevices.some((x) => x.user_id === u.id && x.device_id === dev.id)) {
      throw bad(`Thiết bị “${dev.name}” (${dev.key}) đã được kết nối với tài khoản của bạn từ trước.`);
    }
    db.userDevices.push({ user_id: u.id, device_id: dev.id, connected_at: iso(now()) });
    return pick(dev, PUBLIC_DEVICE);
  }

  // ---------------- quản trị: tài khoản ----------------
  function resolveUserHouse(data, role) {
    if (role === "admin") return null;
    const address = normAddr(data.new_address);
    if (address) {
      if (address.length < 5 || address.length > 200) throw bad("Địa chỉ nhà phải từ 5 đến 200 ký tự");
      return houseId(address);
    }
    const id = Number.parseInt(data.house_id, 10);
    if (!Number.isFinite(id)) throw bad(role === undefined ? "Chọn địa chỉ nhà cho thiết bị" : "Tài khoản người dùng cần có địa chỉ nhà");
    if (!houseOf(id)) throw bad("Địa chỉ nhà không tồn tại");
    return id;
  }
  async function cleanUser(data, creating) {
    const email = lower(data.email), full_name = String(data.full_name ?? "").trim(), role = String(data.role ?? "").trim();
    const password = String(data.password || "");
    if (email.length > 254 || !GMAIL.test(email)) throw bad("Email phải là địa chỉ @gmail.com hợp lệ");
    if (full_name.length < 1 || full_name.length > 100) throw bad("Họ tên phải từ 1 đến 100 ký tự");
    if (!has(db.roles, role)) throw bad("Vai trò phải là admin hoặc user");
    if (creating && !password) throw bad("Cần nhập mật khẩu cho tài khoản mới");
    if (password && password.length < MIN_PASSWORD) throw bad(`Mật khẩu phải có ít nhất ${MIN_PASSWORD} ký tự`);
    return { email, full_name, role, is_active: data.is_active === undefined ? true : !!data.is_active,
      password_hash: password ? await sha256(password) : null };
  }
  function listUsers(q, role, status) {
    q = lower(q);
    return liveUsers().map(userRow).filter((u) =>
      (!q || [u.email, u.full_name, u.phone, u.house_address].some((v) => v && v.toLowerCase().includes(q))) &&
      (!has(db.roles, role) || u.role === role) &&
      (!["active", "locked"].includes(status) || u.is_active === (status === "active")));
  }
  async function createUser(data) {
    const c = await cleanUser(data, true);
    const phone = cleanPhone(data.phone);
    if (emailTaken(c.email)) throw bad(`Email ${c.email} đã có tài khoản`);
    if (phone && phoneTaken(phone)) throw bad(`Số điện thoại ${phone} đã được dùng cho tài khoản khác`);
    const house_id = resolveUserHouse(data, c.role);
    const u = { id: ++db.seq.user, email: c.email, password_hash: c.password_hash, full_name: c.full_name, role: c.role,
      is_active: c.is_active, created_at: iso(now()), last_login_at: null, phone, house_id, deleted_at: null };
    db.users.push(u);
    return userRow(u);
  }
  function getUser(id) {
    const u = userById(id);
    if (!u) throw notFound("Không tìm thấy tài khoản");
    return u;
  }
  function dropSessions(userId) {
    for (const [k, s] of Object.entries(db.sessions)) if (s.user_id === userId) delete db.sessions[k];
  }
  async function updateUser(id, data, admin) {
    const u = getUser(id);
    const c = await cleanUser(data, false);
    const phone = cleanPhone("phone" in data ? data.phone : u.phone);
    if (phone && phoneTaken(phone, id)) throw bad(`Số điện thoại ${phone} đã được dùng cho tài khoản khác`);
    const house_id = resolveUserHouse({ house_id: u.house_id, ...data }, c.role);
    if (emailTaken(c.email, id)) throw bad(`Email ${c.email} đã có tài khoản`);
    if (id === admin.id && (c.role !== "admin" || !c.is_active)) throw bad("Không thể tự hạ quyền hoặc tự khóa tài khoản đang đăng nhập");
    if (u.role === "admin" && u.is_active && (c.role !== "admin" || !c.is_active) && activeAdmins(id) === 0) {
      throw bad("Phải còn ít nhất một quản trị viên đang hoạt động");
    }
    Object.assign(u, { email: c.email, full_name: c.full_name, role: c.role, is_active: c.is_active, phone, house_id });
    if (c.password_hash) u.password_hash = c.password_hash;
    if (!u.is_active) dropSessions(id);
    return userRow(u);
  }
  function setUserActive(id, active, admin) {
    const u = getUser(id);
    if (id === admin.id && !active) throw bad("Không thể tự khóa tài khoản đang đăng nhập");
    if (u.role === "admin" && u.is_active && !active && activeAdmins(id) === 0) throw bad("Phải còn ít nhất một quản trị viên đang hoạt động");
    u.is_active = active;
    if (!active) dropSessions(id);
    return userRow(u);
  }
  function deleteUser(id, admin) {
    const u = getUser(id);
    if (id === admin.id) throw bad("Không thể xóa tài khoản đang đăng nhập");
    if (u.role === "admin" && u.is_active && activeAdmins(id) === 0) throw bad("Phải còn ít nhất một quản trị viên đang hoạt động");
    u.deleted_at = iso(now());
    u.is_active = false;
    dropSessions(id);
  }
  function listRoles() {
    return ROLES.map(([code]) => {
      const us = liveUsers().filter((u) => u.role === code);
      return { code, name: db.roles[code], users_total: us.length, users_active: us.filter((u) => u.is_active).length,
        permissions: ROLE_PERMISSIONS[code] };
    });
  }
  function renameRole(code, name) {
    name = String(name ?? "").trim();
    if (name.length < 1 || name.length > 50) throw bad("Tên vai trò phải từ 1 đến 50 ký tự");
    if (!has(db.roles, code)) throw notFound("Không tìm thấy vai trò");
    db.roles[code] = name;
    return listRoles().find((r) => r.code === code);
  }

  // ---------------- quản trị: thiết bị ----------------
  function cleanDevice(data) {
    const room = String(data.room ?? "").trim(), code = lower(data.code), name = String(data.name ?? "").trim(), type = String(data.type ?? "").trim();
    if (!ROOMS.some((r) => r[0] === room)) throw bad("Phòng không tồn tại");
    if (!/^[a-z0-9-]{1,30}$/.test(code)) throw bad("Mã thiết bị chỉ gồm chữ thường không dấu, số và dấu gạch ngang (1–30 ký tự)");
    if (name.length < 1 || name.length > 100) throw bad("Tên thiết bị phải từ 1 đến 100 ký tự");
    if (!TYPES.some((t) => t[0] === type)) throw bad("Loại thiết bị không hợp lệ");
    return { room, code, name, type, is_simulated: !!data.is_simulated, is_active: data.is_active === undefined ? true : !!data.is_active };
  }
  function rulesUsing(key) {
    const mentions = (o) => Array.isArray(o) ? o.some(mentions)
      : o && typeof o === "object" ? o.device === key || (o.except || []).includes(key) || Object.values(o).some(mentions) : false;
    return db.rules.filter(mentions).map((r) => r.name);
  }
  function getDevice(id) {
    const d = db.devices.find((x) => x.id === id);
    if (!d) throw notFound("Không tìm thấy thiết bị");
    return d;
  }
  const deviceHouse = (data) => resolveUserHouse(data, undefined);
  function deviceDetail(id) {
    const d = getDevice(id);
    const connected = db.userDevices.filter((x) => x.device_id === id).map((x) => ({ u: userById(x.user_id), at: x.connected_at }))
      .filter((p) => p.u).sort((a, b) => a.at.localeCompare(b.at))
      .map(({ u, at }) => ({ id: u.id, email: u.email, full_name: u.full_name, connected_at: at }));
    return { ...deviceRow(d), connected_users: connected };
  }
  function createDevice(data, admin) {
    const c = cleanDevice(data);
    if (db.devices.some((d) => d.room === c.room && d.code === c.code)) {
      throw bad(`Thiết bị ${c.room}/${c.code} đã được đăng ký (topic MQTT dùng chung cho mọi nhà)`);
    }
    const d = { id: ++db.seq.device, ...c, created_by: admin.id, created_at: iso(now()), house_id: deviceHouse(data) };
    db.devices.push(d);
    return deviceRow(d);
  }
  function updateDevice(id, data) {
    const d = getDevice(id);
    const c = cleanDevice({ is_active: d.is_active, ...data });
    const oldKey = `${d.room}/${d.code}`, newKey = `${c.room}/${c.code}`;
    const other = db.devices.find((x) => x.room === c.room && x.code === c.code);
    if (other && other.id !== id) throw bad(`Thiết bị ${newKey} đã được đăng ký`);
    const house_id = deviceHouse({ house_id: d.house_id, ...data });
    if (newKey !== oldKey || house_id !== d.house_id) {
      const used = rulesUsing(oldKey);
      if (used.length) throw bad(`Không đổi được phòng/mã/địa chỉ nhà vì luật đang dùng ${oldKey}: ${used.join(", ")}`);
    }
    Object.assign(d, c, { house_id });
    return deviceRow(d);
  }
  function deleteDevice(id) {
    const d = getDevice(id), key = `${d.room}/${d.code}`;
    const used = rulesUsing(key);
    if (used.length) throw bad(`Không xóa được vì luật đang dùng ${key}: ${used.join(", ")}. Sửa hoặc xóa các luật đó trước.`);
    db.devices = db.devices.filter((x) => x.id !== id);
    db.userDevices = db.userDevices.filter((x) => x.device_id !== id);
  }
  function listHouses() {
    return db.houses.map((h) => {
      const us = liveUsers().filter((u) => u.house_id === h.id);
      const owners = us.filter((u) => u.role === "user").map((u) => u.full_name).join(", ");
      return { id: h.id, address: h.address, devices: db.devices.filter((d) => d.house_id === h.id).length,
        users: us.length, owners: owners || null };
    });
  }

  // ---------------- quản trị: luật (kiểm tra rút gọn so với backend/services/rule_validation.py) ----------------
  function validateRule(data) {
    if (!data || typeof data !== "object") throw bad("Dữ liệu luật không hợp lệ");
    const id = String(data.id ?? "").trim(), name = String(data.name ?? "").trim();
    if (!/^[a-z0-9_]{2,50}$/.test(id)) throw bad("Mã luật chỉ gồm chữ thường không dấu, số và dấu gạch dưới (2–50 ký tự)");
    if (name.length < 1 || name.length > 150) throw bad("Tên luật phải từ 1 đến 150 ký tự");
    const conditions = data.conditions || [], actions = data.actions || [];
    if (!Array.isArray(conditions)) throw bad("Điều kiện phải là danh sách");
    if (!Array.isArray(actions) || !actions.length) throw bad("Luật phải có ít nhất một hành động");
    const house_id = Number(data.house_id);
    if (!Number.isInteger(house_id) || !houseOf(house_id)) throw bad("Chọn địa chỉ nhà cho luật");
    if (!data.trigger || typeof data.trigger !== "object") throw bad("Thiếu điều kiện kích hoạt (trigger)");
    const keys = new Set(db.devices.filter((d) => d.house_id === house_id).map((d) => `${d.room}/${d.code}`));
    const check = (o, where) => {
      if (o && typeof o === "object" && typeof o.device === "string" && !keys.has(o.device)) {
        throw bad(`${where}: thiết bị “${o.device}” chưa được đăng ký ở địa chỉ nhà này`);
      }
    };
    check(data.trigger, "Kích hoạt");
    conditions.forEach((c, i) => check(c, `Điều kiện ${i + 1}`));
    actions.forEach((a, i) => {
      check(a, `Hành động ${i + 1}`);
      if (a && a.scene && !scenesCache.some((s) => s.id === a.scene)) throw bad(`Hành động ${i + 1}: không có kịch bản “${a.scene}”`);
      if (a && a.mode && !has(MODES, a.mode)) throw bad(`Hành động ${i + 1}: chế độ phải thuộc ${Object.keys(MODES).join(", ")}`);
    });
    const rule = { id, name, description: String(data.description ?? "").trim().slice(0, 300), enabled: data.enabled === undefined ? true : !!data.enabled,
      house_id, trigger: data.trigger };
    if (conditions.length) rule.conditions = conditions;
    rule.actions = actions;
    const cd = data.cooldown;
    if (![undefined, null, 0, ""].includes(cd)) {
      if (!Number.isInteger(cd) || cd <= 0 || cd > 86400) throw bad("Thời gian nghỉ giữa 2 lần chạy phải từ 1 đến 86400 giây");
      rule.cooldown = cd;
    }
    return rule;
  }
  function ruleIndex(id) {
    const i = db.rules.findIndex((r) => r.id === id);
    if (i < 0) throw notFound("Không tìm thấy luật");
    return i;
  }

  // =========================================================
  //  Số liệu lịch sử sinh tự động (giống backend/database/seed_history.py), ổn định theo thời gian:
  //  cùng một giờ luôn ra cùng số liệu nên tải lại trang không bị "nhảy".
  // =========================================================
  const HOUR = 3600e3, DAY = 24 * HOUR, DATA_DAYS = 70;
  const CLIMATE_ROOMS = { living: 27, bedroom: 26, kitchen: 29, lab: 28 };
  const LOADS = [["living/tv-plug", 90], ["kitchen/stove-plug", 1500], ["living/ac", 900], ["living/light", 18], ["bedroom/light", 12]];
  const CMD_DEVICES = ["living/light", "living/ac", "bedroom/light", "kitchen/hood-fan", "entrance/lock"];
  const SOURCES = [["dashboard", 5], ["automation", 3], ["esp32-button", 1], ["scene:away", 1], ["scene:sleep", 1]];
  const ALERTS = [
    ["critical", "Phát hiện khí gas 1146 ppm ở nhà bếp! Đã ngắt bếp điện và bật quạt hút (dữ liệu mẫu)"],
    ["info", "Phòng khách 31.4°C — đã bật điều hòa 26°C"],
    ["warn", "23:00 — cửa chính chưa khóa, đã tự động khóa"],
    ["info", "Phòng khách không có người 2 phút — đã tắt đèn và quạt"],
  ];

  function rng(seedNum) {            // mulberry32
    let a = seedNum >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const hashStr = (s) => [...s].reduce((h, c) => Math.imul(h ^ c.charCodeAt(0), 16777619), 2166136261) >>> 0;
  const pad = (n) => String(n).padStart(2, "0");
  const dayStr = (ms) => { const d = new Date(ms); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
  const dataStart = () => Math.floor((now() - DATA_DAYS * DAY) / HOUR) * HOUR;
  const lastHour = () => Math.floor(now() / HOUR) * HOUR;            // giờ đang chạy chưa tính (logger chưa đủ giờ)

  // Công suất trung bình (W) của một thiết bị trong một giờ: 6 mẫu 10 phút, tối 18–23h bật nhiều hơn
  function avgPower(key, watt, hourMs) {
    const r = rng(hashStr(key) ^ (hourMs / HOUR));
    const h = new Date(hourMs).getHours();
    const pOn = h >= 18 && h <= 23 ? 0.6 : 0.15;
    let sum = 0;
    for (let i = 0; i < 6; i++) sum += r() < pOn ? watt * (0.9 + 0.2 * r()) : 0;
    return sum / 6;
  }
  // [{day, device, kwh}] gom theo ngày và thiết bị trong [from, to)
  function usage(from, to) {
    const out = new Map();
    for (let h = Math.max(from, dataStart()); h < Math.min(to, lastHour()); h += HOUR) {
      const day = dayStr(h);
      for (const [key, watt] of LOADS) {
        const k = day + "|" + key;
        out.set(k, (out.get(k) || 0) + avgPower(key, watt, h) / 1000);
      }
    }
    return [...out].map(([k, kwh]) => { const [day, device] = k.split("|"); return { day, device, kwh }; });
  }
  const round = (v, n = 3) => Math.round(v * 10 ** n) / 10 ** n;

  function climateAt(room, t) {
    const hour = new Date(t).getHours() + new Date(t).getMinutes() / 60;
    const daily = Math.sin((hour - 9) / 24 * 2 * Math.PI);           // nóng nhất ~15h
    const r = rng(hashStr(room) ^ Math.floor(t / 60000));
    return { temperature: round(CLIMATE_ROOMS[room] + 3 * daily + (r() - 0.5) * 0.8, 1),
      humidity: round(65 - 8 * daily + (r() - 0.5) * 4, 1) };
  }

  // Lệnh và cảnh báo: sinh theo từng giờ / ngày bằng số ngẫu nhiên có hạt giống cố định
  function commandsIn(from, to) {
    const out = [];
    for (let h = Math.max(Math.floor(from / HOUR) * HOUR, dataStart()); h < to; h += HOUR) {
      const r = rng(0xc0ffee ^ (h / HOUR));
      const hr = new Date(h).getHours();
      const n = Math.floor(r() * (hr >= 18 && hr <= 23 ? 5 : 1.5));
      for (let i = 0; i < n; i++) {
        const t = h + Math.floor(r() * HOUR);
        if (t < from || t >= to || t > now()) continue;
        let w = r() * 11, source = SOURCES[0][0];
        for (const [s, weight] of SOURCES) { if ((w -= weight) < 0) { source = s; break; } }
        out.push({ t, device: CMD_DEVICES[Math.floor(r() * CMD_DEVICES.length)], source });
      }
    }
    return out;
  }
  function alertsIn(from, to) {
    const out = [];
    for (let d = Math.floor(Math.max(from, dataStart()) / DAY) * DAY; d < to; d += DAY) {
      const r = rng(0xa1e47 ^ (d / DAY));
      const n = 1 + Math.floor(r() * 3);
      for (let i = 0; i < n; i++) {
        const t = d + Math.floor(r() * DAY);
        const [level, text] = ALERTS[i === 0 && r() < 0.35 ? 0 : 1 + Math.floor(r() * 3)];
        if (t >= from && t < to && t <= now()) out.push({ t, level, text });
      }
    }
    return out.sort((a, b) => b.t - a.t);
  }

  const histHours = (q, def = 24) => Math.min(24 * 30, Math.max(1, Number.parseInt(q.get("hours") ?? def, 10) || def));
  function summary(hours) {
    const since = now() - hours * HOUR, start = dataStart();
    const samples = Math.floor((now() - start) / 600000) * (Object.keys(CLIMATE_ROOMS).length + LOADS.length);
    const cmdsAll = commandsIn(start, now() + 1), alertsAll = alertsIn(start, now() + 1);
    return {
      messages_total: samples + cmdsAll.length + alertsAll.length, first: start, last: now(),
      commands: cmdsAll.filter((c) => c.t > since).length,
      alerts: alertsAll.filter((a) => a.t > since && a.level === "critical").length,
      rooms: Object.keys(CLIMATE_ROOMS).sort(),
    };
  }
  function climate(room, hours) {
    if (!(room in CLIMATE_ROOMS)) return { room, bucket_ms: 60000, points: [] };
    const b = Math.max(60000, Math.floor(hours * HOUR / 120));
    const points = [];
    for (let t = Math.ceil((now() - hours * HOUR) / b) * b; t <= now(); t += b) points.push({ t, ...climateAt(room, t) });
    return { room, bucket_ms: b, points };
  }
  function energy(days) {
    const byDay = {}, byDev = {};
    for (const r of usage(now() - days * DAY, now())) {
      byDay[r.day] = (byDay[r.day] || 0) + r.kwh;
      byDev[r.device] = (byDev[r.device] || 0) + r.kwh;
    }
    return {
      by_day: Object.keys(byDay).sort().map((day) => ({ day, kwh: round(byDay[day]) })),
      by_device: Object.entries(byDev).filter(([, v]) => v > 0).map(([device, kwh]) => ({ device, kwh: round(kwh) }))
        .sort((a, b) => b.kwh - a.kwh),
    };
  }
  function commands(hours) {
    const list = commandsIn(now() - hours * HOUR, now() + 1);
    const count = (field) => Object.entries(list.reduce((m, c) => ((m[c[field]] = (m[c[field]] || 0) + 1), m), {}))
      .map(([k, n]) => ({ [field]: k, n })).sort((a, b) => b.n - a.n);
    return { by_source: count("source"), by_device: count("device").slice(0, 10) };
  }

  // ---------- tiền điện (giống backend/services/energy_service.py) ----------
  function bill(kwh, cfg) {
    const rows = [];
    let prev = 0, subtotal = 0;
    for (let i = 0; i < cfg.tiers.length; i++) {
      const upTo = cfg.tiers[i].up_to, price = cfg.tiers[i].price;
      const used = Math.max(0, Math.min(kwh - prev, upTo === null ? Infinity : upTo - prev));
      subtotal += used * price;
      rows.push({ tier: i + 1, from: prev, to: upTo, price, kwh: round(used), vnd: Math.round(used * price) });
      if (upTo === null || kwh <= upTo) break;
      prev = upTo;
    }
    const vat = subtotal * (cfg.vat || 0);
    return { kwh: round(kwh), subtotal: Math.round(subtotal), vat: Math.round(vat), total: Math.round(subtotal + vat), tiers: rows };
  }
  function budgetStatus(actual, projected, cfg) {
    const budget = cfg.budget_vnd || 0;
    if (!budget) return "off";
    if (actual >= budget) return "over";
    if ((projected !== null && projected >= budget) || actual >= budget * (cfg.warn_ratio ?? 0.8)) return "warn";
    return "ok";
  }
  function monthReport(month) {
    const cfg = energyCfg;
    const t = now();
    const cur = new Date(t);
    month = month || `${cur.getFullYear()}-${pad(cur.getMonth() + 1)}`;
    const m = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(month);
    if (!m) throw bad("month phải có dạng YYYY-MM");
    const start = new Date(+m[1], +m[2] - 1, 1).getTime(), end = new Date(+m[1], +m[2], 1).getTime();
    const rows = usage(start, end);
    const byDay = {}, byDev = {};
    for (const r of rows) {
      byDay[r.day] = (byDay[r.day] || 0) + r.kwh;
      byDev[r.device] = (byDev[r.device] || 0) + r.kwh;
    }
    const first = rows.length ? Math.max(start, dataStart()) : null;
    const kwh = Object.values(byDay).reduce((a, v) => a + v, 0);
    const actual = bill(kwh, cfg);
    const finished = t >= end;
    const covered = first !== null ? Math.min(t, end) - Math.max(start, first) : 0;
    let projected = null;
    if (finished) projected = { kwh: actual.kwh, total: actual.total };
    else if (covered >= HOUR) {
      const pk = kwh / covered * (end - start);
      projected = { kwh: round(pk), total: bill(pk, cfg).total };
    }
    let cum = 0;
    const days = Object.keys(byDay).sort().map((day) => {
      cum += byDay[day];
      return { day, kwh: round(byDay[day]), cum_kwh: round(cum), cum_vnd: bill(cum, cfg).total };
    });
    const devices = Object.entries(byDev).filter(([, v]) => v > 0).map(([device, v]) => ({ device, kwh: round(v),
      share: kwh ? round(v / kwh, 4) : 0, vnd: kwh ? Math.round(actual.total * v / kwh) : 0 })).sort((a, b) => b.kwh - a.kwh);
    const budget = cfg.budget_vnd || 0;
    return {
      month, start, end, finished, coverage: covered > 0 ? round(covered / (end - start), 4) : 0,
      kwh: actual.kwh, bill: actual, projected,
      budget: { vnd: budget, warn_ratio: cfg.warn_ratio ?? 0.8, used_ratio: budget ? round(actual.total / budget, 4) : null,
        status: budgetStatus(actual.total, projected && projected.total, cfg) },
      by_day: days, by_device: devices, price_note: cfg._note || "",
    };
  }

  // =========================================================
  //  Định tuyến
  // =========================================================
  async function route(method, url, body, headers) {
    const p = url.pathname, q = url.searchParams;
    let m;
    // ----- đăng nhập / đăng ký -----
    if (p === "/api/auth/login" && method === "POST") return login(body);
    if (p === "/api/auth/register/otp" && method === "POST") return requestOtp(body);
    if (p === "/api/auth/register/verify" && method === "POST") return verifyOtp(body);
    if (p === "/api/auth/register" && method === "POST") return st(201, await register(body));
    if (p === "/api/auth/me" && method === "GET") return publicUser(currentUser(headers));
    if (p === "/api/auth/logout" && method === "POST") {
      const auth = headers.Authorization || headers.authorization || "";
      delete db.sessions[auth.replace(/^Bearer /, "")];
      return st(204, null);
    }
    // ----- người dùng: thiết bị của tôi -----
    if (p === "/api/devices/mine" && method === "GET") return myDevices(currentUser(headers));
    if (p === "/api/devices/connect" && method === "POST") return st(201, connectDevice(currentUser(headers), body));
    // ----- lịch sử (backend không yêu cầu đăng nhập) -----
    if (p === "/api/summary") return summary(histHours(q));
    if (p === "/api/climate") return climate(q.get("room") || "", histHours(q));
    if (p === "/api/energy") return energy(Math.min(90, Math.max(1, Number.parseInt(q.get("days") ?? 7, 10) || 7)));
    if (p === "/api/energy/report") return monthReport(q.get("month"));
    if (p === "/api/commands") return commands(histHours(q));
    if (p === "/api/alerts") return alertsIn(dataStart(), now() + 1).slice(0, Math.min(200, Number.parseInt(q.get("limit") ?? 20, 10) || 20));

    // ----- quản trị -----
    if (!p.startsWith("/api/admin/")) throw notFound("Not Found");
    const admin = requireAdmin(headers);
    const path = p.slice("/api/admin".length);
    if (path === "/overview") {
      const day = now() - DAY;
      const recent = db.logins.filter((l) => Date.parse(l.created_at) > day);
      return { users_total: liveUsers().length, users_admin: liveUsers().filter((u) => u.role === "admin").length,
        rooms_total: ROOMS.length, devices_total: db.devices.length, devices_simulated: db.devices.filter((d) => d.is_simulated).length,
        rules_total: db.rules.length, scenes_total: scenesCache.length,
        sessions_active: Object.values(db.sessions).filter((s) => s.expires > now()).length,
        logins_ok_24h: recent.filter((l) => l.success).length, logins_failed_24h: recent.filter((l) => !l.success).length };
    }
    if (path === "/devices-by-room") {
      return ROOMS.map(([code, name]) => {
        const ds = db.devices.filter((d) => d.room === code);
        return { code, name, total: ds.length, simulated: ds.filter((d) => d.is_simulated).length };
      });
    }
    if (path === "/login-history") {
      const limit = Math.min(200, Math.max(1, Number.parseInt(q.get("limit") ?? 20, 10) || 20));
      return [...db.logins].reverse().slice(0, limit).map(({ id, email, success, ip_address, created_at }) => ({ id, email, success, ip_address, created_at }));
    }
    // tài khoản & vai trò
    if (path === "/users" && method === "GET") return listUsers(q.get("q") || "", q.get("role") || "", q.get("status") || "");
    if (path === "/users" && method === "POST") return st(201, await createUser(body));
    if ((m = /^\/users\/(\d+)\/active$/.exec(path)) && method === "PUT") return setUserActive(+m[1], !!body.is_active, admin);
    if ((m = /^\/users\/(\d+)$/.exec(path))) {
      if (method === "PUT") return updateUser(+m[1], body, admin);
      if (method === "DELETE") { deleteUser(+m[1], admin); return st(204, null); }
    }
    if (path === "/roles" && method === "GET") return listRoles();
    if ((m = /^\/roles\/([^/]+)$/.exec(path)) && method === "PUT") return renameRole(decodeURIComponent(m[1]), body.name);
    // thiết bị
    if (path === "/devices" && method === "GET") return db.devices.map(deviceRow);
    if (path === "/devices" && method === "POST") return st(201, createDevice(body, admin));
    if (path === "/device-options") return { rooms: ROOMS.map(([code, name]) => ({ code, name })),
      types: TYPES.map(([code, name]) => ({ code, name })).sort((a, b) => a.name.localeCompare(b.name, "vi")) };
    if (path === "/houses") return listHouses();
    if ((m = /^\/devices\/(\d+)\/active$/.exec(path)) && method === "PUT") {
      const d = getDevice(+m[1]);
      d.is_active = !!body.is_active;
      return deviceRow(d);
    }
    if ((m = /^\/devices\/(\d+)$/.exec(path))) {
      if (method === "GET") return deviceDetail(+m[1]);
      if (method === "PUT") return updateDevice(+m[1], body);
      if (method === "DELETE") { deleteDevice(+m[1]); return st(204, null); }
    }
    // luật tự động
    if (path === "/rules" && method === "GET") return db.rules;
    if (path === "/rule-options") return { scenes: scenesCache.map((s) => ({ id: s.id, name: s.name || s.id })), modes: MODES };
    if (path === "/rules" && method === "POST") {
      const rule = validateRule(body);
      if (db.rules.some((r) => r.id === rule.id)) throw bad(`Mã luật “${rule.id}” đã tồn tại`);
      db.rules.push(rule);
      return st(201, rule);
    }
    if ((m = /^\/rules\/([^/]+)\/enabled$/.exec(path)) && method === "PUT") {
      const r = db.rules[ruleIndex(decodeURIComponent(m[1]))];
      r.enabled = body.enabled === undefined ? true : !!body.enabled;
      return r;
    }
    if ((m = /^\/rules\/([^/]+)$/.exec(path))) {
      const id = decodeURIComponent(m[1]);
      if (method === "PUT") {
        const i = ruleIndex(id);
        db.rules[i] = validateRule({ house_id: db.rules[i].house_id, ...body, id });
        return db.rules[i];
      }
      if (method === "DELETE") { ruleIndex(id); db.rules = db.rules.filter((r) => r.id !== id); return st(204, null); }
    }
    throw notFound("Not Found");
  }

  class Status { constructor(status, data) { this.status = status; this.data = data; } }
  const st = (status, data) => new Status(status, data);
  const json = (status, data) => new Response(data === null ? null : JSON.stringify(data),
    { status, headers: data === null ? {} : { "Content-Type": "application/json" } });

  /* Dùng như fetch(): MockApi.fetch("/api/...", {method, headers, body}) → Promise<Response> */
  async function mockFetch(path, options = {}) {
    await ready();
    await new Promise((r) => setTimeout(r, 60 + Math.random() * 120));   // giả độ trễ mạng
    const fresh = store.load();                                       // tab khác có thể vừa ghi (vd đăng nhập)
    if (fresh && fresh.v === 1 && fresh.rules) db = fresh;
    const method = (options.method || "GET").toUpperCase();
    let body = {};
    if (options.body) {
      try { body = JSON.parse(options.body); } catch { return json(422, { detail: "Dữ liệu gửi lên không phải JSON" }); }
    }
    try {
      const out = await route(method, new URL(path, "http://mock"), body || {}, options.headers || {});
      store.save();
      return out instanceof Status ? json(out.status, out.data) : json(200, out);
    } catch (e) {
      store.save();                                                   // vd ghi nhận đăng nhập sai
      if (e instanceof HttpError) return json(e.status, { detail: e.message });
      console.error(e);
      return json(500, { detail: String(e.message || e) });
    }
  }

  window.MockApi = { fetch: mockFetch, reset: () => { try { localStorage.removeItem(KEY); } catch { /* bỏ qua */ } } };
})();
