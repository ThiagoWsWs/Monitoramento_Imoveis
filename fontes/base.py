"""Estruturas e utilitários comuns às fontes."""
from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import dataclass, field

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}
PAUSA_ENTRE_REQUISICOES = 1.0  # segundos, para não sobrecarregar os sites

_sessao = requests.Session()
_sessao.headers.update(HEADERS)


@dataclass
class Imovel:
    fonte: str
    id: str
    titulo: str
    preco: float | None          # aluguel mensal (None = "consulte")
    cidade: str
    link: str
    tipo: str = ""               # Apartamento, Casa, Studio...
    quartos: int | None = None
    area_m2: float | None = None
    bairro: str = ""
    condominio: float | None = None
    duplicados: list["Imovel"] = field(default_factory=list, compare=False, repr=False)

    @property
    def chave(self) -> str:
        return f"{self.fonte}:{self.id}"

    @property
    def todas_chaves(self) -> list[str]:
        return [self.chave] + [d.chave for d in self.duplicados]


def baixar(url: str) -> str:
    """GET simples com pausa educada e texto em UTF-8."""
    for tentativa in range(3):
        time.sleep(PAUSA_ENTRE_REQUISICOES * (1 + tentativa * 5))
        try:
            r = _sessao.get(url, timeout=90)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except requests.RequestException:
            if tentativa == 2:
                raise
    raise RuntimeError("inalcançável")


def ld_json(html: str) -> list:
    """Todos os blocos JSON-LD (schema.org) da página."""
    blocos = []
    for b in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            blocos.append(json.loads(b))
        except ValueError:
            pass
    return blocos


def normalizar(texto: str) -> str:
    """'São Leopoldo' -> 'sao leopoldo' (sem acento, minúsculo)."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9]+", " ", t.lower())
    return t.strip()


def slug(texto: str) -> str:
    return normalizar(texto).replace(" ", "-")


def numero(texto) -> float | None:
    """'R$ 3.500,00' -> 3500.0 ; '58 m²' -> 58.0 ; None/'' -> None."""
    if texto is None:
        return None
    if isinstance(texto, (int, float)):
        return float(texto)
    m = re.search(r"\d[\d.]*(,\d+)?", str(texto))
    if not m:
        return None
    return float(m.group(0).replace(".", "").replace(",", "."))


def humanizar_slug(s: str) -> str:
    """'apartamento-1-dormitorio-vero' -> 'Apartamento 1 dormitorio vero'."""
    return s.replace("-", " ").strip().capitalize()
