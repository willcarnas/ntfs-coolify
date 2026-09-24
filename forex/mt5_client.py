"""Integração com MetaTrader 5 isolada em uma camada própria (secao 13).

Toda conexão/reconexão, retry e timeout ficam aqui; instabilidades do terminal
não propagam exceções para o restante do módulo forex.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from comum.logger import get_logger

log = get_logger("forex.mt5")

try:
    import MetaTrader5 as mt5  # type: ignore

    DISPONIVEL = True
except Exception as exc:  # pragma: no cover - só existe no Windows com MT5
    mt5 = None
    DISPONIVEL = False
    log.info("MetaTrader5 indisponível (%s)", exc)


class ConectorMT5:
    """Wrapper resiliente em torno do pacote oficial MetaTrader5."""

    def __init__(self, terminal_path: Optional[str] = None, login: Optional[int] = None,
                 senha: Optional[str] = None, servidor: Optional[str] = None) -> None:
        self.terminal_path = terminal_path
        self.login = login
        self.senha = senha
        self.servidor = servidor
        self.conectado = False
        self._ultima_tentativa = 0.0

    @property
    def disponivel(self) -> bool:
        return DISPONIVEL

    def conectar(self, forcar: bool = False) -> bool:
        if not DISPONIVEL:
            return False
        if self.conectado and not forcar:
            return True
        # Evita tentar reconectar freneticamente.
        if not forcar and time.monotonic() - self._ultima_tentativa < 10:
            return self.conectado
        self._ultima_tentativa = time.monotonic()
        try:
            kwargs: dict[str, Any] = {}
            if self.terminal_path:
                kwargs["path"] = self.terminal_path
            if self.login:
                kwargs.update({"login": self.login, "password": self.senha, "server": self.servidor})
            ok = mt5.initialize(**kwargs) if kwargs else mt5.initialize()
            if not ok:
                erro = mt5.last_error()
                log.warning("MT5 initialize falhou: %s", erro)
                self.conectado = False
                return False
            self.conectado = True
            info = mt5.terminal_info()
            log.info("MT5 conectado (%s)", getattr(info, "name", "terminal"))
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("MT5 initialize lançou exceção: %s", exc)
            self.conectado = False
            return False

    def desconectar(self) -> None:
        if DISPONIVEL and self.conectado:
            try:
                mt5.shutdown()
            except Exception:  # noqa: BLE001
                pass
        self.conectado = False

    def simbolo_visivel(self, simbolo: str) -> bool:
        if not self.conectar():
            return False
        try:
            if mt5.symbol_info(simbolo) is None:
                return False
            return bool(mt5.symbol_select(simbolo, True))
        except Exception:  # noqa: BLE001
            return False

    def ticker(self, simbolo: str) -> Optional[dict[str, Any]]:
        if not self.conectar():
            return None
        try:
            t = mt5.symbol_info_tick(simbolo)
            info = mt5.symbol_info(simbolo)
            if t is None:
                return None
            preco = t.last or t.bid or t.ask
            variacao = None
            if info and info.session_open:
                pass
            return {
                "preco": preco,
                "bid": t.bid,
                "ask": t.ask,
                "maxima": getattr(info, "high", None),
                "minima": getattr(info, "low", None),
                "variacao_pct": variacao,
            }
        except Exception as exc:  # noqa: BLE001
            log.warning("MT5 ticker %s falhou: %s", simbolo, exc)
            self.conectado = False
            return None

    def velas(self, simbolo: str, timeframe: str = "1h", limite: int = 300) -> list[dict[str, Any]]:
        if not self.conectar():
            return []
        tf = _timeframe_para_mt5(timeframe)
        if tf is None:
            return []
        try:
            taxas = mt5.copy_rates_from_pos(simbolo, tf, 0, limite)
            if taxas is None or len(taxas) == 0:
                return []
            velas = []
            for r in taxas:
                ts = datetime.fromtimestamp(int(r["time"]), tz=timezone.utc)
                velas.append(
                    {
                        "ts": ts,
                        "abertura": float(r["open"]),
                        "maxima": float(r["high"]),
                        "minima": float(r["low"]),
                        "fechamento": float(r["close"]),
                        "volume": float(r["tick_volume"]),
                    }
                )
            return velas
        except Exception as exc:  # noqa: BLE001
            log.warning("MT5 velas %s falhou: %s", simbolo, exc)
            self.conectado = False
            return []


def _timeframe_para_mt5(timeframe: str):
    if not DISPONIVEL:
        return None
    mapa = {
        "1m": mt5.TIMEFRAME_M1,
        "5m": mt5.TIMEFRAME_M5,
        "15m": mt5.TIMEFRAME_M15,
        "30m": mt5.TIMEFRAME_M30,
        "1h": mt5.TIMEFRAME_H1,
        "4h": mt5.TIMEFRAME_H4,
        "1d": mt5.TIMEFRAME_D1,
    }
    return mapa.get(timeframe)
