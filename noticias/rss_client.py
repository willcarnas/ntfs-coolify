"""Coleta de notícias via RSS (fonte primária, RF-07)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from comum.logger import get_logger

log = get_logger("noticias.rss")

try:
    import feedparser  # type: ignore

    DISPONIVEL = True
except Exception as exc:  # pragma: no cover
    feedparser = None
    DISPONIVEL = False
    log.warning("feedparser indisponível: %s", exc)


def _data_publicacao(entry: Any) -> str | None:
    for attr in ("published_parsed", "updated_parsed"):
        valor = getattr(entry, attr, None)
        if valor:
            try:
                return datetime(*valor[:6], tzinfo=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            except (TypeError, ValueError):
                continue
    return None


def coletar(feeds: list[dict[str, str]], limite_por_feed: int = 20) -> list[dict[str, Any]]:
    """Lê os feeds configurados e devolve itens normalizados."""
    if not DISPONIVEL:
        return []
    itens: list[dict[str, Any]] = []
    for feed in feeds:
        url = feed.get("url")
        nome = feed.get("nome", url or "rss")
        if not url:
            continue
        try:
            parsed = feedparser.parse(url)
            if getattr(parsed, "bozo", 0) and not parsed.entries:
                log.warning("RSS sem entradas (%s): %s", nome, url)
                continue
            for entry in parsed.entries[:limite_por_feed]:
                titulo = (getattr(entry, "title", "") or "").strip()
                if not titulo:
                    continue
                itens.append(
                    {
                        "titulo": titulo,
                        "link": getattr(entry, "link", None),
                        "resumo": (getattr(entry, "summary", "") or "")[:500],
                        "fonte": nome,
                        "publicado_em": _data_publicacao(entry),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("falha ao ler feed %s: %s", nome, exc)
    return itens
