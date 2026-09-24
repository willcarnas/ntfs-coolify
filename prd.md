# PRD — Sistema de Suporte a Decisão para Trading (Opções B3, Forex e Cripto)

> Autor: Willians
> Status: Draft — v1.1
> Ambiente alvo: Mini PC doméstico, Windows 11, 24/7
> Uso previsto: Base para implementação assistida por IA (OpenCode + VS Code)

---

## 1. Resumo Executivo

Sistema pessoal de suporte à decisão para operações com opções na B3, além de forex e criptomoedas (mercados 24h). O sistema coleta dados de mercado de fontes majoritariamente gratuitas, calcula indicadores técnicos e de fluxo, estima um preço justo de abertura para dólar e índices brasileiros com base em referências internacionais (DXY, futuros de índice americano), monitora o humor do mercado via notícias, envia alertas de oportunidade via Telegram e disponibiliza tudo em uma dashboard web local. As operações continuam sendo executadas manualmente pelo usuário; o sistema apenas monitora e registra as entradas/saídas para análise futura. Automação de execução é um objetivo de fase posterior, condicionado à validação da assertividade do sistema.

O sistema roda continuamente em um mini PC doméstico com hardware modesto (Intel Celeron J4125, 4 GB RAM, Windows 11), o que exige arquitetura leve, modular e resiliente a falhas parciais.

### Objetivo de negócio
Aumentar a qualidade das decisões de compra/venda de opções e de posições em forex/cripto, reduzindo viés emocional, por meio de indicadores objetivos, alertas automáticos e uma visão consolidada em dashboard — sem depender de assinaturas pagas de dados na fase inicial.

### Meta de MVP
Coletar dados de pelo menos um ativo de cada classe (B3, forex via MT5, cripto), calcular indicadores básicos, gerar alerta no Telegram, exibir tudo em uma dashboard web acessível na rede local, e registrar manualmente as operações realizadas — tudo rodando de forma estável por 7 dias contínuos no hardware atual.

---

## 2. Missão e Princípios

**Missão:** dar ao usuário uma visão técnica consolidada do mercado (B3, forex, cripto) antes de cada decisão de compra/venda, sem depender de dados pagos, com histórico registrado para aprendizado futuro (incluindo eventual uso de IA), acessível tanto via alertas no Telegram quanto por uma dashboard web.

**Princípios de projeto:**
1. **Gratuito primeiro** — nenhuma dependência obrigatória de API paga na fase atual.
2. **Isolamento de falhas** — a queda de um módulo (ex.: cripto) não pode afetar os demais (ex.: forex, B3, alertas, dashboard).
3. **Transparência da fonte** — todo dado exibido informa de onde veio e há quanto tempo foi obtido.
4. **Humano no controle** — o sistema recomenda; o usuário decide e executa manualmente até que haja confiança suficiente para automação.
5. **Compatível com hardware modesto** — todo módulo, incluindo a dashboard, deve ser leve o bastante para rodar em um Celeron J4125 com 4 GB de RAM.

---

## 3. Usuários-Alvo

- **Usuário único (Willians)**: trader pessoal, opera opções na B3 e pretende operar forex/cripto fora do horário da bolsa brasileira. Usa análise técnica e de fluxo. Acessa o sistema via Telegram (alertas) e via navegador (dashboard), na rede doméstica.

---

## 4. Escopo

### 4.1 Dentro do escopo (Fase 1 — MVP)
- ✅ Coleta de cotações de ações/índices da B3 (fechamento diário e acompanhamento de sessão).
- ✅ Coleta de cotações forex via MetaTrader 5 (conta demo ou real).
- ✅ Coleta de cotações de cripto via biblioteca pública (ex.: `ccxt`).
- ✅ Cálculo de indicadores técnicos clássicos (médias móveis, RSI, MACD, bandas de Bollinger) por ativo.
- ✅ Estimativa de preço justo de abertura (dólar/índice BR) usando referências internacionais disponíveis (DXY/índices futuros americanos, quando a fonte permitir).
- ✅ Coleta de notícias de mercado (RSS quando disponível; scraping como fallback documentado).
- ✅ Motor de sinais gerando recomendações (compra/venda/observação) com justificativa.
- ✅ Motor de risco aplicando regras simples (ex.: não repetir alerta duplicado, limite diário de alertas).
- ✅ Envio de alertas via Telegram.
- ✅ **Dashboard web local** exibindo cotações, indicadores, sinais, notícias, saúde do sistema e histórico de operações.
- ✅ Registro manual de operações realizadas (entrada, saída, resultado) para acompanhamento.
- ✅ Armazenamento histórico de todos os dados coletados para análise futura.
- ✅ Execução como serviços Windows independentes (NSSM), com reinício automático.

