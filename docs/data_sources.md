# Fontes de Dados — status real (documento vivo)

> Atualizar sempre que uma fonte mudar de comportamento (PRD secao 13).
> Última validação: execução de smoke test em ambiente Windows 11 / Python 3.11.

Este documento registra o resultado da Fase 0 (validação de fontes), quais
fontes funcionaram, com qual latência real, e quais símbolos dependem de
configuração manual (ex.: MT5).

## Resumo por domínio

| Domínio | Fonte | Status | Latência observada | Observação |
|---|---|---|---|---|
| B3 ações | `brapi.dev` | ✅ funciona parcialmente | ~1 s/ticker | Sem token, o limite anônimo é atingido rapidamente (HTTP 401 após alguns tickers). Configure `BRAPI_TOKEN`. |
| B3 ações (fallback) | `yfinance` | ✅ funciona | ~1–2 s/ticker | Assumiu os tickers que a brapi recusou; estável. |
| B3 índices | `yfinance` (`^BVSP`) | ✅ funciona | ~1 s | brapi recusou `^BVSP` sem token. |
| Macro BR | `bcb` SGS | ✅ funciona | <1 s/serie | Endpoint correto: `/dados/ultimos/{n}?formato=json` com header `Accept: application/json`. Séries: 432, 11, 4389, 433, 1. |
| Biblioteca `mercados` | `mercados` | ⚪ não instalada | — | Adaptador opcional; cascata segue para brapi/yfinance. Instalar apenas se validado. |
| Forex | MetaTrader 5 | ⚠ depende do terminal | — | Pacote `MetaTrader5` instala, mas `initialize()` exige o terminal MT5 x64 instalado (`-10003 IPC initialize failed`). |
| Forex (contingência) | feed `simulado` | ✅ funciona | instantâneo | Ativado por `forex/config.json` (`permitir_simulado`). Fonte gravada como `simulado` e nunca confundida com dado real. |
| Cripto | `ccxt` (binance) | ✅ funciona | ~10 s por par (300 velas) | OHLCV 1h + orderbook. Fallbacks configurados: kraken, coinbase, okx, bybit. |
| Notícias | RSS | ✅ funciona | ~2 s | InfoMoney, Investing, Yahoo, CoinDesk retornam itens. Reuters Business retorna vazio (feed descontinuado). |
| Notícias (fallback) | scraping InfoMoney | ✅ implementado | ~2 s | Seletores em `noticias/config.json` (`padrao_link`). Usar apenas se RSS falhar. |
| DXY / índices futuros americanos | MT5 (`USDX`, `US500`, `USTEC`, `DE40`) | ⚠ não confirmado | — | Validar quais símbolos a corretora expõe. Sem MT5, a pré-abertura usa o feed simulado ou fica sem entradas (`faltantes` visíveis na dashboard). |

## Latência e confiabilidade por módulo

- **Ciclo B3** (`intervalo_coleta=300s`): 8 ativos + 5 séries macro em ~25 s.
- **Ciclo cripto** (`intervalo_coleta=120s`): 3 pares em ~30 s (binance, rate limit respeitado).
- **Ciclo forex** (`intervalo_coleta=60s`): instantâneo em modo simulado.
- **Ciclo notícias** (`intervalo_coleta=300s`): ~2 s; 50 manchetes na primeira execução.
- **Ciclo sinais** (`intervalo_sinais=120s`): <1 s para 21 ativos monitorados.

## Circuit breakers

- `b3.brapi` / `b3.yfinance`: 3 falhas → 300 s aberto.
- `b3.bcb`: 3 falhas → 600 s aberto.
- `cripto.<exchange>`: 2 falhas → 180 s aberto.

## Fontes que exigem validação manual do usuário

1. **Símbolos MT5** para DXY/índices americanos — depende da corretora. Ajustar
   `forex/config.json` → `referencias_pre_abertura` após checar no terminal.
2. **Token brapi** — sem ele, parte dos tickers recai em yfinance (ok, mas com
   latência um pouco maior e sem garantia de cobertura em tempo quase real).
3. **Token/Chat ID do Telegram** — sem configuração, alertas ficam na fila
   (`fila_alertas`), visíveis na dashboard, e nada mais é afetado.
