# Boas praticas e governanca do projeto

Este documento reune as regras de governanca e as praticas de engenharia adotadas no oc-agent-automation, para servir de referencia rapida (inclusive em uma eventual auditoria) sobre o que o sistema faz, o que ele deliberadamente nao faz, e por que.

## 1. Separacao de dados sensiveis (LGPD)

Dados de saude do paciente (nome, convenio, carteirinha, cirurgiao, data de realizacao, aviso de cirurgia, setor), quando presentes no campo de observacao de uma OC, sao extraidos para uma tabela propria, `dados_clinicos`, fisicamente separada das tabelas comerciais. Nenhuma consulta SQL de faturamento, exportacao CSV ou secao do relatorio HTML faz join com essa tabela. Essa decisao foi tomada no desenho do schema, antes de qualquer codigo de extracao ser escrito.

## 2. Guardrail: nenhuma exclusao automatica de dado

Regra explicita do projeto: nao existe, em nenhum lugar do codigo, uma funcao que exclua uma linha de `ordens_compra`. Situacoes que poderiam parecer candidatas a uma exclusao automatica foram resolvidas de outra forma:

- Duplicidade (mesma OC salva em arquivos diferentes): sinalizada com `status_extracao = 'possivel_duplicata'`, nunca excluida. Ver secao 3.
- Arquivo com falha repetida de extracao: movido para uma pasta de quarentena, nunca apagado do disco. Ver secao 8.

Se no futuro fizer sentido excluir de fato um registro (por exemplo, uma duplicata confirmada manualmente), essa acao deve continuar sendo manual, feita por uma pessoa com acesso direto ao banco (via DB Browser ou a extensao SQLite do VS Code), nunca uma funcao automatica do pipeline.

## 3. Duplicidade sinalizada, nunca excluida

Quando a mesma OC (mesmo `numero_oc` e mesmo `cliente_id`) aparece em mais de um arquivo de origem, provavel resultado do mesmo PDF sendo salvo duas vezes pela automacao de ingestao (por exemplo, um fluxo do Power Automate que reprocessa o mesmo e-mail), `database.py` marca todos os registros do grupo com `status_extracao = 'possivel_duplicata'`. A central de alertas do relatorio HTML (ver secao 18) lista esses grupos, entre outros tipos de alerta, para revisao manual.

## 4. Validacao cruzada de valores

Depois de gravar os itens de uma OC, o pipeline confere se a soma dos valores dos itens (com ou sem o valor do frete) bate com o `valor_total` declarado no documento, dentro de uma tolerancia de R$ 0,02. Quando ha divergencia, a OC e marcada com `alerta_valor_divergente = 1` e aparece na central de alertas do relatorio (ver secao 18). Nada e corrigido automaticamente: a divergencia pode ser um erro de extracao, mas tambem pode ser legitima (desconto, imposto, arredondamento nao capturado nos itens).

## 5. Criterio de confianca de extracao

O campo `confianca_extracao` e uma autoavaliacao do proprio modelo (nao uma metrica calculada pelo pipeline), mas seguindo um criterio explicito de quatro faixas definido no prompt (ver `docs/data_model.md` para a tabela completa). Quando a confianca relatada fica abaixo de `LIMITE_CONFIANCA_BAIXA` (padrao 0.7), a OC e marcada com `alerta_baixa_confianca = 1` e aparece na central de alertas do relatorio (ver secao 18), para revisao manual antes de considerar os dados definitivos.

## 6. Validacao de CNPJ

`src/validadores.py` confere o digito verificador do CNPJ do cliente e do fornecedor (algoritmo padrao, independente do LLM). Um CNPJ com digito errado e sinalizado com `alerta_cnpj_invalido = 1` e aparece na central de alertas do relatorio (ver secao 18). Diferente dos demais alertas do projeto, este e determinístico: nao ha ambiguidade sobre se o CNPJ e valido ou nao, so sobre o que fazer a respeito (corrigir a extracao, ou confirmar que o documento original ja veio com o CNPJ errado).

## 7. Resiliencia: retry com backoff

Chamadas a API via OpenRouter podem falhar por instabilidade transitoria (erro de rede, limite de taxa, erro temporario do servidor). `llm_extractor.py` tenta novamente automaticamente nesses casos (ate 3 tentativas, com espera crescente entre elas: 2s, depois 4s). Erros que nao sao transitorios (chave invalida, requisicao malformada, resposta que nao bate com o schema) falham imediatamente, sem retry, porque tentar de novo nao mudaria o resultado.

## 8. Quarentena de arquivos com falha repetida

