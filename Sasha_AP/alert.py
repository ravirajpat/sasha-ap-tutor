#!/usr/bin/env python3
"""
Daily practice alert — run via GitHub Actions at 5 PM.
Sends email to Sasha and parent if she hasn't answered MIN_QUESTIONS today.
"""

import os
import smtplib
from datetime import date
from email.mime.text import MIMEText

from supabase import create_client

MIN_QUESTIONS = int(os.environ.get("MIN_QUESTIONS", "5") or "5")
SUPABASE_URL   = os.environ["SUPABASE_URL"]
SUPABASE_KEY   = os.environ["SUPABASE_KEY"]
GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
SASHA_EMAIL    = os.environ["SASHA_EMAIL"]
PARENT_EMAIL   = os.environ["PARENT_EMAIL"]


def get_today_questions() -> int:
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    result = sb.table("daily_progress").select("questions_answered").eq("date", date.today().isoformat()).execute()
    return result.data[0]["questions_answered"] if result.data else 0


def send_email(to: str, subject: str, body: str):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.send_message(msg)


def main():
    q = get_today_questions()
    print(f"Questions answered today: {q}/{MIN_QUESTIONS}")

    if q >= MIN_QUESTIONS:
        print("Goal met — no alerts needed.")
        return

    exam_days = (date(2026, 5, 6) - date.today()).days

    send_email(
        SASHA_EMAIL,
        "⚛️ Don't forget your physics practice today!",
        f"Hi Sasha!\n\n"
        f"You've answered {q} out of {MIN_QUESTIONS} practice questions today.\n"
        f"Your AP Physics 1 exam is in {exam_days} days — every session counts! 💪\n\n"
        f"Head to your tutor and knock out a few more questions:\n"
        f"https://share.streamlit.io\n\n"
        f"You've got this! 🌟"
    )

    send_email(
        PARENT_EMAIL,
        "📚 Sasha hasn't completed today's AP Physics practice",
        f"Hi!\n\n"
        f"This is an automated reminder that Sasha has answered {q} out of {MIN_QUESTIONS} "
        f"practice questions today (goal: {MIN_QUESTIONS}).\n\n"
        f"Her AP Physics 1 exam is on May 6, 2026 ({exam_days} days away).\n"
        f"Please encourage her to complete today's practice session!\n\n"
        f"— Sasha's AP Physics Tutor"
    )

    print(f"Alerts sent to Sasha and parent ({q}/{MIN_QUESTIONS} questions done).")


if __name__ == "__main__":
    main()
