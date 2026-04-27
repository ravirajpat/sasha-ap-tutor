#!/usr/bin/env python3
"""
Morning daily quiz alert.
Sends Sasha an HTML email with today's topic and a one-click link that opens
the Streamlit app and auto-loads a fresh 4 MCQ + 1 FRQ practice set.

Run via GitHub Actions at 8 AM EST (13:00 UTC) every day.
"""

import os
import smtplib
import sys
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent import AGENTS, get_daily_topic  # noqa: E402

GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")
SASHA_EMAIL    = os.environ["SASHA_EMAIL"]
PARENT_EMAILS  = [e.strip() for e in os.environ["PARENT_EMAIL"].split(",") if e.strip()]
APP_URL        = os.environ.get("APP_URL", "https://sasha-ap-tutor.streamlit.app").rstrip("/")

# Subject accent colours that match the app's formula-card palette
SUBJECT_COLOR = {
    "physics":  "#4e9af1",
    "calculus": "#9b59b6",
}


def send_quiz_email(cfg, topic: str) -> None:
    today     = date.today()
    days_left = (cfg.exam_date - today).days
    today_str = today.strftime("%A, %B %d")
    color     = SUBJECT_COLOR.get(cfg.key, "#4e9af1")
    app_link  = f"{APP_URL}?daily_quiz=true&subject={cfg.key}"

    # Short unit label for the email subject line (strip the "Unit N:" prefix)
    short_topic = topic.split(":", 1)[-1].strip() if ":" in topic else topic

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:16px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',
             Roboto,sans-serif;background:#f0f2f5;color:#333">

  <div style="max-width:540px;margin:0 auto;background:#fff;border-radius:14px;
              overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.09)">

    <!-- Coloured header band -->
    <div style="background:{color};padding:22px 28px 18px">
      <p style="margin:0 0 2px;color:rgba(255,255,255,0.75);font-size:0.8rem;
                letter-spacing:0.06em;text-transform:uppercase">Daily Practice</p>
      <h1 style="margin:0;color:#fff;font-size:1.25rem;font-weight:700;line-height:1.3">
        {cfg.icon}&nbsp; {cfg.display_name}
      </h1>
      <p style="margin:4px 0 0;color:rgba(255,255,255,0.8);font-size:0.85rem">
        {today_str} &nbsp;·&nbsp; {days_left} day{"s" if days_left != 1 else ""} to exam
      </p>
    </div>

    <!-- Body -->
    <div style="padding:24px 28px 20px">
      <p style="margin:0 0 6px;font-size:1rem;font-weight:600">Good morning, Sasha! ☀️</p>
      <p style="margin:0 0 20px;color:#555;font-size:0.93rem;line-height:1.55">
        Today's topic is
        <span style="background:{color}18;color:{color};font-weight:600;
                     padding:1px 7px;border-radius:4px">{topic}</span>.<br><br>
        Your quiz has <strong>4 Multiple Choice + 1 Free Response</strong> questions
        at <strong>moderate difficulty</strong> — the same style as the real AP exam.
        It takes about 15–20 minutes.
      </p>

      <!-- CTA -->
      <div style="text-align:center;margin:28px 0 24px">
        <a href="{app_link}"
           style="display:inline-block;background:{color};color:#fff;text-decoration:none;
                  padding:13px 38px;border-radius:9px;font-size:1rem;font-weight:600;
                  letter-spacing:0.01em;box-shadow:0 2px 8px {color}55">
          🚀&nbsp; Start Today's Quiz
        </a>
      </div>

      <p style="color:#aaa;font-size:0.78rem;text-align:center;margin:0">
        Opens in your AP Tutor app · Questions generated fresh for you
      </p>
    </div>

    <!-- Footer -->
    <div style="background:#f8f8f8;padding:12px 28px;border-top:1px solid #ebebeb">
      <p style="margin:0;color:#ccc;font-size:0.72rem;text-align:center">
        Sasha's AP Tutor &nbsp;·&nbsp; Exam on {cfg.exam_date.strftime("%B %d, %Y")}
      </p>
    </div>

  </div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{cfg.icon} AP Quiz Today — {short_topic}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = SASHA_EMAIL
    msg["Cc"]      = ", ".join(PARENT_EMAILS)
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.send_message(msg, to_addrs=[SASHA_EMAIL] + PARENT_EMAILS)

    print(f"[daily_quiz] Sent → {SASHA_EMAIL} (cc: {', '.join(PARENT_EMAILS)}) | {cfg.display_name}: {topic}")


def main():
    today = date.today()
    sent  = 0

    for cfg in AGENTS.values():
        days_left = (cfg.exam_date - today).days
        if days_left <= 0:
            print(f"[daily_quiz] {cfg.display_name}: exam has passed — skipping.")
            continue
        topic = get_daily_topic(cfg)
        send_quiz_email(cfg, topic)
        sent += 1

    if sent == 0:
        print("[daily_quiz] All exams have passed — no emails sent.")


if __name__ == "__main__":
    main()
