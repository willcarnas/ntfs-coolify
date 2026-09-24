"""Cliente HTTP mínimo da API de bots do Telegram (sem dependências pesadas).

Isola toda a comunicação externa (secao 13) com timeout agressivo.
"""
from __future__ import annotations

from typing import Any, Optional

import requests

from comum import config
from comum.logger import get_logger

log = get_logger("telegram.bot")

BASE = "https://api.telegram.org/bot{token}/{metodo}"


def configurado() -> bool:
    return bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)


def _chamar(metodo: str, timeout: Optional[float] = None, **params: Any) -> Optional[dict[str, Any]]:
    if not config.TELEGRAM_BOT_TOKEN:
        return None
    url = BASE.format(token=config.TELEGRAM_BOT_TOKEN, metodo=metodo)
    try:
        resp = requests.post(url, json=params, timeout=timeout or config.HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("telegram %s falhou: %s", metodo, exc)
        return None


def enviar_mensagem(texto: str, chat_id: Optional[str] = None) -> bool:
    destino = chat_id or config.TELEGRAM_CHAT_ID
    if not config.TELEGRAM_BOT_TOKEN or not destino:
        return False
    dados = _chamar(
        "sendMessage",
        chat_id=destino,
        text=texto,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    return bool(dados and dados.get("ok"))


def obter_updates(offset: Optional[int] = None, timeout: int = 5) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset is not None:
        params["offset"] = offset
    dados = _chamar("getUpdates", timeout=config.HTTP_TIMEOUT + timeout, **params)
    if not dados or not dados.get("ok"):
        return []
    return dados.get("result", []) or []


def formatar_alerta(payload: dict[str, Any]) -> str:
    """Monta a mensagem HTML rastreável (RF-10: fontes + indicadores-chave)."""
    if payload.get("tipo") == "saude" or payload.get("mensagem"):
        return str(payload.get("mensagem") or "⚠ Alerta de sistema")
    tipo = (payload.get("tipo") or "").upper()
    emoji = {"COMPRA": "🟢", "VENDA": "🔴"}.get(tipo, "⚪")
    linhas = [
        f"{emoji} <b>{tipo} — {payload.get('ativo')}</b> ({payload.get('classe')})",
        f"Confiança: <b>{float(payload.get('confianca') or 0)*100:.0f}%</b> | Preço: {payload.get('preco')}",
        "",
        "<b>Fatores:</b>",
    ]
    fatores = payload.get("fatores") or []
    for f in fatores[:6]:
        desc = f.get("descricao") or f.get("nome")
        linhas.append(f"• {desc}")
    fontes = payload.get("fontes") or []
    if fontes:
        linhas.append("")
        linhas.append(f"Fontes: {', '.join(fontes)}")
    if payload.get("dados_desatualizados"):
        linhas.append("⚠ Dados desatualizados.")
    linhas.append(f"<i>Sinal #{payload.get('sinal_id')} • {payload.get('criado_em')}</i>")
    return "\n".join(linhas)
