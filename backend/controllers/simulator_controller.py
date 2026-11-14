"""
Controller của bộ giả lập thiết bị: đọc tham số dòng lệnh, xử lý tín hiệu tắt, chạy căn nhà giả lập.

Topic (prefix mặc định "home"):
  home/<phòng>/<thiết bị>/status   thiết bị → broker   QoS 1, retained   online/offline + mô tả (discovery), LWT
  home/<phòng>/<thiết bị>/state    thiết bị → broker   QoS 1, retained   trạng thái hiện tại {"on":true,...}
  home/<phòng>/<thiết bị>/set      ai đó   → thiết bị  QoS 1             lệnh {"on":false}, {"position":50}, ...

Ví dụ:
  python backend/run_simulator.py
  python backend/run_simulator.py --rooms living,kitchen --qos 2
  python backend/run_simulator.py --host 192.168.1.10 --no-random     # tắt sự kiện ngẫu nhiên khi thuyết trình
"""
import argparse
import signal
import sys

from backend.common.cli import add_mqtt_args
from backend.simulator.house import House


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Giả lập thiết bị nhà thông minh (MQTT)")
    add_mqtt_args(p)
    p.add_argument("--rooms", help="chỉ chạy các phòng này, vd: living,kitchen")
    p.add_argument("--qos", type=int, choices=[0, 1, 2], default=1, help="QoS khi publish state")
    p.add_argument("--keepalive", type=int, default=10, help="keep-alive (giây)")
    p.add_argument("--interval", type=float, default=5.0, help="chu kỳ báo số liệu cảm biến (giây)")
    p.add_argument("--revive", type=float, default=20.0, help="sau khi 'mất điện' bao lâu thì bật lại (giây)")
    p.add_argument("--no-random", action="store_true", help="tắt chuyển động ngẫu nhiên (chỉ khi bấm Giả lập)")
    p.add_argument("--quiet", action="store_true", help="không in mỗi lần đổi trạng thái")
    p.add_argument("--verbose", action="store_true", help="in cả số liệu định kỳ")
    p.add_argument("--extra", action="append", default=[], metavar="PHÒNG/MÃ:LOẠI:TÊN",
                   help='giả lập thêm thiết bị (lặp lại được), vd --extra "living/a1:fan:Quạt trần". '
                        "Dùng cho thiết bị quản trị viên mới tạo mà chưa có phần cứng thật")
    return p


def main():
    args = build_parser().parse_args()

    house = House(args)
    if not house.devices:
        sys.exit("Không có thiết bị nào (kiểm tra --rooms)")

    def stop(*_):
        house.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    house.run()


if __name__ == "__main__":
    main()
