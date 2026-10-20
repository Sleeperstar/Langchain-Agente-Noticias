"""Outlook sender node: usa pywin32 contra la sesion activa de Outlook Desktop."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

from agente_noticias.config import LOGO_PATH, get_recipients
from agente_noticias.email_template import WIN_LOGO_CID
from agente_noticias.state import NewsState

OL_MAIL_ITEM = 0  # constante COM olMailItem
OL_BY_VALUE = 1  # olByValue para adjuntos
# MAPI property tags to embed an attachment by Content-ID (inline image).
PR_ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"
PR_ATTACH_HIDDEN = "http://schemas.microsoft.com/mapi/proptag/0x7FFE000B"


def attach_inline_images(
    mail, html_body: str, images: Iterable[tuple[str, str]]
) -> list[str]:
    """Attaches each (path, cid) referenced as `cid:<cid>` in `html_body` as a hidden
    inline image. Returns the attached CIDs; a failing image is logged and skipped."""
    attached: list[str] = []
    for path, cid in images:
        if f"cid:{cid}" not in html_body or not Path(path).is_file():
            continue
        try:
            attachment = mail.Attachments.Add(
                Source=str(path),
                Type=OL_BY_VALUE,
                Position=0,
                DisplayName=cid,
            )
            pa = attachment.PropertyAccessor
            pa.SetProperty(PR_ATTACH_CONTENT_ID, cid)
            pa.SetProperty(PR_ATTACH_HIDDEN, True)
            attached.append(cid)
        except Exception as exc:  # noqa: BLE001
            print(f"[outlook_sender] no se pudo embeber {cid}: {exc}")
    return attached


def _send_via_outlook(
    to: str,
    subject: str,
    html_body: str,
    inline_images: Iterable[tuple[str, str]] | None = None,
) -> str:
    """Crea y envia un correo HTML usando la sesion activa de Outlook.

    `inline_images` son pares (ruta, Content-ID) que el HTML referencia con `cid:`.
    Si es None se embebe solo el logo de WIN (compatibilidad).

    Requiere que Outlook Desktop este abierto y autenticado.

    LangGraph ejecuta los nodos en hilos de un executor; cada hilo necesita
    inicializar COM con `CoInitialize()` antes de usar Outlook (de lo contrario
    pywin32 lanza "No se ha llamado a CoInitialize"). Por eso inicializamos y
    liberamos COM en el hilo actual.
    """
    try:
        import pythoncom  # type: ignore[import-not-found]
        import win32com.client  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pywin32 no esta instalado. Ejecuta `uv add pywin32`."
        ) from exc

    if inline_images is None:
        inline_images = [(str(LOGO_PATH), WIN_LOGO_CID)]

    pythoncom.CoInitialize()
    try:
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "No se pudo conectar con Outlook. Abre Outlook Desktop y vuelve a intentar."
            ) from exc

        mail = outlook.CreateItem(OL_MAIL_ITEM)
        mail.To = to
        mail.Subject = subject

        # Embed images by CID (robust way to show them in Outlook).
        attach_inline_images(mail, html_body, inline_images)

        mail.HTMLBody = html_body
        mail.Send()
        return f"Correo enviado a {to} via Outlook Desktop."
    finally:
        pythoncom.CoUninitialize()


def outlook_sender_node(state: NewsState) -> dict:
    """Nodo del grafo que envia el correo (flujo automatico, sin HITL)."""
    recipients = get_recipients()
    to = "; ".join(recipients)
    subject = state.get("subject") or "Noticias IA - WIN Internet"
    html_body = state.get("html_body") or ""

    try:
        result = _send_via_outlook(
            to=to,
            subject=subject,
            html_body=html_body,
            inline_images=state.get("inline_images"),
        )
    except Exception as exc:  # noqa: BLE001 - Outlook closed, COM error, etc.
        error = f"ERROR: no se pudo enviar el correo via Outlook: {exc}"
        print(f"[outlook_sender] {error}", file=sys.stderr)
        return {"send_result": error, "send_ok": False}
    print(f"[outlook_sender] {result}")
    return {"send_result": result, "send_ok": True}
