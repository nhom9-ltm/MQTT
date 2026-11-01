#!/usr/bin/env python3
"""
Kiểm tra xác thực + ACL của broker đang chạy ở chế độ bảo mật.
    python BE/broker/test_acl.py [--host localhost] [--port 1883]
Đọc mật khẩu từ BE/broker/credentials.env. Thoát với mã 1 nếu có ca kiểm tra thất bại.
"""
import argparse
import os
import sys
import threading
import time
import uuid

import paho.mqtt.client as mqtt

HERE = os.path.dirname(os.path.abspath(__file__))


def load_passwords():
    out = {}
    with open(os.path.join(HERE, "credentials.env"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("PASS_"):
                k, v = line.strip().split("=", 1)
                out[k[5:].lower().replace("_", "-")] = v
    return out


def connect(host, port, user=None, pw=None, transport="tcp"):
    """Trả về (client, rc) — rc là mã CONNACK (0 = chấp nhận, 5 = không được phép)."""
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"acltest-{uuid.uuid4().hex[:6]}",
                    transport=transport)
    if user:
        c.username_pw_set(user, pw)
    done = threading.Event()
    res = {}

    def on_connect(client, ud, flags, rc, props=None):
        res["rc"] = rc.value if hasattr(rc, "value") else rc
        done.set()

    c.on_connect = on_connect
    c.connect(host, port)
    c.loop_start()
    done.wait(5)
    return c, res.get("rc", -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--ws-port", type=int, default=9001)
    args = ap.parse_args()
    pw = load_passwords()
    fails = []

    def check(name, ok):
        print(f"  {'✔' if ok else '✘'} {name}")
        if not ok:
            fails.append(name)

    # --- 1. Đăng nhập
    print("1) Đăng nhập")
    c, rc = connect(args.host, args.port)
    check("không tài khoản → bị từ chối", rc != 0)
    c.loop_stop()
    c, rc = connect(args.host, args.port, "dashboard", "sai-mat-khau")
    check("sai mật khẩu → bị từ chối", rc != 0)
    c.loop_stop()
    c, rc = connect(args.host, args.ws_port, "dashboard", pw["dashboard"], transport="websockets")
    check("dashboard đăng nhập qua WebSocket :9001 → được", rc == 0)
    c.loop_stop()

    # --- 2. Quan sát bằng tài khoản logger (đọc home/#)
    seen = []
    obs, rc = connect(args.host, args.port, "logger", pw["logger"])
    check("logger đăng nhập → được", rc == 0)
    obs.on_message = lambda cl, ud, m: seen.append((m.topic, m.payload.decode()))
    obs.subscribe("home/acltest/#", qos=1)
    time.sleep(0.5)

    # --- 3. Dashboard: chỉ được gửi lệnh set
    print("2) Dashboard")
    dash, rc = connect(args.host, args.port, "dashboard", pw["dashboard"])
    dash.publish("home/acltest/dev/state", '{"fake":true}', qos=1)    # giả mạo state
    dash.publish("home/acltest/dev/status", '{"fake":true}', qos=1)   # giả mạo status
    dash.publish("home/acltest/dev/set", '{"on":true}', qos=1)        # lệnh hợp lệ
    time.sleep(1)
    topics = [t for t, _ in seen]
    check("gửi lệnh …/set → broker chuyển tiếp", "home/acltest/dev/set" in topics)
    check("giả mạo …/state → bị chặn", "home/acltest/dev/state" not in topics)
    check("giả mạo …/status → bị chặn", "home/acltest/dev/status" not in topics)

    # --- 4. Simulator: ghi state được, nhưng không ra lệnh được
    print("3) Simulator")
    seen.clear()
    sim, rc = connect(args.host, args.port, "simulator", pw["simulator"])
    sim.publish("home/acltest/dev/state", '{"ok":true}', qos=1)
    sim.publish("home/acltest/dev/set", '{"on":true}', qos=1)
    time.sleep(1)
    topics = [t for t, _ in seen]
    check("ghi …/state → được", "home/acltest/dev/state" in topics)
    check("gửi …/set (ra lệnh cho thiết bị khác) → bị chặn", "home/acltest/dev/set" not in topics)

    # --- 5. Logger chỉ đọc
    print("4) Logger")
    seen.clear()
    obs.publish("home/acltest/dev/state", '{"x":1}', qos=1)
    time.sleep(1)
    check("logger ghi message → bị chặn (chỉ đọc)", not seen)

    for cl in (obs, dash, sim):
        cl.loop_stop()
    print()
    if fails:
        print(f"THẤT BẠI {len(fails)} ca: {fails}")
        sys.exit(1)
    print("Tất cả ca kiểm tra đạt.")


if __name__ == "__main__":
    main()