### 4.2 Fora do escopo (Fase 1)
- ❌ Execução automática de ordens (compra/venda automatizada).
- ❌ Uso de dados pagos ou APIs com custo recorrente.
- ❌ Dashboard multiusuário ou exposta publicamente na internet (acesso restrito à rede local/VPN).
- ❌ Modelos de IA/ML treinados (previsto para fase futura, após validação do sistema baseado em regras).
- ❌ Suporte a múltiplas corretoras simultâneas no forex.

---

## 5. Arquitetura do Sistema

### 5.1 Visão geral

Cada domínio de mercado roda como **processo/serviço Windows independente**, comunicando-se apenas via banco de dados/fila compartilhada — nunca por chamada direta de função entre módulos de domínios diferentes. A dashboard é um consumidor **somente leitura** desses dados, e não um módulo que processa ou decide nada.
┌─────────────┐ ┌──────────────┐ ┌─────────────┐ ┌───────────────┐ │ módulo B3 │ │ módulo forex │ │ módulo cripto│ │ módulo notícias│ │ (serviço) │ │ (serviço) │ │ (serviço) │ │ (serviço) │ └──────┬──────┘ └──────┬───────┘ └──────┬──────┘ └──────┬────────┘ │ │ │ │ └────────────┬────┴─────────┬────────┴────────┬────────┘ ▼ ▼ ▼ banco de dados local (SQLite/Postgres) + fila de eventos │ ▼ ┌──────────────────────┐ ┌───────────────────┐ │ motor de sinais │──────▶│ motor de risco │ └──────────────────────┘ └───────────────────┘ │ ┌──────────┴───────────┐ ▼ ▼ serviço de Telegram dashboard web local (processo próprio) (processo próprio, somente leitura)

### 5.2 Regras de isolamento

- Cada módulo roda como **serviço Windows separado** (via NSSM), com log próprio e reinício automático em falha.
- Comunicação exclusivamente por contrato de dados (tabela no banco, arquivo, fila) — nunca importação de código de outro módulo em tempo de execução.
- Timeout agressivo em toda chamada externa (rede, API, terminal MT5); circuit breaker por fonte de dados que falha repetidamente.
- Motor de sinais e motor de risco são serviços separados; um não pode travar esperando o outro.
- Telegram e dashboard são apenas consumidores de dados já processados — se caírem, a coleta continua intacta; se a coleta cair, a dashboard deve mostrar dado desatualizado com aviso, não travar ou quebrar.

### 5.3 Critério de aceitação da arquitetura
Ao encerrar manualmente o processo de qualquer módulo (ex.: cripto), os demais módulos — incluindo a dashboard — devem continuar operando normalmente, exibindo o último dado válido conhecido com indicação de que está desatualizado.

---

## 6. Fontes de Dados (somente gratuitas)

| Domínio | Fonte primária | Fallback | Observação |
|---|---|---|---|
| Ações/índices BR (histórico, macro) | `mercados` (dados oficiais B3/CVM/BCB) | `brapi` → `yfinance` | `mercados` não cobre tempo real por design |
| Ações BR (acompanhamento de sessão) | `brapi` | `yfinance` | Latência variável, validar na prática |
| Macro BR (Selic, CDI, IPCA) | `mercados` (BCB SGS) | — | Fonte oficial |
| Forex | MetaTrader 5 (conta demo/real da corretora) | — | Nativo no Windows; validar símbolos disponíveis |
| DXY / índices futuros americanos | Símbolos MT5 da corretora (ex.: USDX, índices como CFD) | `yfinance` (hipótese, validar) | **Não confirmado** — validar manualmente quais símbolos a corretora expõe |
| Cripto | `ccxt` (endpoints públicos de exchange) | Exchange alternativa via `ccxt` | Sem custo, múltiplas exchanges sob uma API |
| Notícias de mercado | RSS oficial (se existir) | Scraping InfoMoney/Investing (não confirmado, verificar termos de uso) | Sem API pública gratuita confirmada |

