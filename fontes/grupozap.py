"""ZAP Imóveis e Viva Real (mesmo grupo, mesmo formato schema.org e mesmos IDs)."""
from __future__ import annotations

import logging
import re

from .base import Imovel, baixar, ld_json, numero, slug

log = logging.getLogger(__name__)
MAX_PAGINAS = 15

TIPOS = {
    "Apartment": "Apartamento", "House": "Casa", "SingleFamilyResidence": "Casa",
    "Residence": "Residência", "Store": "Loja", "OfficeBuilding": "Sala comercial",
    "LandForm": "Terreno", "Place": "Imóvel",
}


def _itens(html: str) -> list[dict]:
    for b in ld_json(html):
        if isinstance(b, dict) and b.get("@type") == "ItemList":
            return [e.get("item") or {} for e in b.get("itemListElement", [])]
    return []


def _converter(fonte: str, it: dict, cidade: str) -> Imovel:
    oferta = it.get("offers") or {}
    extra = oferta.get("additionalProperty") or {}
    if isinstance(extra, list):
        extra = next((e for e in extra if "Condo" in e.get("name", "")), {})
    nome = it.get("name", "")
    m = re.search(r"\sem\s+(.+?),\s*[^,]+$", nome)
    tipo_en = (it.get("additionalType") or "").rsplit("/", 1)[-1]
    return Imovel(
        fonte=fonte,
        id=str(it.get("@id")),
        titulo=nome,
        preco=numero(oferta.get("price")),
        cidade=(it.get("address") or {}).get("addressLocality") or cidade,
        link=it.get("url", ""),
        tipo=TIPOS.get(tipo_en, tipo_en),
        quartos=it.get("numberOfBedrooms"),
        area_m2=numero((it.get("floorSize") or {}).get("value")),
        bairro=m.group(1).strip() if m else "",
        condominio=numero(extra.get("value")) if "Condo" in extra.get("name", "") else None,
    )


def _paginar(fonte: str, url_base: str, cidade: str) -> list[Imovel]:
    vistos: dict[str, Imovel] = {}
    for pagina in range(1, MAX_PAGINAS + 1):
        url = url_base if pagina == 1 else f"{url_base}?pagina={pagina}"
        itens = _itens(baixar(url))
        novos = [i for i in itens if str(i.get("@id")) not in vistos]
        if not novos:
            break
        for it in novos:
            vistos[str(it.get("@id"))] = _converter(fonte, it, cidade)
    return list(vistos.values())


def buscar_zap(cfg: dict, busca: dict) -> list[Imovel]:
    # O ZAP aceita o filtro de quartos na URL (só quando é um número exato).
    q = busca["quartos_min"]
    filtro = f"{q}-quarto{'s' if q > 1 else ''}/" if q == busca["quartos_max"] else ""
    res = []
    for cidade in busca["cidades"]:
        res += _paginar("ZAP", f"https://www.zapimoveis.com.br/aluguel/imoveis/rs+{slug(cidade)}/{filtro}", cidade)
    log.info("ZAP: %d imóveis", len(res))
    return res


def buscar_vivareal(cfg: dict, busca: dict) -> list[Imovel]:
    res = []
    for cidade in busca["cidades"]:
        res += _paginar("Viva Real", f"https://www.vivareal.com.br/aluguel/rio-grande-do-sul/{slug(cidade)}/", cidade)
    log.info("Viva Real: %d imóveis", len(res))
    return res
