"""Wimoveis (mesmo grupo do Imovelweb): lê os cartões de anúncio da página."""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .base import Imovel, baixar, ld_json, numero, slug

log = logging.getLogger(__name__)
BASE = "https://www.wimoveis.com.br"
MAX_PAGINAS = 15
TIPOS = {"Apartment": "Apartamento", "House": "Casa", "SingleFamilyResidence": "Casa"}


def _tipos_por_id(html: str) -> dict[str, tuple[str, str]]:
    """id do anúncio -> (tipo, título) a partir do JSON-LD (RentAction)."""
    res = {}
    for b in ld_json(html):
        if isinstance(b, dict) and b.get("@type") == "RentAction":
            obj = b.get("object") or {}
            m = re.search(r"-(\d+)\.html", obj.get("url", ""))
            if m:
                t = obj.get("type", "")
                res[m.group(1)] = (TIPOS.get(t, t), obj.get("name", ""))
    return res


def buscar(cfg: dict, busca: dict) -> list[Imovel]:
    res: dict[str, Imovel] = {}
    for cidade in busca["cidades"]:
        for pagina in range(1, MAX_PAGINAS + 1):
            url = f"{BASE}/aluguel/imoveis/rs/{slug(cidade)}"
            if pagina > 1:
                url += f"?page={pagina}"
            html = baixar(url)
            tipos = _tipos_por_id(html)
            novos = 0
            for card in BeautifulSoup(html, "html.parser").select('[data-qa="posting PROPERTY"]'):
                id_ = card.get("data-id")
                if not id_ or id_ in res:
                    continue

                def txt(qa: str) -> str:
                    el = card.select_one(f'[data-qa="{qa}"]')
                    return el.get_text(" ", strip=True) if el else ""

                feats = txt("POSTING_CARD_FEATURES")
                q = re.search(r"(\d+)\s*quarto", feats)
                # "91 m² tot. 53 m² útil": usa a menor (área útil)
                areas = [numero(x) for x in re.findall(r"([\d.,]+)\s*m²", feats)]
                area = min((a for a in areas if a), default=None)
                local = txt("POSTING_CARD_LOCATION")
                tipo, nome = tipos.get(id_, ("", ""))
                caminho = (card.get("data-to-posting") or "").split("?")[0]
                foto = next((u for img in card.find_all("img")
                             for u in [img.get("src") or img.get("data-src") or ""]
                             if "/avisos/" in u), "")
                res[id_] = Imovel(
                    fonte="Wimoveis",
                    id=id_,
                    titulo=nome or f"{tipo} {feats}".strip(),
                    preco=numero(txt("POSTING_CARD_PRICE")),
                    cidade=cidade,
                    link=BASE + caminho if caminho else url,
                    tipo=tipo,
                    quartos=int(q.group(1)) if q else None,
                    area_m2=area,
                    bairro=local.split(",")[0].strip() if "," in local else "",
                    condominio=numero(txt("expensas")),
                    foto=foto.replace("/360x266/", "/720x532/"),
                )
                novos += 1
            if not novos:
                break
    log.info("Wimoveis: %d imóveis", len(res))
    return list(res.values())