### 6.1 Cascata de fallback (pseudo-lógica)
Ação BR (histórico/macro): mercados → indisponível Ação BR (sessão em curso): brapi → yfinance → indisponível Forex: MT5 (corretora A) → indisponível DXY/índice americano: MT5 (símbolo da corretora) → yfinance (hipótese) → indisponível Cripto: ccxt (exchange A) → ccxt (exchange B) → indisponível Notícia: RSS oficial → scraping → indisponível

Toda leitura de dado deve ser carimbada com fonte + timestamp; a ausência de uma fonte deve reduzir a confiança do sinal gerado, nunca ser preenchida silenciosamente — e essa informação deve aparecer visualmente na dashboard.

---

## 7. Requisitos Funcionais

### RF-01 — Coleta de dados B3
Coletar cotações diárias e, quando possível, intradiárias de ações e índices via `mercados`/`brapi`/`yfinance`, armazenando histórico local com fonte e timestamp.
**Critério de aceite:** rodar por 5 dias úteis seguidos sem interrupção manual, com dado do fechamento de cada pregão salvo corretamente.

### RF-02 — Coleta de dados Forex (MT5)
Conectar ao terminal MetaTrader 5 via pacote Python oficial, coletar cotações dos pares configurados continuamente (polling configurável, ex.: a cada 1–5 min).
**Critério de aceite:** conexão estável por 24h contínuas sem exigir reinício manual do terminal.

### RF-03 — Coleta de dados Cripto
Coletar cotações e indicadores de fluxo básico (livro de ofertas, negócios recentes) via `ccxt` de ao menos uma exchange, 24/7.
**Critério de aceite:** dado atualizado a cada ciclo de polling configurado, com log de falhas de conexão sem derrubar o serviço.

### RF-04 — Cálculo de indicadores técnicos
Calcular indicadores clássicos (médias móveis, RSI, MACD, Bandas de Bollinger, volume relativo) para cada ativo monitorado, atualizados a cada novo dado coletado.
**Critério de aceite:** indicadores recalculados corretamente após cada ciclo de coleta, validados manualmente contra uma plataforma de referência para pelo menos 3 ativos.

### RF-05 — Análise de fluxo (nível básico)
Usar dados de negociações/livro de ofertas disponíveis (B3 via `mercados` D+0/D+1; cripto via `ccxt` em tempo real) para estimar pressão compradora/vendedora.
**Critério de aceite:** gerar métrica de fluxo (ex.: desequilíbrio comprador/vendedor) por ativo, atualizada a cada ciclo.

### RF-06 — Estimativa de preço justo de pré-abertura
Estimar valor de abertura esperado para dólar e principais índices BR, usando como entrada DXY e futuros de índice americano (quando disponíveis via MT5), ADRs (se aplicável) e câmbio internacional.
**Critério de aceite:** ao faltar uma das entradas (ex.: DXY indisponível), o sistema deve sinalizar redução de confiança na estimativa, nunca preencher silenciosamente com dado desatualizado.

### RF-07 — Coleta de notícias e humor de mercado
Coletar manchetes de fontes configuradas (RSS prioritário; scraping como fallback documentado), com classificação simples de sentimento (positivo/negativo/neutro) por palavra-chave ou modelo leve.
**Critério de aceite:** notícias novas aparecem no painel/alerta em até X minutos da publicação (definir X conforme fonte disponível).

### RF-08 — Motor de sinais
Combinar indicadores técnicos, fluxo, notícias e (quando disponível) a estimativa de pré-abertura para gerar recomendação de compra/venda/observação por ativo, com justificativa textual dos fatores considerados.
**Critério de aceite:** cada sinal gerado deve listar quais indicadores e fontes contribuíram para a recomendação.

### RF-09 — Motor de risco
Aplicar regras de controle antes de qualquer alerta ser enviado (ex.: evitar alertas duplicados em curto intervalo, limite diário de alertas por ativo, exigir confiança mínima quando faltarem fontes).
**Critério de aceite:** motor de risco continua funcionando mesmo se o motor de sinais estiver degradado (ex.: bloqueando envio por falta de dado), sem travar o processo geral.

### RF-10 — Alertas via Telegram
Enviar mensagem ao Telegram para cada sinal aprovado pelo motor de risco, incluindo ativo, tipo de sinal, indicadores-chave e fonte dos dados.
**Critério de aceite:** mensagem chega em até 1 minuto após aprovação do sinal, com bot funcionando de forma independente dos demais módulos.

