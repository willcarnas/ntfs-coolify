"""Contratos de dados entre módulos (secao 13).

Cada leitura de dado externo é carimbada com `(valor, fonte, timestamp)`.
Estas dataclasses padronizam a troca via banco e nunca carregam apenas o valor.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from . import db

CLASSES_VALIDAS = ("b3", "forex", "cripto")
TIPOS_SINAL = ("compra", "venda", "observacao")
SENTIMENTOS = ("positivo", "negativo", "neutro")


@dataclass
class Leitura:
    """Resultado padronizado de uma coleta: valor + fonte + timestamp."""

    valor: Any
    fonte: str
    coletado_em: str
    sucesso: bool = True
    erro: Optional[str] = None
    desatualizado: bool = False

    @classmethod
    def falha(cls, fonte: str, erro: str) -> "Leitura":
        return cls(valor=None, fonte=fonte, coletado_em=db.iso(), sucesso=False, erro=erro)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Cotacao:
    ativo: str
    classe: str
    preco: Optional[float]
    fonte: str
    coletado_em: str = field(default_factory=db.iso)
    abertura: Optional[float] = None
    maxima: Optional[float] = None
    minima: Optional[float] = None
    volume: Optional[float] = None
    variacao_pct: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> tuple:
        return (
            self.ativo,
            self.classe,
            self.preco,
            self.abertura,
            self.maxima,
            self.minima,
            self.volume,
            self.variacao_pct,
            self.bid,
            self.ask,
            json.dumps(self.extra, ensure_ascii=False) if self.extra else None,
            self.fonte,
            self.coletado_em,
        )


@dataclass
class Vela:
    ativo: str
    classe: str
    timeframe: str
    ts: str
    abertura: Optional[float]
    maxima: Optional[float]
    minima: Optional[float]
    fechamento: Optional[float]
    volume: Optional[float]
    fonte: str
    coletado_em: str = field(default_factory=db.iso)


@dataclass
class FatorSinal:
    """Fator que contribuiu para um sinal (RF-08 - justificativa rastreável)."""

    nome: str
    valor: Any
    peso: float
    contribuicao: float
    descricao: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Sinal:
    ativo: str
    classe: str
    tipo: str
    confianca: float
    preco: Optional[float]
    justificativa: str
    fatores: list[FatorSinal] = field(default_factory=list)
    fontes: list[str] = field(default_factory=list)
    dados_desatualizados: bool = False
    criado_em: str = field(default_factory=db.iso)
    status: str = "pendente"
    id: Optional[int] = None

    def to_row(self) -> tuple:
        return (
            self.ativo,
            self.classe,
            self.tipo,
            round(float(self.confianca), 4),
            self.preco,
            self.justificativa,
            json.dumps([f.to_dict() for f in self.fatores], ensure_ascii=False),
            json.dumps(self.fontes, ensure_ascii=False),
            1 if self.dados_desatualizados else 0,
            self.status,
            self.criado_em,
        )


@dataclass
class Noticia:
    titulo: str
    fonte: str
    coletado_em: str = field(default_factory=db.iso)
    link: Optional[str] = None
    resumo: Optional[str] = None
    sentimento: str = "neutro"
    score: float = 0.0
    publicado_em: Optional[str] = None
    hash: Optional[str] = None

    def to_row(self) -> tuple:
        return (
            self.titulo,
            self.link,
            self.resumo,
            self.fonte,
            self.sentimento,
            self.score,
            self.publicado_em,
            self.coletado_em,
            self.hash,
        )


@dataclass
class EntradaPreAbertura:
    """Uma entrada opcional do cálculo de pré-abertura (RF-06)."""

    nome: str
    valor: Optional[float]
    fonte: str
    peso: float
    disponivel: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EstimativaPreAbertura:
    ativo: str
    valor_estimado: Optional[float]
    confianca: float
    entradas: list[EntradaPreAbertura] = field(default_factory=list)
    faltantes: list[str] = field(default_factory=list)
    fonte: str = "composicao"
    coletado_em: str = field(default_factory=db.iso)
