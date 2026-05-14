from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SIGNING_SECRET = os.environ.get("SOCIALAUTOPOST_WEBHOOK_SIGNING_SECRET", "")
PLATFORM_SECRET_MAP = {
    "tiktok": os.environ.get("SOCIALAUTOPOST_WEBHOOK_TIKTOK_SECRET", ""),
    "reels": os.environ.get("SOCIALAUTOPOST_WEBHOOK_REELS_SECRET", ""),
    "shorts": os.environ.get("SOCIALAUTOPOST_WEBHOOK_SHORTS_SECRET", ""),
}
MAX_SKEW_SECONDS = int(os.environ.get("SOCIALAUTOPOST_WEBHOOK_MAX_SKEW_SEC", "300"))
PORT = int(os.environ.get("SOCIALAUTOPOST_WEBHOOK_PORT", "8899"))


def compute_signature(secret: str, timestamp: str, body: bytes) -> str:
    signed = f"{timestamp}.".encode("utf-8") + body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_request(secret: str, signature: str, timestamp: str, body: bytes, max_skew_seconds: int) -> tuple[bool, str]:
    if not secret:
        return False, "missing server signing secret"
    if not signature:
        return False, "missing signature header"
    if not timestamp:
        return False, "missing timestamp header"
    try:
        ts = int(timestamp)
    except ValueError:
        return False, "invalid timestamp header"
    now = int(time.time())
    if abs(now - ts) > max_skew_seconds:
        return False, "timestamp outside allowed skew"
    expected = compute_signature(secret, timestamp, body)
    if not hmac.compare_digest(signature, expected):
        return False, "signature mismatch"
    return True, ""


class WebhookHandler(BaseHTTPRequestHandler):
    server_version = "SocialAutoPostWebhookExample/0.1"

    def do_POST(self) -> None:
        if self.path != "/autopost":
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length)
        signature = self.headers.get("x-signature", "")
        timestamp = self.headers.get("x-timestamp", "")
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_json({"ok": False, "error": "invalid json body"}, HTTPStatus.BAD_REQUEST)
            return

        platform = str(payload.get("platform", "")).lower()
        tenant_header = self.headers.get("x-platform", "").lower()
        secret = resolve_signing_secret(platform, tenant_header)
        ok, reason = verify_request(secret, signature, timestamp, body, MAX_SKEW_SECONDS)
        if not ok:
            self.send_json({"ok": False, "error": reason, "platform": platform or tenant_header}, HTTPStatus.UNAUTHORIZED)
            return

        remote_id = f"posted_{int(time.time())}"
        self.send_json(
            {
                "id": remote_id,
                "status": "accepted",
                "platform": platform,
                "url": f"https://example.local/posts/{remote_id}",
            },
            HTTPStatus.OK,
        )

    def send_json(self, payload: object, status: int) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), WebhookHandler)
    print(f"Webhook example listening on http://127.0.0.1:{PORT}/autopost")
    server.serve_forever()


def resolve_signing_secret(platform: str, tenant_header: str) -> str:
    for key in (platform, tenant_header):
        if key and PLATFORM_SECRET_MAP.get(key):
            return PLATFORM_SECRET_MAP[key]
    return SIGNING_SECRET


if __name__ == "__main__":
    main()
