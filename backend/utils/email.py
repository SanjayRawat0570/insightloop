from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os
from typing import List

SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'reports@example.com')


def send_report_email(recipients: List[str], report_name: str, pdf_url: str, summary: str):
    if not SENDGRID_API_KEY:
        raise RuntimeError("SENDGRID_API_KEY not configured")
    client = SendGridAPIClient(SENDGRID_API_KEY)
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=recipients,
        subject=f"{report_name}",
        html_content=f"<p>{summary}</p><p><a href='{pdf_url}'>View Report</a></p>",
    )
    return client.send(message)
