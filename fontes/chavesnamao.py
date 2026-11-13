"""Chaves na Mão: o link de cada anúncio já traz tipo, quartos, bairro, m² e preço.

Ex.: /imovel/apartamento-para-alugar-1-quarto-com-garagem-rs-gramado-centro-30m2-RS3000/id-47438001/
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .base import Imovel, baixar, humanizar_slug, slug

log = logging.getLogger(__name__)
BASE = "https://www.chavesnamao.com.br"
MAX_PAGINAS = 15

_RE = re.compile(
    r"/imovel/(?P<tipo>[a-z-]+?)-para-alugar(?:-(?P<q>\d+)-quartos?)?(?P<resto>.*?)"
    r"-rs-(?P<cidade>[a-z-]+?)-(?P<bairro>[a-z0-9-]*?)(?:-(?P<m2>\d+)m2)?-RS(?P<preco>\d+)/id-(?P<id>\d+)/?"
)


def buscar(cfg: dict, busca: dict) -> list[Imovel]:
    res: dict[str, Imovel] = {}
    for cidade in busca["cidades"]:
        cslug = slug(cidade)
        for pagina in range(1, MAX_PAGINAS + 1):
            url = f"{BASE}/imoveis-residenciais-para-alugar/rs-{cslug}/"
            if pagina > 1:
                url += f"?pg={pagina}"
            sopa = BeautifulSoup(baixar(url), "html.parser")
            novos = 0
            for a in sopa.find_all("a", href=True):
                m = _RE.search(a["href"])
                if not m or m["id"] in res:
                    continue
                # o nome da cidade no link pode se misturar com o bairro
                if not (m["cidade"] + "-" + m["bairro"]).startswith(cslug):
                    continue
                bairro = (m["cidade"] + "-" + m["bairro"])[len(cslug):].strip("-")
                titulo = a.get("title") or a.get_text(" ", strip=True)
                res[m["id"]] = Imovel(
                    fonte="Chaves na Mão",
                    id=m["id"],
                    titulo=titulo or humanizar_slug(m["tipo"]),
                    preco=float(m["preco"]),
                    cidade=cidade,
                    link=BASE + a["href"] if a["href"].startswith("/") else a["href"],
                    tipo=humanizar_slug(m["tipo"]),
                    quartos=int(m["q"]) if m["q"] else None,
                    area_m2=float(m["m2"]) if m["m2"] else None,
                    bairro=humanizar_slug(bairro).title() if bairro else "",
                )
                novos += 1
            if not novos:
                break
    log.info("Chaves na Mão: %d imóveis", len(res))
    return list(res.values())
