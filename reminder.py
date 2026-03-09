import json
import os
import sys
import logging
import requests
import threading
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Logging ──────────────────────────────────────────────────
LOG_FILE = Path(__file__).parent / "reminder.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("reminder")

# ── Config ──────────────────────────────────────────────────
CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULT_CONFIG = {
    "api_base_url": "http://localhost:3900/api/v1",
    "jwt_token": "",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "qwen3:8b",
    "deadline_warn_hours": 48,
    "hook_port": 3901
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return {**DEFAULT_CONFIG, **cfg}
    else:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        return DEFAULT_CONFIG


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ── Token Hook (Listener) ────────────────────────────────────
class TokenHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path == "/token":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                token = data.get("token")
                if token:
                    self.server.received_token = token
                    self.send_response(200)
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success"}).encode())
                    log.info("✅ Đã nhận được token từ Hook!")
                else:
                    self.send_error(400, "Missing token")
            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        return  # Silent server logs


def wait_for_token(cfg: dict) -> str:
    """Khởi chạy server tạm thời để chờ token từ Frontend."""
    port = cfg.get("hook_port", 3901)
    server = HTTPServer(("localhost", port), TokenHandler)
    server.received_token = None
    
    log.info("📡 Đang chờ token từ trình duyệt (Hook)...")
    log.info(f"👉 Hãy đăng nhập vào LMS tại http://localhost:5173")
    
    while not server.received_token:
        server.handle_request()
    
    token = server.received_token
    server.server_close()
    return token


# ── API Calls ──────────────────────────────────────────────────
def get_ai_deadline_info(cfg: dict) -> str:
    url = f"{cfg['api_base_url']}/ai/chat"
    headers = {
        "Authorization": f"Bearer {cfg['jwt_token']}",
        "Content-Type": "application/json",
    }
    payload = {
        "type": "DEADLINE",
        "question": (
            "Liệt kê các bài tập có deadline trong vòng 48 giờ tới. "
            "Nếu có, hãy nói rõ tên bài tập và thời hạn. "
            "Nếu không có, hãy nói không có deadline gấp."
        ),
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data.get("answer", "Không có thông tin deadline.")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return "AUTH_EXPIRED"
        return f"❌ Lỗi HTTP {e.response.status_code}"
    except Exception as e:
        return f"❌ Lỗi: {e}"


def get_ai_exam_info(cfg: dict) -> str:
    url = f"{cfg['api_base_url']}/ai/chat"
    headers = {
        "Authorization": f"Bearer {cfg['jwt_token']}",
        "Content-Type": "application/json",
    }
    payload = {
        "type": "EXAM",
        "question": (
            "Có kỳ thi nào trong vòng 7 ngày tới không? "
            "Nếu có, hãy nói rõ tên kỳ thi, thời gian bắt đầu và kết thúc."
        ),
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data.get("answer", "Không có thông tin kỳ thi.")
    except Exception as e:
        return f"❌ Lỗi lấy thông tin kỳ thi: {e}"


# ── Desktop Notification ──────────────────────────────────────
def send_notification(title: str, message: str):
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message[:256],
            app_name="LMS AI Reminder",
            timeout=12,
        )
        log.info(f"✅ Đã gửi notification: {title}")
    except Exception:
        print(f"\n📣 {title}\n{message}\n")


# ── Main ──────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("🚀 LMS AI Reminder khởi động")
    log.info("=" * 60)

    cfg = load_config()

    # Thử gọi API với token cũ
    token_valid = False
    if cfg["jwt_token"]:
        log.info("🔍 Đang kiểm tra token hiện tại...")
        test_info = get_ai_deadline_info(cfg)
        if test_info != "AUTH_EXPIRED":
            token_valid = True
            log.info("✅ Token vẫn còn hiệu lực.")

    if not token_valid:
        # Nếu token hết hạn hoặc chưa có, mở Hook chờ token mới
        new_token = wait_for_token(cfg)
        cfg["jwt_token"] = new_token
        save_config(cfg)
        log.info("💾 Đã lưu token mới.")

    # Tiến hành lấy dữ liệu
    log.info("📚 Đang lấy dữ liệu AI...")
    deadline_info = get_ai_deadline_info(cfg)
    exam_info = get_ai_exam_info(cfg)

    # Xử lý thông báo (giữ nguyên logic cũ)
    urgent_keywords = ["hạn", "deadline", "nộp", "ngày mai", "hôm nay", "còn", "sắp"]
    if any(kw in deadline_info.lower() for kw in urgent_keywords) and "không có" not in deadline_info[:50].lower():
        send_notification("⚠️ LMS – Deadline sắp đến!", deadline_info[:200])
    
    if any(kw in exam_info.lower() for kw in ["thi", "ngày", "giờ"]) and "không có" not in exam_info[:50].lower():
        send_notification("📅 LMS – Lịch thi sắp tới", exam_info[:200])

    log.info("✅ Hoàn thành.")


if __name__ == "__main__":
    main()
