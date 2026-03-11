import smtplib
from email.mime.text import MIMEText

from mlflow_oidc_auth.logger import get_logger

logger = get_logger()


def send_quota_email(to_address: str, subject: str, body: str) -> bool:
    """Send a quota notification email via SMTP.

    Returns True if sent successfully, False otherwise.
    """
    from mlflow_oidc_auth.config import config

    if not to_address:
        logger.warning("Cannot send quota email: no recipient address provided")
        return False

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = config.QUOTA_SMTP_FROM
    msg["To"] = to_address

    try:
        if config.QUOTA_SMTP_TLS:
            server = smtplib.SMTP(config.QUOTA_SMTP_HOST, config.QUOTA_SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP(config.QUOTA_SMTP_HOST, config.QUOTA_SMTP_PORT)

        if config.QUOTA_SMTP_USERNAME and config.QUOTA_SMTP_PASSWORD:
            server.login(config.QUOTA_SMTP_USERNAME, config.QUOTA_SMTP_PASSWORD)

        server.sendmail(config.QUOTA_SMTP_FROM, [to_address], msg.as_string())
        server.quit()
        logger.info(f"Quota email sent to {to_address}: {subject}")
        return True
    except Exception as e:
        logger.warning(f"Failed to send quota email to {to_address}: {e}")
        return False


def send_soft_cap_warning(username: str, used_bytes: int, quota_bytes: int, pct: float, email_address: str = None) -> bool:
    if not email_address:
        logger.debug(f"Skipping soft-cap warning for {username}: no email address on record")
        return False
    used_mb = used_bytes / (1024 * 1024)
    quota_mb = quota_bytes / (1024 * 1024)
    subject = f"MLflow storage quota warning: {pct:.0%} used"
    body = (
        f"Dear {username},\n\n"
        f"You are approaching your MLflow artifact storage quota.\n\n"
        f"  Used:  {used_mb:.1f} MB\n"
        f"  Quota: {quota_mb:.1f} MB\n"
        f"  Usage: {pct:.1%}\n\n"
        f"Please delete unused experiments or artifacts to free up space.\n"
        f"When your quota is reached, new runs and artifact uploads will be blocked.\n"
    )
    return send_quota_email(email_address, subject, body)


def send_hard_cap_notification(username: str, used_bytes: int, quota_bytes: int, email_address: str = None) -> bool:
    if not email_address:
        logger.debug(f"Skipping hard-cap notification for {username}: no email address on record")
        return False
    used_mb = used_bytes / (1024 * 1024)
    quota_mb = quota_bytes / (1024 * 1024)
    subject = "MLflow storage quota exceeded — uploads blocked"
    body = (
        f"Dear {username},\n\n"
        f"Your MLflow artifact storage quota has been reached.\n\n"
        f"  Used:  {used_mb:.1f} MB\n"
        f"  Quota: {quota_mb:.1f} MB\n\n"
        f"New experiment creation, run creation, and artifact uploads are now blocked.\n"
        f"Please delete unused experiments or artifacts to restore access.\n"
    )
    return send_quota_email(email_address, subject, body)
