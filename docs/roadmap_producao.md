# Roadmap para producao em escala

Este documento e diferente dos demais em `docs/`: os outros descrevem o que o
sistema **ja faz** hoje. Aqui vao recomendacoes e pontos de atencao para
quando este projeto for de fato ligado em producao com volume real (o caso
citado como referencia: uma distribuidora recebendo por volta de mil OCs por
dia) - nada disso esta implementado ainda, e uma lista do que vale revisar
antes ou durante essa transicao.

## 1. Ingestao: fluxo no Power Automate

A primeira peca que falta para ligar isso em producao nao e codigo deste
repositorio, e um fluxo no Power Automate que:

1. Monitore a caixa de e-mail onde as OCs chegam (um e-mail/pasta especifico,
   dedicado a receber essas notas).
2. Salve o(s) PDF(s) anexados na pasta de entrada que este agente le
   (`PASTA_ENTRADA_OC`).

**Frequencia sugerida para o fluxo do Power Automate**: usar o gatilho
automatico "Quando um novo e-mail chegar" (conector do Outlook/Exchange, via
disparo automatico, nao agendado) - ele reage a cada e-mail que chega, sem
precisar escolher um intervalo de verificacao, e sem custo de licenca
premium para esse gatilho especifico. Se por algum motivo o gatilho
automatico nao for viavel (ex: permissao de caixa compartilhada), a
alternativa e um fluxo agendado verificando a cada 5-15 minutos - frequente o
suficiente para os PDFs estarem sempre disponiveis bem antes da proxima
execucao do pipeline (ver secao 4), sem gerar verificacoes desnecessarias.

**Sobre o link para a nota no SharePoint** (a pergunta natural que vem
depois: "como a pessoa acessa o PDF original a partir do painel?"): o jeito
mais simples, evitando um fluxo separado so para gerar link por arquivo, e
fazer o Power Automate salvar o PDF diretamente numa pasta de
SharePoint/OneDrive que tambem esteja sincronizada localmente (cliente de
sincronizacao do OneDrive) na maquina onde o pipeline roda. Assim:

- `PASTA_ENTRADA_OC` = o caminho local sincronizado (ex:
  `C:\Users\...\OneDrive - Empresa\OC_entrada`).
- `URL_PASTA_ENTRADA_OC` = a URL web dessa mesma pasta no SharePoint.

O codigo ja monta o link de cada arquivo so concatenando essa URL base com o
nome do arquivo (`link_documento()` em `src/formatacao_painel.py`) - nao e
necessario o Power Automate gerar um link de compartilhamento por PDF
individualmente. Essa abordagem so exige confirmar que os nomes de arquivo
salvos pelo fluxo nao mudam (o Power Automate as vezes acrescenta um sufixo
tipo " (2)" em caso de nome duplicado - vale nomear os anexos de forma unica
no fluxo, por exemplo prefixando com a data/hora do e-mail, para evitar
colisao).

## 2. Frequencia de execucao do pipeline (agente)

Sugestao: rodar 2-3 vezes ao dia, distribuidas ao longo do horario
comercial, por exemplo:

- **09:00** - processa o que chegou durante a noite/madrugada e bem cedo.
- **13:00-13:30** - processa a manha, logo apos o almoco.
- **17:30-18:00** - processa a tarde, fechando o dia com o painel atualizado
  antes de quem for revisar os alertas sair.

Por que 2-3x (e nao mais frequente, nem so 1x): como o Power Automate ja
salva os PDFs continuamente (quase em tempo real, ver secao 1), rodar o
pipeline mais vezes ao dia nao muda quantos tokens sao gastos no total (cada
PDF ainda e extraido exatamente uma vez, na proxima execucao que o encontrar
pendente) - a decisao de 2-3x e sobre balancear "quao atualizado o painel
fica durante o dia" contra "nao precisar manter um agendador rodando o dia
inteiro". Se o `Agendador de Tarefas do Windows` estiver numa maquina que
fica ligada o dia todo, rodar com mais frequencia (a cada 1-2h) e igualmente
valido e deixa o painel mais fresco, sem custo adicional real.

## 3. Link para o documento original (SharePoint/OneDrive)

Hoje, em modo demo, a coluna "Documento" nunca vira link clicavel - e
proposital, nao um bug: os PDFs de demonstracao ficam apenas em
`demo_data/pdfs/`, nunca foram enviados a nenhum lugar na nuvem, entao nao ha
URL real para apontar. `URL_PASTA_ENTRADA_OC` no `.env.example` e so um
dominio de exemplo (`exemplo.sharepoint.com`), nao um endereco de verdade.

