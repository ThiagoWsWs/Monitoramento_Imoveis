"""Envio de mensagens pelo bot do Telegram."""
from __future__ import annotations

import html
import os

import requests

LIMITE = 4000  # o Telegram aceita até 4096 caracteres por mensagem


def _enviar(texto: str) -> None:
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": texto,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(f"Telegram recusou a mensagem: {r.status_code} {r.text}")


def enviar_blocos(cabecalho: str, blocos: list[str], rodape: str = "") -> None:
    """Junta os blocos em mensagens de até LIMITE caracteres e envia."""
    msgs, atual = [], cabecalho
    for b in blocos:
        if len(atual) + len(b) + 2 > LIMITE:
            msgs.append(atual)
            atual = ""
        atual = f"{atual}\n\n{b}" if atual else b
    if rodape:
        atual = f"{atual}\n\n{rodape}" if atual else rodape
    if atual:
        msgs.append(atual)
    for m in msgs:
        _enviar(m)


def esc(texto) -> str:
    return html.escape(str(texto or ""), quote=False)
