"""Módulo de coleta cripto (RF-03 + fluxo básico RF-05).

Serviço independente, roda 24/7. Cascata entre exchanges via ccxt; grava velas,
cotação e métrica de desequilíbrio do livro de ofertas. Falha de uma exchange
não derruba o serviço (circuit breaker por exchange).
"""
from __future__ import annotations

import sys
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
import ccxt_client  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
CFG = config.load_json(CONFIG_PATH, {})
MODULO = "cripto"

_EXCHANGES = [CFG.get("exchange_primaria", "binance")] + list(CFG.get("exchanges_fallback", []))
_BREAKERS = {nome: CircuitBreaker(f"cripto.{nome}", max_falhas=2, cooldown_segundos=180) for nome in _EXCHANGES}


def _ts_iso(ms: Any) -> Optional[str]:
    try:
        return db.iso(datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc))
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _buscar(par: str, timeframe: str, limite: int) -> tuple[Optional[str], list[list]]:
    """Tenta cada exchange disponível até obter OHLCV."""
    for nome in _EXCHANGES:
        breaker = _BREAKERS.get(nome)
        if breaker is not None and not breaker.disponivel:
            continue
        try:
            dados = (breaker.chamar(ccxt_client.historico, nome, par, timeframe, limite)
                     if breaker else ccxt_client.historico(nome, par, timeframe, limite))
        except Exception:  # noqa: BLE001
            dados = None
        if dados:
            return nome, dados
    return None, []


class ServicoCripto(Servico):
    def __init__(self) -> None:
        super().__init__(MODULO, intervalo=int(CFG.get("intervalo_coleta", 120)))
        self._exchange_ativa: Optional[str] = None

    def ciclo(self) -> None:
        timeframe = CFG.get("timeframe", "1h")
        limite = int(CFG.get("limite_velas", 300))
        pares = CFG.get("pares", [])
        disponiveis = 0

        for par in pares:
            nome, dados = _buscar(par, timeframe, limite)
            if not dados:
                self.log.warning("sem dados para %s em nenhuma exchange", par)
                continue

            ativo = par.replace("/", "")
            velas = []
            for linha in dados:
                ts = _ts_iso(linha[0])
                if not ts:
                    continue
                velas.append(
                    Vela(
                        ativo=ativo, classe="cripto", timeframe=timeframe, ts=ts,
                        abertura=linha[1], maxima=linha[2], minima=linha[3],
                        fechamento=linha[4], volume=linha[5], fonte=f"ccxt:{nome}",
                    )
                )
            if not velas:
                continue
            repo.inserir_velas(velas)

            variacao = None
            if len(velas) >= 2 and velas[-2].fechamento:
                variacao = (velas[-1].fechamento - velas[-2].fechamento) / velas[-2].fechamento * 100.0

            repo.inserir_cotacao(
                Cotacao(
                    ativo=ativo, classe="cripto", preco=velas[-1].fechamento,
                    abertura=velas[-1].abertura, maxima=velas[-1].maxima,
                    minima=velas[-1].minima, volume=velas[-1].volume,
                    variacao_pct=variacao, fonte=f"ccxt:{nome}",
                    extra={"par": par, "exchange": nome},
                )
            )

            # Fluxo (RF-05)
            if CFG.get("coletar_fluxo", True):
                try:
                    ob = ccxt_client.orderbook(nome, par)
                    repo.salvar_indicadores(
                        ativo, "cripto", timeframe,
                        {"fluxo_desequilibrio": ob.get("desequilibrio")},
                        fonte=f"ccxt:{nome}",
                    )
                except Exception as exc:  # noqa: BLE001
                    self.log.warning("fluxo falhou para %s: %s", par, exc)

            self._exchange_ativa = nome
            disponiveis += 1
            self.log.info("%s: %s velas via %s (último=%s)", ativo, len(velas), nome, velas[-1].fechamento)

        if disponiveis == 0:
            self.heartbeat("degradado", "nenhuma exchange disponível")
        else:
            self.log.info("ciclo concluído: %s pares via %s", disponiveis, self._exchange_ativa)


if __name__ == "__main__":
    ServicoCripto().executar(executar_uma_vez=modo_uma_vez())
