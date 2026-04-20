from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class NotificationEvent:
    host: str
    status: str
    duration_seconds: float
    errors: list[str]
    run_id: str
    plan_id: str | None = None
    scope: str | None = None
    kind: str = "deploy"

    def as_text(self) -> str:
        parts = [
            f"Seraf {self.kind}",
            f"host={self.host}",
            f"status={self.status}",
            f"duration={self.duration_seconds:.2f}s",
        ]
        if self.scope:
            parts.append(f"scope={self.scope}")
        if self.plan_id:
            parts.append(f"plan={self.plan_id}")
        parts.append(f"run={self.run_id}")
        if self.errors:
            parts.append(f"errors={' | '.join(self.errors)}")
        return "\n".join(parts)


def post_json(url: str, payload: dict[str, Any], *, timeout: int = 10) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout):
        return None


def send_telegram_notification(config: dict[str, Any], event: NotificationEvent) -> None:
    if not config.get("enabled"):
        return
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")
    if not bot_token or not chat_id:
        raise ValueError("telegram notification requires bot_token and chat_id")
    api_base = config.get("api_base", "https://api.telegram.org")
    url = f"{api_base.rstrip('/')}/bot{bot_token}/sendMessage"
    post_json(url, {"chat_id": chat_id, "text": event.as_text()})


def send_email_notification(config: dict[str, Any], event: NotificationEvent) -> None:
    if not config.get("enabled"):
        return
    recipient = config.get("to")
    if not recipient:
        raise ValueError("email notification requires a 'to' address")
    sendmail_bin = config.get("sendmail_bin", "sendmail")
    subject_prefix = config.get("subject_prefix", "[Seraf]")
    message = (
        f"To: {recipient}\n"
        f"Subject: {subject_prefix} {event.status} {event.host}\n"
        "Content-Type: text/plain; charset=utf-8\n\n"
        f"{event.as_text()}\n"
    )
    subprocess.run([sendmail_bin, recipient], input=message, text=True, check=True, capture_output=True)


def notify_all(config: dict[str, Any], event: NotificationEvent) -> list[str]:
    warnings: list[str] = []
    try:
        send_telegram_notification(config.get("telegram", {}), event)
    except (OSError, ValueError, urllib.error.URLError, subprocess.SubprocessError) as exc:
        warnings.append(f"telegram notification failed: {exc}")
    try:
        send_email_notification(config.get("email", {}), event)
    except (OSError, ValueError, urllib.error.URLError, subprocess.SubprocessError) as exc:
        warnings.append(f"email notification failed: {exc}")
    return warnings