### RF-11 — Dashboard web
Disponibilizar uma dashboard web local (acessível pelo navegador na rede doméstica) exibindo: cotações e indicadores atuais por ativo/classe (B3, forex, cripto); sinais gerados pelo motor de sinais, com justificativa; feed de notícias coletadas e classificação de sentimento; estimativa de pré-abertura (dólar/índices) com indicação de confiança; status de saúde do sistema (RAM, CPU, disco, conectividade, status de cada serviço/módulo); histórico de operações registradas manualmente, com resultado acumulado.

A dashboard deve indicar visivelmente, para cada bloco de dado, a fonte e o timestamp da última atualização, e sinalizar quando um módulo está fora do ar (dado desatualizado) sem quebrar a interface.

**Critério de aceite:** dashboard acessível via navegador na rede local, atualizando os dados automaticamente (ex.: a cada 30–60s ou via atualização manual), permanecendo utilizável mesmo quando um dos módulos de coleta está indisponível.

### RF-12 — Registro manual de operações
Permitir registrar manualmente (via comando no Telegram ou pela própria dashboard) entrada e saída de uma operação, vinculando ao sinal que a originou, quando aplicável.
**Critério de aceite:** histórico de operações manuais consultável na dashboard, com cálculo de resultado (lucro/prejuízo) por operação registrada.

### RF-13 — Armazenamento histórico
Persistir todos os dados coletados (cotações, indicadores, sinais, notícias, operações) em banco local, com rotina de backup periódico.
**Critério de aceite:** backup automatizado executado e verificável (arquivo gerado) pelo menos uma vez por dia.

### RF-14 — Monitoramento de saúde do sistema
Monitorar uso de CPU, RAM, disco e conectividade de internet do próprio mini PC, alertando via Telegram e exibindo na dashboard quando sair de faixas aceitáveis.
**Critério de aceite:** alerta de saúde disparado em teste manual (ex.: simular disco cheio ou perda de rede), visível tanto no Telegram quanto na dashboard.

---

## 8. Requisitos Não-Funcionais

- **Hardware-alvo:** Intel Celeron J4125, 4 GB RAM, Windows 11, SSD (recomenda-se upgrade de RAM assim que possível — 4 GB é abaixo do recomendado até para o MT5 sozinho, e a dashboard soma consumo adicional).
- **Disponibilidade:** módulos de forex e cripto devem operar 24/7; módulo B3 segue horário de pregão; dashboard deve estar disponível sempre que o mini PC estiver ligado.
- **Resiliência a reinício:** após queda de energia ou reinício do Windows, todos os serviços devem subir automaticamente, na ordem: dados → sinais → risco → alertas → dashboard.
- **Resiliência a falha parcial:** falha de um módulo não pode impedir o funcionamento dos demais, incluindo a dashboard (ver Seção 5).
- **Custo:** nenhuma dependência obrigatória de API paga na Fase 1.
- **Segurança:** credenciais de corretora/Telegram armazenadas fora do código-fonte; dashboard acessível apenas na rede local (sem exposição direta à internet na Fase 1).
- **Observabilidade:** todo módulo deve gerar log próprio com timestamp e nível de severidade.
- **Leveza da dashboard:** priorizar framework web leve (ex.: FastAPI/Flask + frontend simples) em vez de soluções que mantenham muito estado em memória, dado o limite de 4 GB de RAM.
- **Uso de memória:** cada serviço, incluindo a dashboard, deve ser leve o suficiente para coexistir com os demais dentro do limite de RAM disponível; validar consumo real antes de ativar todos os módulos simultaneamente.

---

## 9. Infraestrutura e Ambiente de Execução

### 9.1 Hardware atual
Mini PC com Intel Celeron J4125 (quad-core), 4 GB RAM, Windows 11.

**Ressalva conhecida:** 4 GB está abaixo da recomendação mínima confortável até para o MT5 isoladamente; adicionar uma dashboard web soma mais consumo. A estratégia de implementação deve prever ativação gradual de módulos (ver Seção 12 — Fases), com a dashboard entrando por último na sequência de testes, e monitoramento constante de RAM. Upgrade de memória segue como o próximo investimento de maior impacto no projeto.

