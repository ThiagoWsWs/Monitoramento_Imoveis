"""Monitor diário de aluguéis -> Telegram.

Uso:
    python main.py            # busca, envia no Telegram e salva o histórico
    python main.py --teste    # busca e mostra no terminal (não envia, não salva)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import tomllib
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import telegram
from fontes import chavesnamao, grupozap, imobiliarias, wimoveis
from fontes.base import Imovel, normalizar

RAIZ = Path(__file__).parent
ARQ_CONFIG = RAIZ / "config.toml"
ARQ_VISTOS = RAIZ / "dados" / "vistos.json"
DIAS_PARA_ESQUECER = 30  # anúncio sumido há mais que isso sai do histórico
FUSO = ZoneInfo("America/Sao_Paulo")

log = logging.getLogger("monitor")

FONTES = {
    # chave no config.toml: (nome exibido, função)
    "zap": ("ZAP Imóveis", grupozap.buscar_zap),
    "vivareal": ("Viva Real", grupozap.buscar_vivareal),
    "chavesnamao": ("Chaves na Mão", chavesnamao.buscar),
    "wimoveis": ("Wimoveis", wimoveis.buscar),
    "imobiliarias": ("Imobiliárias locais", imobiliarias.buscar),
}


def coletar(cfg: dict) -> tuple[list[Imovel], list[str]]:
    todos, falhas = [], []
    for chave, (nome, funcao) in FONTES.items():
        c = cfg.get("fontes", {}).get(chave, {})
        if not c.get("ativo", True):
            continue
        try:
            achados = funcao(c, cfg["busca"])
            if not achados:
                falhas.append(f"{nome} (nenhum resultado, o site pode ter mudado)")
            todos.extend(achados)
        except Exception as e:
            log.exception("Falha na fonte %s", nome)
            falhas.append(f"{nome} ({type(e).__name__})")
    return todos, falhas


def filtrar(imoveis: list[Imovel], busca: dict) -> list[Imovel]:
    qmin, qmax = busca.get("quartos_min", 0), busca.get("quartos_max", 99)
    pmin, pmax = busca.get("preco_min", 0), busca.get("preco_max", 0)
    excluir = [normalizar(p) for p in busca.get("palavras_excluir", [])]
    tipos_excl = [normalizar(p) for p in busca.get("tipos_excluir", [])]
    ok = []
    for i in imoveis:
        if i.quartos is None or not (qmin <= i.quartos <= qmax):
            continue
        if i.preco is not None and (i.preco < pmin or (pmax and i.preco > pmax)):
            continue
        titulo, tipo = f" {normalizar(i.titulo)} ", normalizar(i.tipo)
        if any(f" {p} " in titulo for p in excluir):
            continue
        if any(p in tipo for p in tipos_excl):
            continue
        ok.append(i)
    return ok


def _mesmo_imovel(a: Imovel, b: Imovel) -> bool:
    # ZAP e Viva Real compartilham o mesmo ID de anúncio.
    if {a.fonte, b.fonte} == {"ZAP", "Viva Real"}:
        return a.id == b.id
    if normalizar(a.cidade) != normalizar(b.cidade) or a.preco != b.preco or a.preco is None:
        return False
    na, nb = normalizar(a.bairro), normalizar(b.bairro)
    mesmo_bairro = bool(na and nb and (na.startswith(nb) or nb.startswith(na)))
    bairro_diferente = bool(na and nb) and not mesmo_bairro
    if a.area_m2 and b.area_m2:
        # sites às vezes rotulam o bairro diferente; aí exige área idêntica
        return abs(a.area_m2 - b.area_m2) < (0.5 if bairro_diferente else 3.5)
    return mesmo_bairro


def agrupar(imoveis: list[Imovel]) -> list[Imovel]:
    """Junta o mesmo imóvel anunciado em sites diferentes."""
    unicos: list[Imovel] = []
    for a in imoveis:
        par = next(
            (b for b in unicos
             if b.fonte != a.fonte
             and all(d.fonte != a.fonte for d in b.duplicados)
             and _mesmo_imovel(a, b)),
            None,
        )
        if par:
            par.duplicados.append(a)
            # completa dados que faltam no principal
            par.area_m2 = par.area_m2 or a.area_m2
            par.bairro = par.bairro or a.bairro
            par.condominio = par.condominio or a.condominio
        else:
            unicos.append(a)
    return unicos


def comparar(imoveis: list[Imovel], vistos: dict, hoje: str):
    novos, baixaram = [], []
    for a in imoveis:
        anteriores = [vistos[k] for k in a.todas_chaves if k in vistos]
        if not anteriores:
            novos.append(a)
        else:
            precos = [v["preco"] for v in anteriores if v["preco"]]
            if a.preco and precos and a.preco < min(precos):
                baixaram.append((a, min(precos)))
        primeiro = min((v["primeiro"] for v in anteriores), default=hoje)
        for x in [a] + a.duplicados:
            vistos[x.chave] = {"preco": x.preco, "titulo": x.titulo, "primeiro": primeiro, "ultimo": hoje}
    limite = (datetime.fromisoformat(hoje) - timedelta(days=DIAS_PARA_ESQUECER)).date().isoformat()
    for k in [k for k, v in vistos.items() if v["ultimo"] < limite]:
        del vistos[k]
    return novos, baixaram


def reais(v: float | None) -> str:
    return "Consulte" if not v else f"R$ {v:,.0f}".replace(",", ".")


def bloco(i: Imovel, extra: str = "") -> str:
    e = telegram.esc

    def href(x: Imovel) -> str:
        return e(x.link).replace('"', "&quot;")

    cabeca = " · ".join(p for p in [i.tipo, f"{i.quartos} quarto{'s' if (i.quartos or 0) > 1 else ''}",
                                   f"{i.area_m2:.0f} m²" if i.area_m2 else ""] if p)
    valor = f"💰 {reais(i.preco)}/mês"
    if i.condominio:
        valor += f" + cond. {reais(i.condominio)}"
    local = f"📍 {e(i.bairro) + ', ' if i.bairro else ''}{e(i.cidade)}"
    fontes = e(i.fonte) + "".join(f' · <a href="{href(d)}">{e(d.fonte)}</a>' for d in i.duplicados)
    return "\n".join([
        f'🏠 <b><a href="{href(i)}">{e(cabeca)}</a></b>',
        f"{valor}{extra}",
        local,
        f"🔗 {fontes}",
    ])


def montar_mensagem(cfg, novos, baixaram, total, falhas):
    b, env = cfg["busca"], cfg.get("envio", {})
    maximo = env.get("max_por_dia", 40)
    data = datetime.now(FUSO).strftime("%d/%m")
    q = b["quartos_min"] if b["quartos_min"] == b["quartos_max"] else f"{b['quartos_min']}–{b['quartos_max']}"
    cab = (
        f"🔑 <b>Aluguel em {telegram.esc(' e '.join(b['cidades']))}</b> · {q} quarto(s) · {data}\n"
        f"<b>{len(novos)}</b> novos · <b>{len(baixaram)}</b> baixaram de preço · "
        f"{total} disponíveis no total"
    )
    chave = lambda i: i.preco or 10**9  # "Consulte" vai pro fim
    blocos = [bloco(a, f"  📉 <s>{reais(antes)}</s>") for a, antes in sorted(baixaram, key=lambda x: chave(x[0]))[:maximo]]
    blocos += [bloco(a) for a in sorted(novos, key=chave)[: max(0, maximo - len(blocos))]]
    rodape = []
    resto = len(novos) + len(baixaram) - len(blocos)
    if resto > 0:
        rodape.append(f"➕ Mais {resto} anúncios não mostrados (limite de {maximo} por dia).")
    if falhas:
        rodape.append("⚠️ Fontes com problema hoje: " + ", ".join(telegram.esc(f) for f in falhas))
    return cab, blocos, "\n".join(rodape)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--teste", action="store_true", help="não envia nem salva; só mostra")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cfg = tomllib.loads(ARQ_CONFIG.read_text(encoding="utf-8"))
    brutos, falhas = coletar(cfg)
    filtrados = filtrar(brutos, cfg["busca"])
    imoveis = agrupar(filtrados)
    log.info("%d anúncios brutos, %d nos filtros, %d imóveis únicos", len(brutos), len(filtrados), len(imoveis))

    vistos = json.loads(ARQ_VISTOS.read_text(encoding="utf-8")) if ARQ_VISTOS.exists() else {}
    primeira_vez = not vistos
    hoje = datetime.now(FUSO).date().isoformat()
    novos, baixaram = comparar(imoveis, vistos, hoje)
    cab, blocos, rodape = montar_mensagem(cfg, novos, baixaram, len(imoveis), falhas)
    if primeira_vez:
        cab += ("\n\n👋 <i>Primeira execução: todos os anúncios atuais contam como novos. "
                "A partir de amanhã chegam só as novidades.</i>")

    if args.teste:
        sys.stdout.reconfigure(encoding="utf-8")
        print("\n" + cab + "\n\n" + "\n\n".join(blocos) + ("\n\n" + rodape if rodape else ""))
        return 0

    if blocos or falhas or cfg.get("envio", {}).get("avisar_sem_novidades", True):
        if not blocos:
            cab += "\n\nNenhum anúncio novo hoje. 😴"
        telegram.enviar_blocos(cab, blocos, rodape)

    ARQ_VISTOS.parent.mkdir(exist_ok=True)
    ARQ_VISTOS.write_text(json.dumps(vistos, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    return 1 if not brutos and falhas else 0


if __name__ == "__main__":
    sys.exit(main())
