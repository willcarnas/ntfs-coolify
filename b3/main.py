"""Módulo de coleta B3 (RF-01).

Serviço independente. Coleta histórico e cotação de ações/índices via cascata
`mercados -> brapi -> yfinance`, além das séries macro do BCB. Grava tudo no
banco com fonte e timestamp (secao 6). Nunca importa código de outro domínio.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from comum import config, db, repo  # noqa: E402
from comum.circuit_breaker import CircuitBreaker  # noqa: E402
from comum.contratos_dados import Cotacao, Vela  # noqa: E402
from comum.servico import Servico, modo_uma_vez  # noqa: E402
from coletores import bcb_client, brapi_client, mercados_client, yfinance_client  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
CFG = config.load_json(CONFIG_PATH, {})

MODULO = "b3"

# Um circuit breaker por fonte, compartilhados entre ativos do módulo.
CB_BRAPI = CircuitBreaker("b3.brapi", max_falhas=3, cooldown_segundos=300)
CB_YF = CircuitBreaker("b3.yfinance", max_falhas=3, cooldown_segundos=300)
CB_BCB = CircuitBreaker("b3.bcb", max_falhas=3, cooldown_segundos=600)


def _ts_para_iso(ts: Any) -> Optional[str]:
    """Normaliza datetime/epoch para ISO-8601 UTC."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        try:
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            return db.iso(dt)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return db.iso(ts)
    if isinstance(ts, str):
        dt = db.parse_iso(ts)
        return db.iso(dt) if dt else ts
    return None


def _velas_da_cascata(ativo_cfg: dict[str, Any], periodo: str, intervalo: str) -> tuple[list[Vela], str, Optional[str], Optional[float]]:
    """Percorre mercados -> brapi -> yfinance. Devolve (velas, fonte, preço, variação).

    Introduzido o circuit breaker: se uma fonte está aberta, é pulada.
    """
    simbolo = ativo_cfg["simbolo"]

    # 1) mercados (oficial, histórico)
    if mercados_client.DISPONIVEL:
        brutos = mercados_client.cotacao_historica(simbolo)
        velas = _normalizar_mercados(brutos)
        if velas:
            return velas, "mercados", velas[-1].fechamento, None

    # 2) brapi (sessão em curso)
    if CB_BRAPI.disponivel:
        pontos = CB_BRAPI.chamar(brapi_client.historico, ativo_cfg.get("brapi", simbolo), periodo, intervalo)
        velas = _normalizar_brapi(pontos)
        if velas:
            preco = velas[-1].fechamento
            anterior = velas[-2].fechamento if len(velas) > 1 else None
            variacao = ((preco - anterior) / anterior * 100.0) if preco and anterior else None
            return velas, "brapi", preco, variacao

    # 3) yfinance (fallback)
    if CB_YF.disponivel:
        pontos = CB_YF.chamar(yfinance_client.historico, ativo_cfg.get("yf", simbolo), periodo, intervalo)
        velas = _normalizar_yfinance(pontos)
        if velas:
            preco = velas[-1].fechamento
            anterior = velas[-2].fechamento if len(velas) > 1 else None
            variacao = ((preco - anterior) / anterior * 100.0) if preco and anterior else None
            return velas, "yfinance", preco, variacao

    return [], "indisponivel", None, None


def _normalizar_brapi(pontos: Any) -> list[Vela]:
    velas = []
    for p in pontos or []:
        ts = _ts_para_iso(p.get("ts_epoch"))
        if not ts:
            continue
        velas.append(
            Vela(
                ativo="", classe="b3", timeframe="1d", ts=ts,
                abertura=p.get("abertura"), maxima=p.get("maxima"), minima=p.get("minima"),
                fechamento=p.get("fechamento"), volume=p.get("volume"), fonte="brapi",
            )
        )
    return velas


def _normalizar_yfinance(pontos: Any) -> list[Vela]:
    velas = []
    for p in pontos or []:
        ts = _ts_para_iso(p.get("ts"))
        if not ts:
            continue
        velas.append(
            Vela(
                ativo="", classe="b3", timeframe="1d", ts=ts,
                abertura=p.get("abertura"), maxima=p.get("maxima"), minima=p.get("minima"),
                fechamento=p.get("fechamento"), volume=p.get("volume"), fonte="yfinance",
            )
        )
    return velas


def _normalizar_mercados(pontos: Any) -> list[Vela]:
    velas = []
    for p in pontos or []:
        if not isinstance(p, dict):
            continue
        ts = _ts_para_iso(p.get("data") or p.get("ts") or p.get("date"))
        fech = p.get("fechamento") or p.get("close") or p.get("preco")
        if not ts or fech is None:
            continue
        velas.append(
            Vela(
                ativo="", classe="b3", timeframe="1d", ts=ts,
                abertura=p.get("abertura") or p.get("open"), maxima=p.get("maxima") or p.get("high"),
                minima=p.get("minima") or p.get("low"), fechamento=fech,
                volume=p.get("volume"), fonte="mercados",
            )
        )
    return velas


class ServicoB3(Servico):
    def __init__(self) -> None:
        super().__init__(MODULO, intervalo=int(CFG.get("intervalo_coleta", 300)))
        self._ultima_macro = 0.0

    def ciclo(self) -> None:
        ativos = list(CFG.get("ativos", [])) + list(CFG.get("indices", []))
        periodo = CFG.get("periodo_historico", "6mo")
        intervalo = CFG.get("intervalo_vela", "1d")
        disponiveis = 0

        for ativo_cfg in ativos:
            simbolo = ativo_cfg["simbolo"]
            velas, fonte, preco, variacao = _velas_da_cascata(ativo_cfg, periodo, intervalo)
            if not velas:
                self.log.warning("sem dados para %s (fontes indisponíveis)", simbolo)
                continue
            for v in velas:
                v.ativo = simbolo
            repo.inserir_velas(velas)
            repo.inserir_cotacao(
                Cotacao(
                    ativo=simbolo, classe="b3", preco=preco, fonte=fonte,
                    abertura=velas[-1].abertura, maxima=velas[-1].maxima,
                    minima=velas[-1].minima, volume=velas[-1].volume,
                    variacao_pct=variacao,
                    extra={"nome": ativo_cfg.get("nome", ""), "velas": len(velas)},
                )
            )
            disponiveis += 1
            self.log.info("%s: %s velas via %s (último=%s)", simbolo, len(velas), fonte, preco)

        # Macro (a cada hora, no máximo)
        if time.monotonic() - self._ultima_macro > int(CFG.get("macro_intervalo", 3600)):
            self._ultima_macro = time.monotonic()
            try:
                n = CB_BCB.chamar(bcb_client.registrar_no_banco, CFG.get("macro_series"))
                self.log.info("macro: %s séries atualizadas", n or 0)
            except Exception as exc:  # noqa: BLE001
                self.log.warning("macro falhou: %s", exc)

        if disponiveis == 0:
            self.heartbeat("degradado", "nenhuma fonte B3 disponível")
        else:
            self.log.info("ciclo concluído: %s ativos atualizados", disponiveis)


if __name__ == "__main__":
    ServicoB3().executar(executar_uma_vez=modo_uma_vez())