### 9.2 Preparação do Windows
- Desativar aplicativos de inicialização automática desnecessários.
- Desativar efeitos visuais (ajustar para melhor desempenho).
- Ajustar arquivo de paginação para compensar RAM limitada.
- Aplicar todas as atualizações do Windows antes de iniciar a instalação dos módulos.
- Instalar no-break (UPS) para evitar corrupção de dados em quedas de energia.

### 9.3 Instalação de dependências
- Python 64 bits, com `venv` isolado por módulo.
- Terminal MetaTrader 5 instalado nativamente (instalação silenciosa via `/auto` opcional).
- Pacote `MetaTrader5` via pip, validando compatibilidade 64 bits.
- Biblioteca `mercados` para dados oficiais B3/CVM/BCB.
- Biblioteca `ccxt` para dados de cripto.
- Framework web leve (FastAPI ou Flask) para a dashboard, com `venv` próprio.
- NSSM para registrar cada módulo, incluindo a dashboard, como serviço Windows.

### 9.4 Gerenciamento de serviços
Cada módulo, incluindo a dashboard, registrado como serviço Windows independente via NSSM, com início automático e reinício em caso de falha:
nssm install ModuloB3 "C:\projeto\b3\venv\Scripts\python.exe" "C:\projeto\b3\main.py" nssm install ModuloForex "C:\projeto\forex\venv\Scripts\python.exe" "C:\projeto\forex\main.py" nssm install ModuloCripto "C:\projeto\cripto\venv\Scripts\python.exe" "C:\projeto\cripto\main.py" nssm install ModuloNoticias "C:\projeto\noticias\venv\Scripts\python.exe" "C:\projeto\noticias\main.py" nssm install MotorSinais "C:\projeto\sinais\venv\Scripts\python.exe" "C:\projeto\sinais\main.py" nssm install MotorRisco "C:\projeto\risco\venv\Scripts\python.exe" "C:\projeto\risco\main.py" nssm install ServicoTelegram "C:\projeto\telegram\venv\Scripts\python.exe" "C:\projeto\telegram\main.py" nssm install DashboardWeb "C:\projeto\dashboard\venv\Scripts\python.exe" "C:\projeto\dashboard\main.py"

Cada serviço configurado com `Start=SERVICE_AUTO_START` e política de reinício automático em falha.

---

## 10. Stack Tecnológica (proposta)

- **Linguagem:** Python 3.x (64 bits) em todos os módulos.
- **Banco de dados:** SQLite na fase inicial (simplicidade, zero configuração); migração para PostgreSQL local avaliada se o volume de dados justificar.
- **Coleta B3:** `mercados`, `brapi`, `yfinance` (cascata de fallback).
- **Coleta Forex:** `MetaTrader5` (pacote oficial) + terminal MT5 instalado localmente.
- **Coleta Cripto:** `ccxt`.
- **Indicadores técnicos:** biblioteca de indicadores em Python (ex.: `pandas-ta` ou implementação própria leve).
- **Notícias:** `feedparser` para RSS; scraping pontual documentado como fallback.
- **Motor de sinais/risco:** lógica em Python puro baseada em regras (sem ML na Fase 1).
- **Telegram:** biblioteca cliente de bot do Telegram em Python.
- **Dashboard web:** FastAPI ou Flask (backend leve) + frontend simples (HTML/JS ou template server-side), priorizando baixo consumo de memória.
- **Gerenciamento de serviços:** NSSM.
- **Backup:** script agendado (Agendador de Tarefas do Windows) copiando o banco para pasta/disco secundário.

---

## 11. Riscos e Itens em Aberto

| Risco | Impacto | Mitigação |
|---|---|---|
| 4 GB de RAM insuficiente para todos os módulos simultâneos | Alto | Ativação gradual de módulos; priorizar upgrade de RAM |
| DXY/índices americanos sem fonte gratuita confirmada | Médio | Validar símbolos MT5 da corretora antes de depender disso no RF-06 |
| Scraping de notícias sujeito a mudança de layout/termos de uso | Médio | Priorizar RSS; isolar scraping em módulo próprio, versionado |
| `mercados` não cobrir tempo real | Baixo/Médio | Usar `brapi`/`yfinance` como complemento para sessão em curso |
| Rede doméstica como ponto único de falha | Médio | Considerar conexão alternativa (dados móveis) como contingência |
| Dashboard consumir RAM excessiva | Médio | Escolher framework leve; testar consumo isoladamente antes de integrar aos demais módulos |

