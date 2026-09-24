"""Scraping de notícias como fallback documentado (RF-07).

Seletores/padrões vivem em `config.json` (secao 13), de modo que mudanças de
layout exijam ajuste de configuração, não reescrita da lógica. Usa apenas a
biblioteca padrão (html.parser) para manter o consumo de memória baixo.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

import requests

from comum import config
from comum.logger import get_logger

log = get_logger("noticias.scraping")


class _ExtratorLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._href: str | None = None
        self._texto: list[str] = []
        self.itens: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._texto = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._texto.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            texto = " ".join(t.strip() for t in self._texto if t.strip())
            if texto:
                self.itens.append((texto, self._href))
            self._href = None
            self._texto = []


def coletar(fontes: list[dict[str, Any]], minimo_titulo: int = 30) -> list[dict[str, Any]]:
    """Extrai manchetes/links segundo `padrao_link` (regex) de cada fonte."""
    itens: list[dict[str, Any]] = []
    for fonte in fontes:
        url = fonte.get("url")
        if not url:
            continue
        padrao = fonte.get("padrao_link", r".*")
        nome = fonte.get("nome", url)
        try:
            resp = requests.get(
                url,
                timeout=config.HTTP_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (compatible; TradingSystemWCN/1.0)"},
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            log.warning("scraping falhou (%s): %s", nome, exc)
            continue

        parser = _ExtratorLinks()
        try:
            parser.feed(resp.text)
        except Exception as exc:  # noqa: BLE001
            log.warning("parse HTML falhou (%s): %s", nome, exc)
            continue

        regex = re.compile(padrao)
        vistos: set[str] = set()
        for texto, href in parser.itens:
            if len(texto) < minimo_titulo or texto in vistos:
                continue
            if not regex.search(href or ""):
                continue
            vistos.add(texto)
            itens.append(
                {"titulo": texto, "link": href, "resumo": None, "fonte": nome, "publicado_em": None}
            )
    return itens
