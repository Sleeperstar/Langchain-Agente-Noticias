"""Outlook sender node: usa pywin32 contra la sesion activa de Outlook Desktop."""
from __future__ import annotations

from agente_ia.config import get_recipient
from agente_ia.state import NewsState

OL_MAIL_ITEM = 0  # constante COM olMailItem


def _send_via_outlook(to: str, subject: str, html_body: str) -> str:
    """Crea y envia un correo HTML usando la sesion activa de Outlook.

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
        mail.HTMLBody = html_body
        mail.Send()
        return f"Correo enviado a {to} via Outlook Desktop."
    finally:
        pythoncom.CoUninitialize()


def outlook_sender_node(state: NewsState) -> dict:
    """Nodo del grafo que envia el correo (flujo automatico, sin HITL)."""
    to = get_recipient()
    subject = state.get("subject") or "Briefing IA - AI Engineer"
    html_body = state.get("html_body") or ""

    result = _send_via_outlook(to=to, subject=subject, html_body=html_body)
    print(f"[outlook_sender] {result}")
    return {"send_result": result}
