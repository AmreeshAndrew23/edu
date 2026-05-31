import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _build_otp_html(code: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f8fafc;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:40px 0;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e2e8f0;">
        <tr>
          <td style="background:linear-gradient(135deg,#1d4ed8,#3b82f6);padding:32px;text-align:center;">
            <div style="font-size:28px;font-weight:900;color:#ffffff;letter-spacing:-0.5px;">QuizThala</div>
            <div style="color:#bfdbfe;font-size:13px;margin-top:4px;">NEET Preparation Platform</div>
          </td>
        </tr>
        <tr>
          <td style="padding:36px 40px;">
            <p style="margin:0 0 8px;font-size:20px;font-weight:700;color:#1e293b;">Verify your email</p>
            <p style="margin:0 0 28px;font-size:14px;color:#64748b;line-height:1.6;">
              Use the code below to complete your QuizThala account setup.<br>
              It expires in <strong>10 minutes</strong>.
            </p>
            <div style="background:#f1f5f9;border:2px dashed #cbd5e1;border-radius:12px;padding:24px;text-align:center;margin-bottom:28px;">
              <div style="font-size:42px;font-weight:900;letter-spacing:12px;color:#1d4ed8;font-family:'Courier New',monospace;">{code}</div>
            </div>
            <p style="margin:0;font-size:13px;color:#94a3b8;">
              If you didn't request this code, you can safely ignore this email.
            </p>
          </td>
        </tr>
        <tr>
          <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;">
            <p style="margin:0;font-size:12px;color:#94a3b8;text-align:center;">
              &copy; 2025 QuizThala — NEET prep made smart
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


async def send_otp_email(to_email: str, code: str) -> None:
    if not settings.BREVO_API_KEY:
        logger.warning("BREVO_API_KEY not configured — OTP for %s is: %s", to_email, code)
        return

    async with httpx.AsyncClient() as client:
        response = await client.post(
            BREVO_URL,
            headers={
                "api-key": settings.BREVO_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "sender": {
                    "name": settings.EMAIL_FROM_NAME,
                    "email": settings.EMAIL_FROM_ADDRESS,
                },
                "to": [{"email": to_email}],
                "subject": f"{code} is your QuizThala verification code",
                "htmlContent": _build_otp_html(code),
            },
            timeout=10,
        )
        if response.status_code >= 400:
            logger.error("Brevo error %s: %s", response.status_code, response.text)
            raise RuntimeError(f"Brevo API error: {response.status_code}")
        logger.info("OTP email sent to %s via Brevo", to_email)
