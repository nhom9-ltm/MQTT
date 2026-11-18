"""Tạo CA tự ký + chứng chỉ cho broker để bật TLS (MQTT 8883, WebSocket 8443).

Chạy từ thư mục gốc repo:
    python infra/broker/gen_certs.py                         # tạo lần đầu / cấp lại chứng chỉ broker
    python infra/broker/gen_certs.py --host 192.168.1.10     # thêm IP / tên miền cho máy khác hoặc ESP32 kết nối
    python infra/broker/gen_certs.py --install               # (Windows) cho Chrome/Edge tin CA — cần cho dashboard wss://
    python infra/broker/gen_certs.py --new-ca                # tạo lại cả CA (mọi máy phải cài/copy lại ca.crt)

Sinh ra trong infra/broker/certs/ (đã .gitignore — mỗi máy tự tạo, KHÔNG đưa khóa lên GitHub):
    ca.crt / ca.key          CA của nhóm. Client giữ ca.crt để kiểm tra broker; ca.key dùng để ký, phải giữ kín
    server.crt / server.key  chứng chỉ của broker, ký bởi CA, có SAN: localhost, 127.0.0.1, tên máy, các IP LAN
và firmware/esp32/esp32_smarthome_node/ca_cert.h (ca.crt dạng chuỗi C cho ESP32).

CA được giữ nguyên giữa các lần chạy (trình duyệt và ESP32 đã tin CA thì không phải cài lại); chỉ chứng chỉ broker
được cấp lại. Xem docs/TLS.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import socket
import subprocess
import sys
from pathlib import Path

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
except ImportError:
    sys.exit("Thiếu thư viện: pip install -r backend/requirements-extra.txt  (cần gói cryptography)")

ROOT = Path(__file__).resolve().parents[2]
CERT_DIR = ROOT / "infra" / "broker" / "certs"
FIRMWARE_HEADER = ROOT / "firmware" / "esp32" / "esp32_smarthome_node" / "ca_cert.h"
CA_DAYS = 3650
SERVER_DAYS = 397           # ≤ 398 ngày: giới hạn trình duyệt chấp nhận cho chứng chỉ máy chủ


def lan_ips() -> list[str]:
    """IP của máy trên các mạng đang dùng (để ESP32 / máy khác kết nối bằng IP vẫn khớp chứng chỉ)."""
    ips: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:                                    # IP của card mạng ra Internet/LAN (không gửi gói nào thật)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith(("127.", "169.254.")))


def san_entries(extra: list[str]) -> list[x509.GeneralName]:
    names = ["localhost", "mosquitto", socket.gethostname()] + ["127.0.0.1", "::1"] + lan_ips() + extra
    out: list[x509.GeneralName] = []
    seen: set[str] = set()
    for n in names:
        n = n.strip()
        if not n or n.lower() in seen:
            continue
        seen.add(n.lower())
        try:
            out.append(x509.IPAddress(ipaddress.ip_address(n)))
        except ValueError:
            out.append(x509.DNSName(n))
    return out


def write_key(path: Path, key) -> None:
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                       serialization.NoEncryption()))


def write_cert(path: Path, cert: x509.Certificate) -> None:
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def make_ca() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Nhom 9 LTM"),
                      x509.NameAttribute(NameOID.COMMON_NAME, "Nhom 9 Smart Home CA")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=CA_DAYS))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True,
                                         content_commitment=False, key_encipherment=False, data_encipherment=False,
                                         key_agreement=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .sign(key, hashes.SHA256()))
    return key, cert


def make_server(ca_key, ca_cert: x509.Certificate, sans: list[x509.GeneralName]):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Nhom 9 LTM"),
                                     x509.NameAttribute(NameOID.COMMON_NAME, "mosquitto")]))
            .issuer_name(ca_cert.subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=SERVER_DAYS))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, key_encipherment=True, content_commitment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.SubjectAlternativeName(sans), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    return key, cert


def write_firmware_header(ca_pem: str) -> None:
    lines = "\n".join(f'"{line}\\n"' for line in ca_pem.strip().splitlines())
    FIRMWARE_HEADER.write_text(
        "// Sinh tự động bởi infra/broker/gen_certs.py — CA để ESP32 kiểm tra chứng chỉ broker khi MQTT_USE_TLS = 1.\n"
        "// Chạy lại script nếu tạo CA mới. File này nằm trong .gitignore (mỗi máy một CA riêng).\n"
        "#pragma once\n\n"
        f"static const char MQTT_CA_CERT[] =\n{lines};\n", encoding="utf-8")


def install_windows(ca_path: Path) -> None:
    if sys.platform != "win32":
        print("--install chỉ dùng trên Windows. macOS: mở ca.crt bằng Keychain → Always Trust; "
              "Linux/Firefox: import ca.crt trong phần Certificates của trình duyệt.")
        return
    print("Thêm CA vào kho 'Trusted Root' của tài khoản Windows (Windows sẽ hỏi xác nhận — bấm Yes)...")
    r = subprocess.run(["certutil", "-user", "-addstore", "Root", str(ca_path)], capture_output=True, text=True)
    if r.returncode == 0:
        print("Đã cài CA. Đóng hẳn rồi mở lại Chrome/Edge để trình duyệt nhận CA mới.")
    else:
        print("Không cài được CA:\n" + (r.stdout or r.stderr))


def main() -> None:
    for stream in (sys.stdout, sys.stderr):         # in tiếng Việt trên console Windows
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", action="append", default=[], metavar="IP_HOẶC_TÊN",
                   help="thêm IP / tên miền vào chứng chỉ broker (lặp lại được)")
    p.add_argument("--new-ca", action="store_true", help="tạo lại CA (mọi client phải nhận ca.crt mới)")
    p.add_argument("--install", action="store_true", help="(Windows) cài ca.crt vào kho tin cậy cho Chrome/Edge")
    args = p.parse_args()

    CERT_DIR.mkdir(parents=True, exist_ok=True)
    ca_crt, ca_key_path = CERT_DIR / "ca.crt", CERT_DIR / "ca.key"

    if args.new_ca or not (ca_crt.exists() and ca_key_path.exists()):
        ca_key, ca_cert = make_ca()
        write_key(ca_key_path, ca_key)
        write_cert(ca_crt, ca_cert)
        print(f"Đã tạo CA mới: {ca_crt.relative_to(ROOT)}")
    else:
        ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
        ca_cert = x509.load_pem_x509_certificate(ca_crt.read_bytes())
        print(f"Dùng lại CA có sẵn: {ca_crt.relative_to(ROOT)}")

    sans = san_entries(args.host)
    key, cert = make_server(ca_key, ca_cert, sans)
    write_key(CERT_DIR / "server.key", key)
    write_cert(CERT_DIR / "server.crt", cert)
    write_firmware_header(ca_crt.read_text())

    print(f"Đã cấp chứng chỉ broker: {(CERT_DIR / 'server.crt').relative_to(ROOT)} "
          f"(hết hạn {cert.not_valid_after_utc:%d/%m/%Y})")
    print("  Tên/IP hợp lệ: " + ", ".join(str(n.value) for n in sans))
    print(f"  CA cho ESP32:  {FIRMWARE_HEADER.relative_to(ROOT)}")
    if args.install:
        install_windows(ca_crt)
    print("Khởi động lại broker để nạp chứng chỉ mới:  mosquitto -c infra/broker/mosquitto.tls.conf -v")


if __name__ == "__main__":
    main()