Um PDF que falha a extracao repetidas vezes (por padrao, 3 tentativas, configuravel via `LIMITE_FALHAS_QUARENTENA` no `.env`) e movido para uma subpasta `falhas/` dentro da pasta de entrada, em vez de ficar sendo tentado para sempre a cada execucao do pipeline. O arquivo nao e apagado, apenas tirado da fila de pendentes, disponivel para uma pessoa inspecionar o motivo da falha (PDF corrompido, layout que o modelo nao consegue interpretar, etc).

## 9. Alertas de falhas recentes

Duas camadas de alerta, ambas configuraveis via `LIMITE_ALERTA_FALHAS` no `.env` (padrao 3):

- Durante uma execucao do pipeline, se o numero de falhas naquela execucao atingir o limite, um alerta e registrado no log com destaque.
- No relatorio HTML, um banner vermelho aparece no topo se houve falhas de extracao acima do limite nas ultimas 24 horas, independente de quantas execucoes do pipeline geraram essas falhas.

Como o projeto roda localmente (sem um servico continuamente ativo para enviar notificacoes por e-mail ou Teams), o alerta hoje e visual (banner no dashboard) e via log. Uma notificacao "empurrada" (e-mail, Teams) exigiria credenciais adicionais e ficaria como proximo passo natural.

## 10. Backup automatico do banco

Antes de cada execucao do pipeline, `database.fazer_backup()` copia o banco SQLite para `output/database/backups/`, com data e hora no nome do arquivo, mantendo apenas os 20 backups mais recentes (mais antigos sao apagados automaticamente para nao acumular disco indefinidamente). Se o banco ainda nao existir (primeira execucao), nao ha o que fazer backup.

## 11. Limite de arquivos por execucao

`LIMITE_ARQUIVOS_POR_EXECUCAO` (padrao 0, sem limite) restringe quantos PDFs pendentes sao processados em uma unica execucao. Se a pasta de entrada acumular muitos arquivos de uma vez (por exemplo, apos um fim de semana), processar todos de uma vez poderia esbarrar em limite de taxa da API. O excedente simplesmente fica pendente e e processado na proxima execucao agendada.

## 12. Log em arquivo

Alem do console, o pipeline grava log em `output/logs/pipeline.log` (rotativo, ate 5MB por arquivo, mantendo os 3 mais recentes). Isso importa quando o pipeline roda sem ninguem olhando a tela, por exemplo via Agendador de Tarefas do Windows a cada poucas horas: sem log em arquivo, uma falha silenciosa so seria percebida ao abrir o relatorio.

## 13. Auditoria: log de extracao e trilha completa

A tabela `log_extracao` registra toda tentativa de extracao, com sucesso ou falha: arquivo, data/hora, status, confianca do modelo, e o erro quando houve. Essa tabela e exposta integralmente na secao "Auditoria e governanca" do relatorio HTML (visualmente discreta, no final da pagina), junto com um resumo escrito das praticas descritas neste documento. A intencao e que qualquer pessoa, numa auditoria, consiga reconstruir o que foi processado e por que, sem depender de alguem explicar de memoria.

## 14. Migracao de schema sem perda de dados

SQLite nao migra automaticamente um schema existente: `CREATE TABLE IF NOT EXISTS` nao adiciona colunas novas a uma tabela ja criada. Sempre que uma coluna nova e adicionada a `ordens_compra`, `database.inicializar_schema()` verifica quais colunas ja existem e adiciona as que faltarem via `ALTER TABLE`, preservando os dados ja gravados. Isso importa especialmente para um banco de producao, que acumula dados reais ao longo do tempo enquanto o codigo continua evoluindo. Vale notar: essa migracao so adiciona a coluna com o valor padrao, ela nao reprocessa retroativamente registros ja gravados por uma versao anterior do codigo.

## 15. Testes automatizados vs harness de avaliacao

Duas camadas de verificacao, com propositos diferentes:

- `tests/` (pytest): testes unitarios rapidos, que usam um cliente OpenRouter/OpenAI simulado. Verificam se o codigo funciona (parsing de JSON, validacao de schema, logica de banco), nao se a extracao esta correta de verdade. Rodam em segundos, sem custo.
- `scripts/avaliar_extracao.py`: harness de avaliacao que chama a API de verdade via OpenRouter contra os 4 PDFs sinteticos e compara o resultado, campo a campo, com um gabarito conhecido. Mede a qualidade real da extracao, com um numero de acerto, e serve tambem para comparar modelos diferentes (basta mudar OPENROUTER_MODEL no .env e rodar de novo). Custa tempo e credito de API a cada execucao, por isso e rodado manualmente, nao automaticamente.

## 16. Integracao continua (CI)

