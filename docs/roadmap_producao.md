# Roadmap para producao em escala

Este documento e diferente dos demais em `docs/`: os outros descrevem o que o
sistema **ja faz** hoje. Aqui vao recomendacoes e pontos de atencao para
quando este projeto for de fato ligado em producao com volume real (o caso
citado como referencia: uma distribuidora recebendo por volta de mil OCs por
dia) - nada disso esta implementado ainda, e uma lista do que vale revisar
antes ou durante essa transicao.

## 1. Link para o documento original (SharePoint/OneDrive)

Hoje, em modo demo, a coluna "Documento" nunca vira link clicavel - e
proposital, nao um bug: os PDFs de demonstracao ficam apenas em
`demo_data/pdfs/`, nunca foram enviados a nenhum lugar na nuvem, entao nao ha
URL real para apontar. `URL_PASTA_ENTRADA_OC` no `.env.example` e so um
dominio de exemplo (`exemplo.sharepoint.com`), nao um endereco de verdade.

**Para producao**: configurar `PASTA_ENTRADA_OC` (caminho local/de rede real,
alimentado por uma regra do Outlook ou fluxo do Power Automate) e
`URL_PASTA_ENTRADA_OC` (a URL web da mesma pasta no OneDrive/SharePoint da
empresa) - so entao o link em `link_documento()` (`src/formatacao_painel.py`)
passa a apontar para um arquivo que existe de verdade, protegido pela
autenticacao Microsoft de quem acessar. Ver [arquitetura_webapp.md](arquitetura_webapp.md).

## 2. Reprocessamento de PDFs a cada execucao

Em modo demo, `pipeline.py` reprocessa TODOS os PDFs de `demo_data/pdfs/` a
cada execucao (sem nenhum controle de "ja processado") - por desenho, ja que
o modo demo existe para ser um conjunto fixo e repetivel de demonstracao, nao
uma fila real.

**Em modo producao isso ja esta resolvido**: todo PDF processado com sucesso
e movido para uma subpasta `processados/` (`folder_watcher.marcar_como_processado`),
e a proxima execucao so olha o que sobrou na pasta de entrada. O ponto de
atencao ao ir para producao nao e implementar isso (ja existe), e sim
**garantir que o ambiente real sempre rode em `MODO_EXECUCAO=producao`**, com
`PASTA_ENTRADA_OC` configurada - rodar em modo demo por engano num ambiente
de verdade reprocessaria tudo sem parar.

## 3. Volume e frequencia de execucao

Com mil OCs/dia, processar tudo de uma vez numa unica execucao arrisca
estourar o rate limit da OpenRouter. Recomendacoes:

- Rodar o pipeline em intervalos curtos (a cada 15-30 min, via Agendador de
  Tarefas do Windows ou cron), processando um lote pequeno de cada vez, em vez
  de uma execucao unica e gigante por dia.
- Calibrar `LIMITE_ARQUIVOS_POR_EXECUCAO` e `LIMITE_CONCORRENCIA` (`.env`)
  para o rate limit real do plano contratado na OpenRouter - comecar
  conservador (ex: concorrencia 5) e medir antes de aumentar.
- Acompanhar `output/logs/pipeline.log` e o alerta de falhas recentes
  (`LIMITE_ALERTA_FALHAS`) nas primeiras semanas de producao, para calibrar
  esses limites com dado real em vez de estimativa.

## 4. Custo recorrente da API

Diferente de uma aplicacao que roda uma vez e acabou, o custo por token da
OpenRouter cresce linearmente com o volume diario - com mil OCs/dia, isso
passa a ser uma linha de custo operacional recorrente, nao um detalhe tecnico.
Recomendado:

- Acompanhar o custo por chamada/modelo no painel da OpenRouter regularmente.
- Reavaliar o modelo configurado (`OPENROUTER_MODEL`) periodicamente com
  `scripts/avaliar_extracao.py` - um modelo mais barato que mantenha a
  qualidade de extracao aceitavel pode ser uma economia significativa em
  escala, mesmo que seja pior "no papel" em benchmarks genericos.

## 5. Arquivamento de longo prazo

`processados/` e `falhas/` acumulam todo arquivo ja tratado, sem nenhuma
limpeza automatica - deliberado hoje (nunca excluir automaticamente, ver
[boas_praticas_e_governanca.md](boas_praticas_e_governanca.md)), mas em
volume alto sustentado por muito tempo (potencialmente milhoes de arquivos),
vale revisar uma politica de arquivamento frio (mover para um storage mais
barato apos N meses) em vez de deletar - fora do escopo atual, mas algo para
reavaliar quando o volume acumulado justificar.
