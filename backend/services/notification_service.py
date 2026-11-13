"""Service của notifier: lọc mức độ, chống spam theo nguồn, gửi qua các kênh ở thread riêng."""
import threading
import time


class NotificationService:
    def __init__(self, channels, levels, cooldown: int = 60):
        self.channels = channels
        self.levels = set(levels)
        self.cooldown = cooldown
        self.last = {}              # source -> thời điểm gửi gần nhất (chống spam)

    def deliver(self, ev: dict):
        for ch in self.channels:
            try:
                ch.send(ev)
                print(f"  → {ch.name}: {ev.get('text', '')[:70]}")
            except Exception as e:  # noqa: BLE001  một kênh lỗi không được làm sập kênh khác
                print(f"  ✘ {ch.name} lỗi: {e}")

    def handle(self, ev) -> bool:
        """Trả True nếu sự kiện được gửi đi."""
        if not isinstance(ev, dict) or ev.get("level") not in self.levels:
            return False
        key = ev.get("source", "")
        now = time.time()
        if now - self.last.get(key, 0) < self.cooldown:
            return False
        self.last[key] = now
        # gửi ở thread riêng để SMTP/HTTP chậm không chặn vòng lặp MQTT
        threading.Thread(target=self.deliver, args=(ev,), daemon=True).start()
        return True

    def send_test(self) -> bool:
        ok = True
        for ch in self.channels:
            try:
                ch.send({"level": "critical", "text": "Tin nhắn thử từ notifier", "source": "test"})
                print(f"✔ {ch.name}: đã gửi")
            except Exception as e:  # noqa: BLE001
                ok = False
                print(f"✘ {ch.name}: {e}")
        return ok