Um workflow do GitHub Actions (`.github/workflows/testes.yml`) roda a suite de testes automaticamente a cada push ou pull request, uma vez que o projeto seja publicado no GitHub. Como os testes nao chamam a API de verdade (usam um cliente simulado), rodar em CI nao tem custo de API nem exige nenhuma credencial configurada no repositorio.

## 17. Configuracao e segredos

Credenciais (`OPENROUTER_API_KEY`) ficam exclusivamente no arquivo `.env`, que nunca e versionado (esta no `.gitignore`). O `.env.example` documenta quais variaveis existem, sem nenhum valor real. Nenhuma chave ou senha e escrita diretamente no codigo em nenhum momento.

## 18. Central de alertas unificada

As quatro sinalizacoes de qualidade de dado (duplicidade, valor divergente, baixa confianca, CNPJ invalido) sao reunidas em uma unica consulta, `sql/queries/central_alertas.sql` (uma UNION ALL das quatro), e exibidas como uma tabela unica no relatorio HTML, uma linha por combinacao de OC e tipo de alerta, cada uma com um selo colorido identificando o tipo. As quatro consultas individuais continuam existindo separadamente (`possiveis_duplicatas.sql`, `alertas_valor.sql`, `baixa_confianca.sql`, `cnpj_invalido.sql`) para quem precisar analisar um tipo especifico isoladamente, mas o painel mostra a visao consolidada, pensada para que uma pessoa de negocio veja rapidamente tudo que precisa de atencao, sem navegar por quatro secoes separadas. Vale notar: a migracao de schema (secao 14) so adiciona a coluna do alerta com valor padrao, ela nao reprocessa registros gravados antes de o alerta existir. Uma OC salva por uma versao anterior do codigo so aparecera sinalizada por um alerta novo depois de ser reprocessada.

## 19. Modelo de extracao configuravel (OpenRouter)

A extracao roda via OpenRouter em vez de uma API de um unico provedor, o que permite trocar de modelo (Anthropic, OpenAI, DeepSeek, Z.ai/GLM, etc) mudando apenas `OPENROUTER_MODEL` no `.env`, sem alterar codigo. Isso e util tanto para controle de custo (modelos diferentes tem precos bem diferentes por milhao de tokens) quanto para comparar qualidade de extracao entre eles usando `scripts/avaliar_extracao.py` (secao 15), que roda o mesmo gabarito conhecido contra qualquer modelo configurado e imprime a taxa de acerto. A lista de modelos ja avaliados neste projeto, com preco aproximado de cada um, fica comentada no topo de `src/llm_extractor.py`.

## 20. Separacao entre banco de demonstracao e banco real

`pipeline.py` e `report_generator.py` gravam/leem em arquivos diferentes dependendo do `--modo`: modo demo usa `output/database/oc_agent_demo.db` e gera `output/report/relatorio_demo.html`; modo producao usa `output/database/oc_agent.db` e gera `output/report/relatorio.html`. Nenhum dos dois e o padrao "escondido" do outro - a escolha e sempre explicita via `--modo` (ou `--db`/`--saida` para sobrepor manualmente). O objetivo e simples: dado sintetico usado para demonstrar o projeto nunca deve aparecer misturado com dado real de producao no mesmo painel, na mesma consulta SQL ou no mesmo CSV exportado, o que evitaria uma pessoa de negocio tomar uma decisao real em cima de um numero fictício por engano.

## Resumo rapido

| Situacao | O que o sistema faz | O que o sistema nunca faz |
|---|---|---|
| Mesma OC em arquivos diferentes | Sinaliza (`possivel_duplicata`) | Excluir automaticamente |
| Soma dos itens diverge do total | Sinaliza (`alerta_valor_divergente`) | Corrigir o valor sozinho |
| Confianca relatada abaixo do limite | Sinaliza (`alerta_baixa_confianca`) | Aceitar sem revisao |
| CNPJ com digito verificador errado | Sinaliza (`alerta_cnpj_invalido`) | Corrigir ou inventar um CNPJ |
| Falha transitoria de rede na API | Tenta de novo (ate 3x, com espera) | Desistir na primeira falha |
| Arquivo falha repetidamente | Move para pasta de quarentena | Excluir o arquivo |
| Muitas falhas em pouco tempo | Alerta no log e no dashboard | Ficar em silencio |
| Antes de cada execucao | Faz backup do banco (mantem 20) | Rodar sem rede de seguranca |
| Muitos arquivos pendentes de uma vez | Processa ate o limite, resto fica para depois | Estourar limite de taxa da API |
| Coluna nova no schema | Migra a tabela existente (ALTER TABLE) | Perder dados do banco antigo |
| Dado clinico (LGPD) | Isola em tabela propria | Expor em relatorio ou export comercial |