**Para producao**: configurar `PASTA_ENTRADA_OC` e `URL_PASTA_ENTRADA_OC`
apontando para a mesma pasta real do OneDrive/SharePoint (ver secao 1 acima
para o fluxo completo de ingestao) - so entao o link em `link_documento()`
(`src/formatacao_painel.py`) passa a apontar para um arquivo que existe de
verdade, protegido pela autenticacao Microsoft de quem acessar. Ver
[arquitetura_webapp.md](arquitetura_webapp.md).

## 4. Reprocessamento de PDFs a cada execucao

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

## 5. Volume e limites de execucao

Com mil OCs/dia, processar tudo de uma vez numa unica execucao arrisca
estourar o rate limit da OpenRouter. Recomendacoes:

- Calibrar `LIMITE_ARQUIVOS_POR_EXECUCAO` e `LIMITE_CONCORRENCIA` (`.env`)
  para o rate limit real do plano contratado na OpenRouter - comecar
  conservador (ex: concorrencia 5) e medir antes de aumentar.
- Acompanhar `output/logs/pipeline.log` e o alerta de falhas recentes
  (`LIMITE_ALERTA_FALHAS`) nas primeiras semanas de producao, para calibrar
  esses limites com dado real em vez de estimativa.

## 6. Custo recorrente da API

Diferente de uma aplicacao que roda uma vez e acabou, o custo por token da
OpenRouter cresce linearmente com o volume diario - com mil OCs/dia, isso
passa a ser uma linha de custo operacional recorrente, nao um detalhe
tecnico. Sugestoes, da mais impactante para a mais incremental:

1. **Trocar de modelo.** O comentario no topo de `src/llm_extractor.py` ja
   compara 4 modelos avaliados, de `anthropic/claude-sonnet-5` (~$2-3 / $10-15
   por milhao de tokens, o atual) ate `deepseek/deepseek-v4-pro` (~$0.44 /
   $0.87 - 5 a 15x mais barato). Usar `scripts/avaliar_extracao.py` para medir
   a taxa de acerto de um candidato mais barato contra o gabarito conhecido
   antes de trocar em producao - preco de tabela nao garante a melhor
   extracao para este schema especifico, mas se a qualidade se mantiver
   aceitavel, o corte de custo e imediato (so muda `OPENROUTER_MODEL`).
2. **Prompt caching.** `PROMPT_SISTEMA` (o prompt de sistema em
   `llm_extractor.py`) e grande - schema JSON completo mais varias regras de
   extracao - e identico em toda chamada, so o texto do PDF muda no final.
   Modelos com suporte a prompt caching (a Anthropic tem isso nativamente)
   cobram bem menos (~90% de desconto) pelos tokens do prompt fixo quando
   reaproveitado entre chamadas seguidas. Com mil chamadas/dia usando
   exatamente o mesmo prompt fixo, isso pode reduzir bastante o custo de
   entrada sem mudar a extracao em si - confirmar se o OpenRouter repassa
   esse recurso para o modelo escolhido (nem todo provedor atras do
   OpenRouter suporta).
3. **Evitar gastar chamada com duplicata obvia.** Hoje a duplicidade so e
   detectada depois de extrair (compara `numero_oc`+cliente ja salvos no
   banco) - ou seja, ja se pagou a chamada a LLM antes de descobrir que era o
   mesmo arquivo salvo duas vezes. Um hash do conteudo do PDF (ou nome+tamanho
   de arquivo ja visto) checado antes de chamar a API evitaria gastar tokens
   numa copia obvia.
4. **Batch API, se o provedor escolhido oferecer.** Como este pipeline nao
   precisa de resposta em tempo real (roda agendado, nao interativo), vale
   checar se o modelo escolhido via OpenRouter tem uma opcao de processamento
   em lote assincrono (a OpenAI, por exemplo, oferece a propria API de Batch
   com desconto) em troca de nao ser instantaneo.

Acompanhar o custo por chamada/modelo no painel da OpenRouter regularmente,
para saber se essas mudancas estao de fato reduzindo o gasto esperado.

## 7. Arquivamento de longo prazo

`processados/` e `falhas/` acumulam todo arquivo ja tratado, sem nenhuma
limpeza automatica - deliberado hoje (nunca excluir automaticamente, ver
[boas_praticas_e_governanca.md](boas_praticas_e_governanca.md)), mas em
volume alto sustentado por muito tempo (potencialmente milhoes de arquivos),
vale revisar uma politica de arquivamento frio (mover para um storage mais
barato apos N meses) em vez de deletar - fora do escopo atual, mas algo para
reavaliar quando o volume acumulado justificar.
