-- ==========================================================
--  Cơ sở dữ liệu ứng dụng Nhà thông minh (PostgreSQL)
--
--  Docker tự chạy file này MỘT LẦN, khi volume database còn trống (xem docker-compose.yml).
--  Đã sửa file và muốn nạp lại (XÓA HẾT dữ liệu trong database này):
--      docker compose rm -sf database
--      docker volume rm mqtt_database-data
--      docker compose up -d database
--
--  Phạm vi: tài khoản, phiên đăng nhập và danh mục cho trang quản trị.
--  Runtime của nhà thông minh không đổi: trạng thái thiết bị vẫn đi qua MQTT, luật/kịch bản vẫn đọc từ
--  BE/config/*.json, lịch sử vẫn ghi vào BE/data/smarthome.db.
-- ==========================================================
SET client_encoding = 'UTF8';


-- ==========================================================
--  CỤM 1 — NGƯỜI DÙNG
-- ==========================================================
CREATE TABLE roles (
    id          SMALLINT PRIMARY KEY,
    code        VARCHAR(20)  NOT NULL UNIQUE,
    name        VARCHAR(50)  NOT NULL
);

CREATE TABLE users (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email           VARCHAR(254) NOT NULL UNIQUE CHECK (email = lower(email) AND email LIKE '%@gmail.com'),
    password_hash   CHAR(64)     NOT NULL,          -- SHA-256 dạng hex của mật khẩu
    full_name       VARCHAR(100) NOT NULL,
    role_id         SMALLINT     NOT NULL REFERENCES roles(id),
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);
CREATE INDEX idx_users_role ON users(role_id);

CREATE TABLE sessions (
    token_hash  CHAR(64)    PRIMARY KEY,            -- SHA-256 của token; bản gốc chỉ nằm ở trình duyệt
    user_id     BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);


-- ==========================================================
--  CỤM 2 — THIẾT BỊ (danh mục, khớp BE/mock/house.py và ESP32)
-- ==========================================================
CREATE TABLE rooms (
    id      SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code    VARCHAR(30)  NOT NULL UNIQUE,           -- cấp <phòng> trong topic MQTT
    name    VARCHAR(50)  NOT NULL
);

CREATE TABLE device_types (
    code    VARCHAR(20)  PRIMARY KEY,               -- trường "type" trong .../status
    name    VARCHAR(50)  NOT NULL
);

CREATE TABLE devices (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    room_id         SMALLINT     NOT NULL REFERENCES rooms(id),
    code            VARCHAR(30)  NOT NULL,          -- cấp <thiết bị> trong topic MQTT
    name            VARCHAR(100) NOT NULL,
    type_code       VARCHAR(20)  NOT NULL REFERENCES device_types(code),
    is_simulated    BOOLEAN      NOT NULL,
    UNIQUE (room_id, code)
);
CREATE INDEX idx_devices_type ON devices(type_code);


-- ==========================================================
--  CỤM 3 — TỰ ĐỘNG HÓA (danh mục; nội dung luật nằm ở BE/config/*.json)
-- ==========================================================
CREATE TABLE automation_rules (
    id                  SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code                VARCHAR(50)  NOT NULL UNIQUE,   -- "id" trong rules.json
    name                VARCHAR(150) NOT NULL,
    cooldown_seconds    INTEGER
);

CREATE TABLE scenes (
    id      SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code    VARCHAR(50)  NOT NULL UNIQUE,               -- "id" trong scenes.json
    name    VARCHAR(100) NOT NULL,
    icon    VARCHAR(16)
);


-- ==========================================================
--  CỤM 4 — NHẬT KÝ
-- ==========================================================
CREATE TABLE login_history (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email       VARCHAR(254) NOT NULL,
    user_id     BIGINT       REFERENCES users(id) ON DELETE SET NULL,
    success     BOOLEAN      NOT NULL,
    ip_address  VARCHAR(45),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_login_history_created ON login_history(created_at DESC);


-- ==========================================================
--  DỮ LIỆU BAN ĐẦU
-- ==========================================================
INSERT INTO roles (id, code, name) VALUES
    (1, 'admin', 'Quản trị viên'),
    (2, 'user',  'Người dùng');

INSERT INTO users (email, password_hash, full_name, role_id) VALUES
    ('admmqtt@gmail.com', '42765d8789c8eaf1d0da8d96eee46fde22527187224b6a64e18e4e9e4ac82e40', 'Quản trị viên', 1),
    ('user1@gmail.com',   'c80e110ef0a2f0bd16b034b8036a8e0a85bec66e9ade9af975c73ed034532888', 'Người dùng 1',  2);

INSERT INTO rooms (code, name) VALUES
    ('living',   'Phòng khách'),
    ('bedroom',  'Phòng ngủ'),
    ('kitchen',  'Nhà bếp'),
    ('entrance', 'Lối vào'),
    ('lab',      'Lab (ESP32)');

INSERT INTO device_types (code, name) VALUES
    ('climate', 'Nhiệt độ & độ ẩm'),
    ('light',   'Đèn'),
    ('fan',     'Quạt'),
    ('ac',      'Điều hòa'),
    ('curtain', 'Rèm'),
    ('plug',    'Ổ cắm'),
    ('lock',    'Khóa cửa'),
    ('door',    'Cảm biến cửa'),
    ('motion',  'Cảm biến chuyển động'),
    ('gas',     'Cảm biến gas'),
    ('node',    'Bo mạch');

INSERT INTO devices (room_id, code, name, type_code, is_simulated)
SELECT r.id, d.code, d.name, d.type_code, d.is_simulated
FROM (VALUES
    ('living',   'climate',     'Nhiệt độ & độ ẩm',     'climate', TRUE),
    ('living',   'light',       'Đèn trần',             'light',   TRUE),
    ('living',   'fan',         'Quạt đứng',            'fan',     TRUE),
    ('living',   'ac',          'Điều hòa',             'ac',      TRUE),
    ('living',   'curtain',     'Rèm cửa sổ',           'curtain', TRUE),
    ('living',   'tv-plug',     'Ổ cắm TV',             'plug',    TRUE),
    ('living',   'motion',      'Cảm biến chuyển động', 'motion',  TRUE),
    ('bedroom',  'climate',     'Nhiệt độ & độ ẩm',     'climate', TRUE),
    ('bedroom',  'light',       'Đèn ngủ',              'light',   TRUE),
    ('bedroom',  'ac',          'Điều hòa',             'ac',      TRUE),
    ('bedroom',  'curtain',     'Rèm cửa sổ',           'curtain', TRUE),
    ('kitchen',  'climate',     'Nhiệt độ & độ ẩm',     'climate', TRUE),
    ('kitchen',  'light',       'Đèn bếp',              'light',   TRUE),
    ('kitchen',  'hood-fan',    'Quạt hút mùi',         'fan',     TRUE),
    ('kitchen',  'stove-plug',  'Bếp điện',             'plug',    TRUE),
    ('kitchen',  'gas',         'Cảm biến khí gas',     'gas',     TRUE),
    ('entrance', 'lock',        'Khóa cửa chính',       'lock',    TRUE),
    ('entrance', 'door',        'Cảm biến cửa chính',   'door',    TRUE),
    ('entrance', 'motion',      'Cảm biến chuyển động', 'motion',  TRUE),
    ('entrance', 'porch-light', 'Đèn hiên',             'light',   TRUE),
    ('lab',      'esp32-01',    'Bo mạch ESP32',        'node',    FALSE),
    ('lab',      'climate',     'DHT22',                'climate', FALSE),
    ('lab',      'light',       'Relay đèn',            'light',   FALSE),
    ('lab',      'fan',         'Relay quạt',           'fan',     FALSE),
    ('lab',      'motion',      'PIR',                  'motion',  FALSE),
    ('lab',      'door',        'Công tắc từ',          'door',    FALSE),
    ('lab',      'gas',         'MQ-2',                 'gas',     FALSE)
) AS d(room_code, code, name, type_code, is_simulated)
JOIN rooms r ON r.code = d.room_code;

INSERT INTO automation_rules (code, name, cooldown_seconds) VALUES
    ('living_hot',       'Phòng khách nóng → bật điều hòa',                120),
    ('gas_leak',         'Rò rỉ gas → ngắt bếp, bật quạt hút',             NULL),
    ('porch_light',      'Có người ở cửa buổi tối → bật đèn hiên 2 phút',  NULL),
    ('intrusion_door',   'Cửa mở khi vắng nhà / ban đêm → báo động',       NULL),
    ('intrusion_motion', 'Chuyển động khi vắng nhà → báo động',            60),
    ('living_idle',      'Không ai trong phòng khách 2 phút → tắt đèn, quạt', NULL),
    ('night_lock',       '23:00 tự khóa cửa nếu quên',                     NULL),
    ('lab_hot',          '[ESP32] Lab > 30°C → bật quạt',                  NULL),
    ('lab_cool',         '[ESP32] Lab < 29°C → tắt quạt',                  NULL),
    ('lab_motion',       '[ESP32] Có chuyển động → bật đèn lab 30 giây',   NULL),
    ('lab_gas',          '[ESP32] MQ-2 báo gas → bật quạt + cảnh báo',     NULL);

INSERT INTO scenes (code, name, icon) VALUES
    ('home',    'Về nhà',      '🏠'),
    ('away',    'Ra khỏi nhà', '🚪'),
    ('sleep',   'Đi ngủ',      '🌙'),
    ('morning', 'Buổi sáng',   '☀️'),
    ('movie',   'Xem phim',    '🎬');
