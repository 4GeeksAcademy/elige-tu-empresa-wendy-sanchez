"""Servicio de correo transaccional para HealthCore usando Resend.

La API key de Resend se lee exclusivamente de la variable de entorno
``RESEND_API_KEY``. Nunca debe aparecer hardcodeada en el código fuente.

Para desarrollo, si ``RESEND_API_KEY`` no está definida, el envío se
simula en consola (log) para permitir probar el flujo sin conexión real.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
import requests

load_dotenv()

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM = os.getenv("RESEND_FROM", "HealthCore <no-reply@healthcore.com>")
RESEND_API_URL = "https://api.resend.com/emails"

# Enlace base que se usa en el correo de restablecimiento. En producción
# debe apuntar al dominio del frontend. En desarrollo, a localhost.
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")


def send_password_reset_email(email: str, reset_token: str) -> None:
    """Envía un correo transaccional con el enlace de restablecimiento.

    El enlace incluye el token firmado en el query string de la URL.
    Si no hay RESEND_API_KEY configurada, simula el envío en consola.
    """
    reset_url = f"{FRONTEND_BASE_URL}/reset-password?token={reset_token}"

    subject = "Restablece tu contraseña de HealthCore"
    html = _build_reset_email_html(reset_url)
    text = _build_reset_email_text(reset_url)

    if not RESEND_API_KEY:
        logger.warning(
            "RESEND_API_KEY no configurada. Simulando envío de restablecimiento "
            "para %s (enlace: %s)",
            email,
            reset_url,
        )
        return

    try:
        response = requests.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_FROM,
                "to": [email],
                "subject": subject,
                "html": html,
                "text": text,
            },
            timeout=15,
        )
        response.raise_for_status()
        logger.info("Correo de restablecimiento enviado a %s", email)
    except Exception:
        # Nunca propagamos el error al cliente: /forgot-password debe devolver
        # siempre 200 para no revelar si el email existe.
        # Capturamos Exception en lugar de solo RequestException para cubrir
        # errores de red inesperados (socket.gaierror, Timeout, etc.).
        # El mensaje de la excepción no se registra para evitar exponer
        # la API key o datos sensibles en los logs.
        logger.error(
            "Error al enviar correo de restablecimiento a %s",
            email,
            exc_info=False,
        )


def _build_reset_email_text(reset_url: str) -> str:
    return (
        "HealthCore\n"
        "----------\n\n"
        "Has solicitado restablecer tu contraseña.\n\n"
        "Pulsa el siguiente enlace para elegir una nueva contraseña:\n"
        f"{reset_url}\n\n"
        "Si no solicitaste este cambio, puedes ignorar este correo.\n"
        "El enlace expira en 30 minutos.\n"
    )


def _build_reset_email_html(reset_url: str) -> str:
    """HTML legible en móvil: single-column layout, botón grande táctil."""
    return f"""\
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Restablece tu contraseña</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f1f5f9;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%;background-color:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e2e8f0;">
          <tr>
            <td style="padding:32px 28px 24px;">
              <p style="margin:0 0 4px;font-size:11px;font-weight:600;letter-spacing:0.16em;text-transform:uppercase;color:#0e7490;">
                HealthCore
              </p>
              <h1 style="margin:0 0 12px;font-size:22px;font-weight:700;color:#0f172a;">
                Restablece tu contraseña
              </h1>
              <p style="margin:0 0 20px;font-size:15px;line-height:1.5;color:#475569;">
                Hemos recibido una solicitud para restablecer la contraseña
                asociada a tu cuenta. Pulsa el botón para elegir una nueva:
              </p>
              <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin:0 0 20px;">
                <tr>
                  <td align="center">
                    <a href="{reset_url}"
                       style="display:inline-block;background-color:#0891b2;color:#ffffff;text-decoration:none;font-size:16px;font-weight:600;padding:14px 28px;border-radius:10px;">
                      Restablecer contraseña
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 12px;font-size:13px;line-height:1.5;color:#64748b;">
                Si el botón no funciona, copia y pega este enlace en tu navegador:
              </p>
              <p style="margin:0 0 20px;font-size:12px;line-height:1.5;color:#0891b2;word-break:break-all;">
                {reset_url}
              </p>
              <p style="margin:0;font-size:12px;line-height:1.5;color:#94a3b8;">
                Si no solicitaste este cambio, puedes ignorar este correo.
                El enlace expira en 30 minutos.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
