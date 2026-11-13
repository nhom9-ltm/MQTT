#!/usr/bin/env python3
"""
Tạo tài khoản MQTT cho chế độ bảo mật (xem docs/MO_RONG.md, mục 2).

  python infra/broker/setup_auth.py            # tạo infra/broker/passwd + infra/broker/credentials.env
  python infra/broker/setup_auth.py --force    # tạo lại mật khẩu mới

* infra/broker/passwd           : file băm mật khẩu cho Mosquitto (tạo bằng mosquitto_passwd trong Docker)
* infra/broker/credentials.env  : mật khẩu dạng chữ thường để bạn đưa cho từng thành phần
Cả hai đã nằm trong .gitignore — không commit.
Cần Docker (dùng image eclipse-mosquitto:2 để chạy mosquitto_passwd, không cần cài Mosquitto).
"""
import argparse
import os
import secrets
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
USERS = ["dashboard", "automation", "logger", "simulator", "esp32-01", "notifier"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true", help="ghi đè và tạo mật khẩu mới")
    args = p.parse_args()

    passwd = os.path.join(HERE, "passwd")
    cred = os.path.join(HERE, "credentials.env")
    if os.path.exists(passwd) and not args.force:
        sys.exit("infra/broker/passwd đã tồn tại. Thêm --force nếu muốn tạo lại.")

    passwords = {u: secrets.token_urlsafe(9) for u in USERS}
    if os.path.exists(passwd):
        os.remove(passwd)

    for i, (user, pw) in enumerate(passwords.items()):
        cmd = ["docker", "run", "--rm", "-v", f"{HERE}:/work", "eclipse-mosquitto:2",
               "mosquitto_passwd", "-b"] + (["-c"] if i == 0 else []) + ["/work/passwd", user, pw]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"mosquitto_passwd lỗi với user {user}:\n{r.stderr}")

    # mosquitto_passwd tạo file 0600 (root) -> user mosquitto trong container broker không đọc được
    subprocess.run(["docker", "run", "--rm", "-v", f"{HERE}:/work", "--entrypoint", "chmod",
                    "eclipse-mosquitto:2", "644", "/work/passwd"], check=True)

    with open(cred, "w", encoding="utf-8") as f:
        f.write("# Mật khẩu MQTT — KHÔNG commit. Tạo bởi infra/broker/setup_auth.py\n")
        for user, pw in passwords.items():
            f.write(f"PASS_{user.upper().replace('-', '_')}={pw}\n")

    print("Đã tạo infra/broker/passwd và infra/broker/credentials.env\n")
    for user, pw in passwords.items():
        print(f"  {user:<11} {pw}")
    print("\nBước tiếp theo:\n"
          "  docker compose --env-file infra/broker/credentials.env -f docker-compose.yml "
          "-f docker-compose.secure.yml up -d --force-recreate mosquitto")


if __name__ == "__main__":
    main()
