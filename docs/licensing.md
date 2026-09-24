# Licenciamento e conformidade (Fase 1)

O sistema usa **apenas fontes gratuitas**. Antes de uso contínuo, revisar os
termos de cada provedor. Este resumo não substitui os termos oficiais.

| Componente | Licença/uso | Observação |
|---|---|---|
| Python 3 | PSF License | Livre. |
| FastAPI, Uvicorn, Starlette, Pydantic | MIT / BSD | Livre. |
| yfinance | Apache-2.0 | Projeto não-oficial do Yahoo Finance; dados "como estão", sem garantia. Uso pessoal. |
| requests | Apache-2.0 | Livre. |
| ccxt | MIT | Apenas endpoints públicos; respeitar rate limits da exchange. |
| feedparser | BSD-2-Clause | Livre. |
| psutil | BSD-3-Clause | Livre. |
| psutil / MetaTrader5 | Licença do pacote oficial | O pacote `MetaTrader5` é fornecido pela MetaQuotes; requer terminal instalado e conta na corretora. |
| brapi.dev | API pública | Plano gratuito com token; respeitar limites de uso. |
| BCB SGS | Dados abertos do governo | Uso livre com atribuição à fonte. |
| RSS de terceiros | Termos do site | Uso pessoal de feeds públicos. |
| Scraping (fallback) | Termos do site | Usar somente como contingência; verificar `robots.txt` e termos de uso. |

## Boas práticas

- Dados pagos/APIs com custo recorrente estão fora do escopo da Fase 1.
- Nenhuma fonte é raspada em alta frequência; os intervalos de coleta são
  conservadores (≥60 s) para respeitar limites e o hardware modesto.
- Todas as credenciais ficam em `.env` (fora do controle de versão).
