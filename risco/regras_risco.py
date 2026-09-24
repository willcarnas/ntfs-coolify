"""Regras puras do motor de risco (RF-09).

Funções determinísticas e testáveis: recebem os dados do sinal e um contexto
(contadores e timestamps já obtidos do banco) e decidem se o alerta pode ser
enviado. O motor de risco nunca deve travar quando o motor de sinais está
degradado — por isso toda entrada é tratada como possivelmente ausente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from comum import db

PADRAO = {
    "confianca_minima": 0.30,
    "confianca_minima_desatualizado": 0.60,
    "intervalo_minimo_segundos": 900,
    "max_alertas_dia_ativo": 5,
    "max_alertas_dia_total": 40,
    "bloquear_dados_desatualizados": True,
    "tipos_alertaveis": ("compra", "venda"),
}


@dataclass
class ResultadoRisco:
    aprovado: bool
    motivo: str = ""
    regras: list[dict[str, Any]] = field(default_factory=list)

    def registrar(self, nome: str, ok: bool, detalhe: str) -> None:
        self.regras.append({"regra": nome, "ok": ok, "detalhe": detalhe})


def _cfg(regras: Optional[dict[str, Any]], chave: str) -> Any:
    if regras and chave in regras:
        return regras[chave]
    return PADRAO[chave]


def avaliar_risco(sinal: dict[str, Any], contexto: dict[str, Any], regras: Optional[dict[str, Any]] = None) -> ResultadoRisco:
    resultado = ResultadoRisco(aprovado=True)
    tipos_ok = tuple(_cfg(regras, "tipos_alertaveis"))

    tipo = sinal.get("tipo")
    if tipo not in tipos_ok:
        resultado.registrar("tipo_alertavel", False, f"tipo '{tipo}' não gera alerta")
        return _reprovar(resultado, "tipo não alertável")

    confianca = float(sinal.get("confianca") or 0.0)
    desatualizado = bool(sinal.get("dados_desatualizados"))
    if desatualizado and _cfg(regras, "bloquear_dados_desatualizados"):
        resultado.registrar("dados_desatualizados", False, "dados desatualizados bloqueiam alerta")
        return _reprovar(resultado, "dados desatualizados")

    minimo = float(_cfg(regras, "confianca_minima_desatualizado" if desatualizado else "confianca_minima"))
    if confianca < minimo:
        resultado.registrar("confianca_minima", False, f"confiança {confianca:.2f} < mínimo {minimo:.2f}")
        return _reprovar(resultado, "confiança abaixo do mínimo")
    resultado.registrar("confianca_minima", True, f"confiança {confianca:.2f} >= {minimo:.2f}")

    # Anti-duplicidade por ativo+tipo
    agora = contexto.get("agora") or db.agora_utc()
    ultimo = db.parse_iso(contexto.get("ultimo_alerta_ativo_em"))
    intervalo = int(_cfg(regras, "intervalo_minimo_segundos"))
    if ultimo is not None:
        idade = (agora - ultimo).total_seconds()
        if idade < intervalo and contexto.get("ultimo_alerta_ativo_tipo") == tipo:
            resultado.registrar("anti_duplicidade", False, f"alerta semelhante há {int(idade)}s (<{intervalo}s)")
            return _reprovar(resultado, "alerta duplicado")
    resultado.registrar("anti_duplicidade", True, "sem duplicidade recente")

    n_ativo = int(contexto.get("alertas_enviados_hoje_ativo") or 0)
    max_ativo = int(_cfg(regras, "max_alertas_dia_ativo"))
    if n_ativo >= max_ativo:
        resultado.registrar("limite_diario_ativo", False, f"{n_ativo}/{max_ativo} alertas hoje")
        return _reprovar(resultado, "limite diário por ativo atingido")
    resultado.registrar("limite_diario_ativo", True, f"{n_ativo}/{max_ativo} alertas hoje")

    n_total = int(contexto.get("alertas_enviados_hoje_total") or 0)
    max_total = int(_cfg(regras, "max_alertas_dia_total"))
    if n_total >= max_total:
        resultado.registrar("limite_diario_total", False, f"{n_total}/{max_total} alertas hoje")
        return _reprovar(resultado, "limite diário global atingido")
    resultado.registrar("limite_diario_total", True, f"{n_total}/{max_total} alertas hoje")

    return resultado


def _reprovar(resultado: ResultadoRisco, motivo: str) -> ResultadoRisco:
    resultado.aprovado = False
    resultado.motivo = motivo
    return resultado


def resumo(resultado: ResultadoRisco) -> str:
    estado = "APROVADO" if resultado.aprovado else f"BLOQUEADO ({resultado.motivo})"
    linhas = [estado]
    for r in resultado.regras:
        linhas.append(f"• {r['regra']}: {'ok' if r['ok'] else 'falhou'} - {r['detalhe']}")
    return " | ".join(linhas)