---

## 12. Fases de Implementação

**Fase 0 — Validação de fontes e hardware**
Testar cada fonte de dado (RF-01 a RF-03) isoladamente; medir consumo de RAM de cada componente separadamente, incluindo o terminal MT5 e a dashboard.

**Fase 1 — MVP funcional**
Implementar coleta de um ativo por classe, indicadores básicos (RF-04), motor de sinais simples (RF-08), motor de risco básico (RF-09), alertas via Telegram (RF-10) e dashboard mínima somente leitura (RF-11), rodando 7 dias contínuos.

**Fase 2 — Expansão de cobertura**
Adicionar mais ativos, análise de fluxo (RF-05), estimativa de pré-abertura (RF-06), notícias (RF-07), registro manual de operações (RF-12) e monitoramento de saúde (RF-14).

**Fase 3 — Maturação**
Ajustar regras do motor de sinais/risco com base no histórico acumulado; avaliar upgrade de hardware; preparar terreno para eventual módulo de IA/ML.

**Fase 4 (futura, fora deste PRD)**
Avaliação de automação parcial de execução, condicionada a métricas de assertividade comprovadas na Fase 3.

---

## 13. Notas de Implementação para IA (OpenCode/VS Code)

- Implementar cada módulo listado na Seção 5 como pacote Python independente, em pasta própria, com seu próprio `venv` e `requirements.txt`.
- Nunca importar código de um módulo de domínio (B3, forex, cripto, notícias) dentro de outro — toda troca de informação passa pelo banco de dados ou fila definidos na Seção 5.
- Implementar a cascata de fallback da Seção 6.1 como função explícita e testável por domínio, retornando sempre `(valor, fonte, timestamp)`, nunca apenas o valor.
- A dashboard (RF-11) deve ler exclusivamente do banco de dados compartilhado — nunca chamar diretamente as APIs externas dos outros módulos.
- Cada serviço deve expor um log estruturado (nível, timestamp, módulo, mensagem) para facilitar diagnóstico em caso de falha parcial.
- Priorizar implementações simples e testáveis nesta fase (sem ML), já que o motor de sinais/risco da Fase 1 é baseado em regras explícitas.
- Escrever testes unitários para as regras do motor de sinais e do motor de risco antes de integrá-las ao restante do sistema, já que são o núcleo de decisão do produto e qualquer erro silencioso ali se propaga para o Telegram e a dashboard.
- Validar cada conector de dado (RF-01 a RF-03) isoladamente, com um script de teste manual simples, antes de conectá-lo ao motor de sinais — isso evita depurar dois problemas ao mesmo tempo (fonte de dado ruim + lógica de sinal ruim).
- Ao implementar o circuit breaker por fonte de dados (Seção 5.2), tratar isso como um componente reutilizável e compartilhado entre módulos (biblioteca comum), não como código duplicado em cada conector.
- Nomear claramente no banco de dados a origem de cada registro (coluna `fonte`, coluna `timestamp_coleta`), desde a primeira versão do schema — adicionar isso depois, com dados já acumulados, é mais trabalhoso do que prever desde o início.
- Ao implementar o RF-06 (pré-abertura), estruturar o cálculo de forma que cada entrada (DXY, futuro de índice, câmbio) seja opcional e clara sobre seu peso na estimativa final, para que a ausência de uma fonte apenas reduza a confiança, sem quebrar o cálculo.
- Registrar em `docs/data_sources.md` o resultado da validação da Fase 0 (quais fontes funcionaram, com qual latência real, e quais símbolos MT5 a corretora escolhida realmente expõe para DXY/índices americanos), para que decisões tomadas na prática fiquem documentadas e não se percam.

---

