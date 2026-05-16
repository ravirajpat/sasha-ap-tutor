#!/usr/bin/env python3
"""
Evening practice reminder — run via GitHub Actions at 5 PM EST.
Sends email to Sasha and parent if she hasn't answered MIN_QUESTIONS today.
Falls back to local JSON if Supabase is not configured.
"""

import os
import smtplib
import sys
from datetime import date
from email.mime.text import MIMEText

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent import AGENTS, get_today_questions, MIN_QUESTIONS  # noqa: E402

GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")
SASHA_EMAIL    = os.environ["SASHA_EMAIL"]
PARENT_EMAIL   = os.environ["PARENT_EMAIL"]
APP_URL        = os.environ.get("APP_URL", "https://sasha-sat-tutor.streamlit.app").rstrip("/")


def send_email(to: str, subject: str, body: str):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.send_message(msg)


def main():
    today = date.today()
    sent  = False

    for cfg in AGENTS.values():
        days_left = (cfg.exam_date - today).days
        if days_left <= 0:
            continue

        q = get_today_questions(cfg)
        print(f"[alert] {cfg.display_name}: {q}/{MIN_QUESTIONS} questions answered today")

        if q >= MIN_QUESTIONS:
            print(f"[alert] {cfg.display_name}: goal met — no alert needed.")
            continue

        send_email(
            SASHA_EMAIL,
            f"{cfg.icon} Don't forget your SAT {cfg.display_name} practice today!",
            f"Hi Sasha!\n\n"
            f"You've answered {q} out of {MIN_QUESTIONS} {cfg.display_name} questions today.\n"
            f"Your SAT exam is in {days_left} days — every session counts! 💪\n\n"
            f"Head to your SAT tutor and knock out a few more questions:\n"
            f"{APP_URL}\n\n"
            f"You've got this! 🌟"
        )

        send_email(
            PARENT_EMAIL,
            f"📚 Sasha hasn't completed today's SAT {cfg.display_name} practice",
            f"Hi!\n\n"
            f"This is an automated reminder that Sasha has answered {q} out of {MIN_QUESTIONS} "
            f"SAT {cfg.display_name} questions today (goal: {MIN_QUESTIONS}).\n\n"
            f"Her SAT exam is on {cfg.exam_date.strftime('%B %d, %Y')} ({days_left} days away).\n"
            f"Please encourage her to complete today's practice session!\n\n"
            f"— Sasha's SAT Tutor"
        )

        print(f"[alert] Alerts sent for {cfg.display_name} ({q}/{MIN_QUESTIONS} done).")
        sent = True

    if not sent:
        print("[alert] All goals met or exam passed — no alerts needed.")


if __name__ == "__main__":
    main()
