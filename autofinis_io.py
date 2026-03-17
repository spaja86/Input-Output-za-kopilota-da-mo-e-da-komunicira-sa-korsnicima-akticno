import os
import ssl
import time
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _load_env(filepath=".env"):
    """Load environment variables from a .env file if present."""
    if not os.path.exists(filepath):
        return
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


class NotificationChannel:
    def notify(self, message):
        raise NotImplementedError("Each channel must implement a notification method.")


class GitHubIssues(NotificationChannel):
    """Creates a GitHub issue via the GitHub REST API."""

    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN", "")
        self.repo = os.environ.get("GITHUB_REPO", "")  # format: "owner/repo"

    def notify(self, message):
        if not self.token or not self.repo:
            logger.warning("GitHub: GITHUB_TOKEN or GITHUB_REPO not configured — skipping.")
            return
        url = f"https://api.github.com/repos/{self.repo}/issues"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        title = message if len(message) <= 80 else message[:77] + "..."
        payload = {"title": title, "body": message}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            issue_url = resp.json().get("html_url", "")
            logger.info("GitHub Issue created: %s", issue_url)
        except requests.RequestException as exc:
            logger.error("GitHub Issue creation failed: %s", exc)


class Email(NotificationChannel):
    """Sends an email notification via SMTP."""

    def __init__(self):
        self.host = os.environ.get("EMAIL_HOST", "")
        try:
            self.port = int(os.environ.get("EMAIL_PORT", "587"))
        except ValueError:
            logger.warning("EMAIL_PORT is not a valid integer; defaulting to 587.")
            self.port = 587
        self.user = os.environ.get("EMAIL_USER", "")
        self.password = os.environ.get("EMAIL_PASSWORD", "")
        self.from_addr = os.environ.get("EMAIL_FROM", self.user)
        self.to_addr = os.environ.get("EMAIL_TO", "")

    def notify(self, message):
        if not all([self.host, self.user, self.password, self.to_addr]):
            logger.warning("Email: credentials not fully configured — skipping.")
            return
        msg = MIMEMultipart()
        msg["From"] = self.from_addr
        msg["To"] = self.to_addr
        msg["Subject"] = "Autofinis Notification"
        msg.attach(MIMEText(message, "plain"))
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(self.user, self.password)
                server.sendmail(self.from_addr, self.to_addr, msg.as_string())
            logger.info("Email sent to %s", self.to_addr)
        except (smtplib.SMTPException, OSError) as exc:
            logger.error("Email sending failed: %s", exc)


class Discord(NotificationChannel):
    """Sends a message to a Discord channel via a webhook URL."""

    def __init__(self):
        self.webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

    def notify(self, message):
        if not self.webhook_url:
            logger.warning("Discord: DISCORD_WEBHOOK_URL not configured — skipping.")
            return
        payload = {"content": message}
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info("Discord notification sent.")
        except requests.RequestException as exc:
            logger.error("Discord notification failed: %s", exc)


class Telegram(NotificationChannel):
    """Sends a message via the Telegram Bot API."""

    def __init__(self):
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    def notify(self, message):
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured — skipping.")
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info("Telegram message sent to chat %s.", self.chat_id)
        except requests.RequestException as exc:
            logger.error("Telegram notification failed: %s", exc)


class Slack(NotificationChannel):
    """Posts a message to a Slack channel via the Slack Web API."""

    def __init__(self):
        self.token = os.environ.get("SLACK_BOT_TOKEN", "")
        self.channel = os.environ.get("SLACK_CHANNEL_ID", "")

    def notify(self, message):
        if not self.token or not self.channel:
            logger.warning("Slack: SLACK_BOT_TOKEN or SLACK_CHANNEL_ID not configured — skipping.")
            return
        url = "https://slack.com/api/chat.postMessage"
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {"channel": self.channel, "text": message}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                logger.error("Slack API error: %s", data.get("error"))
            else:
                logger.info("Slack message posted to %s.", self.channel)
        except requests.RequestException as exc:
            logger.error("Slack notification failed: %s", exc)


class ActiveIOSystem:
    def __init__(self):
        _load_env()
        self.channels = [
            GitHubIssues(),
            Email(),
            Discord(),
            Telegram(),
            Slack(),
        ]

    def notify_all(self, message):
        for channel in self.channels:
            channel.notify(message)

    def run_autofinis(self, iterations=20):
        for i in range(1, iterations + 1):
            time.sleep(1)  # Simulate processing
            message = f"Autofinis iteration {i} completed."
            self.notify_all(message)


if __name__ == "__main__":
    io_system = ActiveIOSystem()
    io_system.run_autofinis()