## 14. Estrutura de Pastas Sugerida
projeto-trading/ ├── b3/ │ ├── venv/ │ ├── main.py │ ├── coletores/ │ │ ├── mercados_client.py │ │ ├── brapi_client.py │ │ └── yfinance_client.py │ └── requirements.txt ├── forex/ │ ├── venv/ │ ├── main.py │ ├── mt5_client.py │ ├── config.json │ └── requirements.txt ├── cripto/ │ ├── venv/ │ ├── main.py │ ├── ccxt_client.py │ └── requirements.txt ├── noticias/ │ ├── venv/ │ ├── main.py │ ├── rss_client.py │ ├── scraping_client.py │ └── requirements.txt ├── sinais/ │ ├── venv/ │ ├── main.py │ ├── indicadores.py │ ├── regras_sinais.py │ └── requirements.txt ├── risco/ │ ├── venv/ │ ├── main.py │ ├── regras_risco.py │ └── requirements.txt ├── telegram/ │ ├── venv/ │ ├── main.py │ └── requirements.txt ├── dashboard/ │ ├── venv/ │ ├── main.py │ ├── static/ │ ├── templates/ │ └── requirements.txt ├── comum/ │ ├── db_schema.sql │ ├── circuit_breaker.py │ ├── logger.py │ └── contratos_dados.py ├── docs/ │ ├── data_sources.md │ ├── licensing.md │ └── PRD.md └── scripts/ ├── backup_diario.py └── monitor_saude.py

Essa separação por pasta reforça na prática o princípio de isolamento defin```markdown
- Cada regra do motor de sinais e do motor de risco deve ser uma função pura e isolada (entrada → saída determinística), facilitando testes unitários e futura substituição por modelo de IA sem reescrever o restante do pipeline.
- Ao implementar o conector MT5, isolar toda a lógica de conexão/reconexão em uma camada própria (ex.: `mt5_client.py`), com retry e timeout configuráveis, para que instabilidades do terminal não propaguem exceções não tratadas para o restante do módulo forex.
- Documentar no repositório, em `docs/data_sources.md`, o status real de cada fonte testada (funcionando, com fallback, indisponível), atualizando esse arquivo sempre que uma fonte mudar de comportamento — esse documento deve ser tratado como vivo, não como entrega única.
- Ao implementar o scraping de notícias, isolar seletores HTML em um arquivo de configuração separado do código de coleta, para que mudanças de layout do site exijam apenas ajuste de configuração, não reescrita da lógica.
- Toda tabela do banco de dados deve incluir colunas de auditoria (`fonte`, `coletado_em`) além dos dados de negócio, para sustentar a exigência de transparência da fonte definida na Seção 2.
- Testes de isolamento (Seção 5.3) devem ser escritos como scripts reproduzíveis (ex.: `tests/test_isolamento_cripto.py`) que encerram o processo do módulo e verificam se os demais serviços continuam respondendo, não apenas validados manualmente uma vez.

---

## 14. Critérios de Aceite Gerais do Projeto (Definition of Done — Fase 1)

- Todos os serviços listados na Seção 9.4 sobem automaticamente após reinício do Windows, na ordem correta, sem intervenção manual.
- Encerrar manualmente qualquer serviço de domínio (B3, forex, cripto ou notícias) não interrompe os demais serviços nem a dashboard.
- A dashboard exibe corretamente o estado "dado desatualizado" quando um módulo está fora do ar, em vez de travar, quebrar ou exibir dado incorreto.
- Um sinal gerado pelo motor de sinais é rastreável até os dados brutos e fontes que o originaram, visível tanto no alerta do Telegram quanto na dashboard.
- O sistema roda de forma contínua por 7 dias no hardware atual (Celeron J4125, 4 GB RAM) sem necessidade de reinício manual por travamento ou vazamento de memória.
- Existe pelo menos um backup automatizado do banco de dados gerado nesse período de 7 dias.

---

## 15. Glossário

- **Preço justo de pré-abertura:** estimativa do valor de abertura de um ativo/índice antes do início do pregão, baseada em referências que já estão operando (ex.: DXY, futuros de índice americano).
- **Motor de sinais:** componente que combina indicadores e dados de contexto para gerar uma recomendação de compra/venda/observação.
- **Motor de risco:** componente que filtra e controla o que efetivamente vira alerta, aplicando regras de segurança (limite de frequência, confiança mínima, etc.).
- **Circuit breaker:** mecanismo que desativa temporariamente uma fonte de dados após falhas repetidas, evitando sobrecarga ou travamento por tentativas contínuas.
- **Isolamento de processo:** princípio arquitetural em que cada módulo roda separadamente, de forma que sua falha não afete os demais.

---

*Fim do documento. Este PRD deve ser tratado como referência viva: atualizar as seções 6 (fontes de dados) e 11 (riscos) sempre que uma fonte gratuita mudar de comportamento ou uma nova limitação de hardware for identificada na prática.*