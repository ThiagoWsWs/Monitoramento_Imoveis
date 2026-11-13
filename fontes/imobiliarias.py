"""Imobiliárias locais que usam a mesma plataforma de site (Altreiter, Bordin, Gramado Garden...).

A página "/alugar-imoveis" lista os aluguéis, com paginação "&pg=N".
O link de cada imóvel traz a categoria, ex.:
  /imovel/locacao-anual-apartamentos-01-dorm-em-gramado/apartamento-1-dormitorio-vero/1366
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .base import Imovel, baixar, humanizar_slug, normalizar, numero

log = logging.getLogger(__name__)
MAX_PAGINAS = 15

_RE = re.compile(
    r"/imovel/(?P<cat>locacao-[a-z0-9-]+?)-em-(?P<cidade>[a-z-]+)/(?P<nome>[^/]+)/(?P<id>\d+)/?$"
)


def _categoria(cat: str) -> tuple[str, int | None]:
    """'locacao-anual-apartamentos-01-dorm' -> ('Apartamentos', 1)."""
    q = re.search(r"-(\d+)-dorm", cat)
    tipo = re.sub(r"^locacao-(anual-)?", "", cat)
    tipo = re.sub(r"-\d+-dorm.*$", "", tipo)
    tipo = {"apartamentos": "apartamento", "casas": "casa"}.get(tipo, tipo)
    return humanizar_slug(tipo), (int(q.group(1)) if q else None)


def _um_site(nome_site: str, base: str, cidades: list[str]) -> list[Imovel]:
    alvo = {normalizar(c).replace(" ", "-"): c for c in cidades}
    res: dict[str, Imovel] = {}
    for pagina in range(1, MAX_PAGINAS + 1):
        url = f"{base}/alugar-imoveis" + (f"&pg={pagina}" if pagina > 1 else "")
        sopa = BeautifulSoup(baixar(url), "html.parser")
        novos = 0
        for card in sopa.select(".listing-item"):
            a = card.find("a", href=True)
            m = _RE.search(a["href"]) if a else None
            if not m or m["id"] in res:
                continue
            novos += 1
            if "temporada" in m["cat"] or m["cidade"] not in alvo:
                res[m["id"]] = None  # marca como visto, mas ignora
                continue
            tipo, quartos = _categoria(m["cat"])
            preco_el = card.select_one(".listing-price")
            titulo_el = card.select_one("h4, h3, .listing-title")
            res[m["id"]] = Imovel(
                fonte=nome_site,
                id=m["id"],
                titulo=" ".join(titulo_el.get_text(" ").split()) if titulo_el else humanizar_slug(m["nome"]),
                preco=numero(preco_el.get_text()) if preco_el else None,
                cidade=alvo[m["cidade"]],
                link=a["href"] if a["href"].startswith("http") else base + a["href"],
                tipo=tipo,
                quartos=quartos,
            )
        if not novos:
            break
    return [i for i in res.values() if i]


def buscar(cfg: dict, busca: dict) -> list[Imovel]:
    res = []
    for site in cfg.get("sites", []):
        try:
            achados = _um_site(site["nome"], site["url"].rstrip("/"), busca["cidades"])
            log.info("%s: %d imóveis", site["nome"], len(achados))
            res += achados
        except Exception as e:
            log.warning("%s falhou: %s", site["nome"], e)
    return res
