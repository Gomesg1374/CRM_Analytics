"""
Email notification for ETL failures.

Configure via environment variables (or .env file):
  SMTP_HOST  — default: smtp.gmail.com
  SMTP_PORT  — default: 587  (STARTTLS)
  SMTP_USER  — Gmail address used to send (e.g. ops@example.com)
  SMTP_PASS  — Gmail App Password (NOT the account password)
              Generate at: myaccount.google.com/apppasswords
  NOTIFY_TO  — recipient address; defaults to SMTP_USER if omitted
"""
import os
import smtplib
import socket
import traceback
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
NOTIFY_TO = os.getenv("NOTIFY_TO", "") or SMTP_USER


def send_failure_email(subject: str, body: str) -> None:
    """
    Sends a failure notification email.
    Returns silently (never raises) if SMTP credentials are not configured.
    """
    if not SMTP_USER or not SMTP_PASS:
        print("  [!] Notificacao por e-mail nao enviada -- configure SMTP_USER e SMTP_PASS.")
        return

    to  = NOTIFY_TO or SMTP_USER
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    host = socket.gethostname()

    msg = MIMEMultipart()
    msg["Subject"] = f"[CRM ETL] {subject} — {now} ({host})"
    msg["From"]    = SMTP_USER
    msg["To"]      = to

    plain = (
        f"CRM Analytics ETL — falha em {now}\n"
        f"Máquina: {host}\n"
        f"{'=' * 60}\n\n"
        f"{body}"
    )
    msg.attach(MIMEText(plain, "plain", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.sendmail(SMTP_USER, [to], msg.as_string())
        print(f"  [ok] Notificacao enviada para {to}")
    except Exception as exc:
        print(f"  [!] Falha ao enviar e-mail de notificacao: {exc}")
