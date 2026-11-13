"""Envio de mensagens pelo bot do Telegram."""
from __future__ import annotations

import html
import io
import logging
import os
import time

import requests

LIMITE = 4000          # o Telegram aceita até 4096 caracteres por mensagem
LIMITE_LEGENDA = 1024  # e até 1024 na legenda de uma foto
PAUSA = 1.1            # o Telegram limita ~1 mensagem por segundo no mesmo chat

log = logging.getLogger(__name__)


def _chamar(metodo: str, dados: dict, arquivos: dict | None = None) -> requests.Response:
    token = os.environ["TELEGRAM_TOKEN"]
    dados = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "parse_mode": "HTML", **dados}
    for _ in range(5):
        r = requests.post(f"https://api.telegram.org/bot{token}/{metodo}", data=dados, files=arquivos, timeout=60)
        if r.status_code == 429:  # muitas mensagens: espera o tempo pedido
            time.sleep(r.json().get("parameters", {}).get("retry_after", 5) + 1)
            continue
        time.sleep(PAUSA)
        return r
    return r


def _enviar(texto: str, silencioso: bool = False) -> None:
    r = _chamar("sendMessage", {
        "text": texto,
        "disable_web_page_preview": "true",
        "disable_notification": str(silencioso).lower(),
    })
    if not r.ok:
        raise RuntimeError(f"Telegram recusou a mensagem: {r.status_code} {r.text}")


def _jpeg(url: str) -> bytes:
    """Baixa a imagem e converte para JPEG (alguns sites entregam WebP, que o Telegram recusa)."""
    from PIL import Image

    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    saida = io.BytesIO()
    Image.open(io.BytesIO(r.content)).convert("RGB").save(saida, "JPEG", quality=88)
    return saida.getvalue()


def _enviar_foto(foto: str, legenda: str) -> None:
    """Manda a foto com o texto como legenda; se a foto falhar, manda só o texto."""
    if foto and len(legenda) <= LIMITE_LEGENDA:
        dados = {"caption": legenda, "disable_notification": "true"}
        r = _chamar("sendPhoto", {"photo": foto, **dados})
        if r.ok:
            return
        try:  # o Telegram não conseguiu usar o link: baixa, converte e manda o arquivo
            r = _chamar("sendPhoto", dados, arquivos={"photo": ("foto.jpg", _jpeg(foto), "image/jpeg")})
            if r.ok:
                return
        except Exception as e:
            log.warning("Não deu para converter a foto %s: %s", foto, e)
        log.warning("Foto recusada (%s), enviando só o texto: %s", r.status_code, foto)
    _enviar(legenda, silencioso=True)


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


def enviar_com_fotos(cabecalho: str, itens: list[tuple[str, str]], rodape: str = "") -> None:
    """Cabeçalho (com notificação), depois um imóvel por mensagem com foto (silenciosas)."""
    _enviar(cabecalho)
    for foto, texto in itens:
        _enviar_foto(foto, texto)
    if rodape:
        _enviar(rodape, silencioso=True)


def esc(texto) -> str:
    return html.escape(str(texto or ""), quote=False)
