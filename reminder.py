import json
import os
import sys
import logging
import requests
import threading
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

CONFIG_FILE = Path(__file__).parent / "config.json"

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            "❌ Không tìm thấy config.json. Hãy tạo file cấu hình trước!"
        )

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
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

def main():
    cfg = load_config()
    token_valid = False
    if cfg["jwt_token"]:
        test_info = get_ai_deadline_info(cfg)
        if test_info != "AUTH_EXPIRED":
            token_valid = True

    if not token_valid:
        new_token = wait_for_token(cfg)
        cfg["jwt_token"] = new_token
        save_config(cfg)

if __name__ == "__main__":
    main()
