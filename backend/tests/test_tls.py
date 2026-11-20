"""
Kiểm thử TLS: tham số --tls, tạo chứng chỉ (infra/broker/gen_certs.py) và kết nối thật qua broker TLS.

    python -m unittest backend.tests.test_tls -v        # chạy từ thư mục gốc repo

Chứng chỉ được tạo trong thư mục tạm, không đụng tới infra/broker/certs/. Phần kết nối thật tự bật một
Mosquitto riêng trên cổng trống; máy không có mosquitto (hoặc thiếu gói cryptography) thì phần đó được bỏ qua.
"""
import argparse
import importlib.util
import os
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from backend.common import tls
from backend.common.cli import add_mqtt_args

ROOT = Path(__file__).resolve().parents[2]

try:
    import cryptography  # noqa: F401
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False


def load_gen_certs():
    spec = importlib.util.spec_from_file_location("gen_certs", ROOT / "infra" / "broker" / "gen_certs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_mosquitto():
    for p in (shutil.which("mosquitto"), r"C:\Program Files\mosquitto\mosquitto.exe", "/usr/sbin/mosquitto"):
        if p and Path(p).is_file():
            return p
    return None


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def parse(argv, env=None):
    with mock.patch.dict(os.environ, env or {}, clear=False):
        for k in ("MQTT_TLS", "MQTT_PORT", "MQTT_CAFILE"):
            if env is None or k not in env:
                os.environ.pop(k, None)
        return add_mqtt_args(argparse.ArgumentParser()).parse_args(argv)


class CliTest(unittest.TestCase):
    def test_default_is_plain_1883(self):
        a = parse([])
        self.assertFalse(a.tls)
        self.assertEqual(a.port, 1883)
        self.assertEqual(Path(a.cafile), tls.DEFAULT_CA)

    def test_tls_switches_default_port(self):
        a = parse(["--tls"])
        self.assertTrue(a.tls)
        self.assertEqual(a.port, 8883)

    def test_explicit_port_wins_in_any_order(self):
        self.assertEqual(parse(["--tls", "--port", "9999"]).port, 9999)
        self.assertEqual(parse(["--port", "9999", "--tls"]).port, 9999)

    def test_env_vars(self):
        a = parse([], {"MQTT_TLS": "1"})
        self.assertTrue(a.tls)
        self.assertEqual(a.port, 8883)
        self.assertEqual(parse([], {"MQTT_TLS": "1", "MQTT_PORT": "18883"}).port, 18883)
        self.assertEqual(parse([], {"MQTT_CAFILE": "x/ca.pem"}).cafile, "x/ca.pem")

    def test_missing_cafile_exits_with_hint(self):
        with self.assertRaises(SystemExit) as cm:
            tls.check_cafile("khong-co/ca.crt")
        self.assertIn("gen_certs.py", str(cm.exception.code))


@unittest.skipUnless(HAVE_CRYPTO, "thiếu gói cryptography")
class GenCertsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = load_gen_certs()
        cls.ca_key, cls.ca = cls.g.make_ca()
        cls.key, cls.cert = cls.g.make_server(cls.ca_key, cls.ca, cls.g.san_entries(["192.168.1.10", "nha.local"]))

    def test_server_cert_signed_by_ca(self):
        self.cert.verify_directly_issued_by(self.ca)

    def test_san_has_local_and_extra_names(self):
        from cryptography import x509
        san = self.cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        dns = san.get_values_for_type(x509.DNSName)
        ips = [str(i) for i in san.get_values_for_type(x509.IPAddress)]
        for name in ("localhost", "mosquitto", "nha.local"):
            self.assertIn(name, dns)
        for ip in ("127.0.0.1", "192.168.1.10"):
            self.assertIn(ip, ips)

    def test_server_cert_is_not_ca_and_for_server_auth(self):
        from cryptography import x509
        from cryptography.x509.oid import ExtendedKeyUsageOID
        self.assertFalse(self.cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca)
        self.assertTrue(self.ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca)
        eku = self.cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        self.assertIn(ExtendedKeyUsageOID.SERVER_AUTH, eku)

    def test_validity_within_browser_limit(self):
        days = (self.cert.not_valid_after_utc - self.cert.not_valid_before_utc).days
        self.assertLessEqual(days, 398)


@unittest.skipUnless(HAVE_CRYPTO and find_mosquitto(), "cần gói cryptography và mosquitto")
class BrokerTlsTest(unittest.TestCase):
    """Bật một Mosquitto TLS thật trên cổng trống rồi kết nối bằng chính new_client của dự án."""

    @classmethod
    def setUpClass(cls):
        g = load_gen_certs()
        cls.tmp = Path(tempfile.mkdtemp())
        ca_key, ca = g.make_ca()
        from cryptography import x509
        key, cert = g.make_server(ca_key, ca, [x509.DNSName("localhost")])   # chỉ có tên localhost
        g.write_cert(cls.tmp / "ca.crt", ca)
        g.write_cert(cls.tmp / "server.crt", cert)
        g.write_key(cls.tmp / "server.key", key)
        other_key, other_ca = g.make_ca()                     # CA lạ: dùng để giả lập client tin nhầm CA
        g.write_cert(cls.tmp / "other.crt", other_ca)

        cls.port = free_port()
        conf = cls.tmp / "m.conf"
        conf.write_text(f"listener {cls.port} 127.0.0.1\nprotocol mqtt\n"
                        f"certfile {(cls.tmp / 'server.crt').as_posix()}\nkeyfile {(cls.tmp / 'server.key').as_posix()}\n"
                        "tls_version tlsv1.2\nallow_anonymous true\n", encoding="utf-8")
        cls.proc = subprocess.Popen([find_mosquitto(), "-c", str(conf)],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", cls.port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def connect(self, host="localhost", cafile=None):
        from backend.common.mqtt_client import new_client
        c = new_client(f"test-tls-{time.time_ns()}", tls=True, cafile=str(cafile or self.tmp / "ca.crt"))
        try:
            c.connect(host, self.port, keepalive=10)
            return c
        finally:
            c.disconnect()

    def test_publish_and_receive_over_tls(self):
        from backend.common.mqtt_client import new_client
        got = []
        sub = new_client(f"test-sub-{time.time_ns()}", tls=True, cafile=str(self.tmp / "ca.crt"))
        sub.on_connect = lambda c, u, f, rc, p: c.subscribe("tls/test", qos=1)
        sub.on_message = lambda c, u, m: got.append(m.payload)
        sub.connect("localhost", self.port)
        sub.loop_start()
        try:
            time.sleep(0.5)
            pub = new_client(f"test-pub-{time.time_ns()}", tls=True, cafile=str(self.tmp / "ca.crt"))
            pub.connect("localhost", self.port)
            pub.loop_start()
            pub.publish("tls/test", b"xin chao", qos=1).wait_for_publish(3)
            pub.loop_stop()
            pub.disconnect()
            for _ in range(30):
                if got:
                    break
                time.sleep(0.1)
        finally:
            sub.loop_stop()
            sub.disconnect()
        self.assertEqual(got, [b"xin chao"])

    def test_rejects_broker_signed_by_unknown_ca(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.connect(cafile=self.tmp / "other.crt")

    def test_rejects_hostname_not_in_certificate(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.connect(host="127.0.0.1")         # vẫn là máy này nhưng IP không có trong SAN → nghi giả mạo


if __name__ == "__main__":
    unittest.main()
