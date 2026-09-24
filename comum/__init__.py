"""Biblioteca comum compartilhada pelos modulos do sistema de trading.

Conforme o PRD (secao 5.2 e 13), este pacote concentra apenas infraestrutura
reutilizavel (acesso a banco, logging, circuit breaker, contratos de dados,
indicadores puros). Nenhum modulo de dominio deve importar codigo de outro
modulo de dominio: a comunicacao ocorre exclusivamente via banco de dados.
"""

__all__ = [
    "config",
    "logger",
    "db",
    "repo",
    "contratos_dados",
    "circuit_breaker",
    "indicadores",
]
