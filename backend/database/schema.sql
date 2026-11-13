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
--  backend/config/*.json, lịch sử vẫn ghi vào backend/data/smarthome.db.
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
    last_login_at   TIMESTAMPTZ,
    deleted_at      TIMESTAMPTZ                     -- xóa mềm: khác NULL = đã xóa (ẩn khỏi hệ thống, không đăng nhập được)
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
--  CỤM 2 — THIẾT BỊ (danh mục, khớp backend/simulator/house.py và ESP32)
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
--  CỤM 3 — TỰ ĐỘNG HÓA (danh mục; nội dung luật nằm ở backend/config/*.json)
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
--  DỮ LIỆU BAN ĐẦU: không khai báo ở đây.
--  Tài khoản, phòng, thiết bị, luật và kịch bản nằm trong backend/database/seed.py
--  (python backend/run_api.py tự nạp mỗi lần khởi động).
-- ==========================================================
