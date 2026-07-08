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

## 10. Backup do banco

Ate a migracao para Postgres/Supabase (ver secao 23), `database.fazer_backup()` copiava o banco SQLite local para `output/database/backups/` antes de cada execucao do pipeline, mantendo os 20 mais recentes. Essa funcao foi removida: o banco agora mora no Supabase, que faz backup da propria infraestrutura gerenciada (Point-in-Time-Recovery no plano pago, snapshot diario no free tier - conferir a politica vigente no painel do projeto antes de assumir uma frequencia especifica). O pipeline local nao precisa mais reimplementar isso.

## 11. Limite de arquivos por execucao

`LIMITE_ARQUIVOS_POR_EXECUCAO` (padrao 0, sem limite) restringe quantos PDFs pendentes sao processados em uma unica execucao. Se a pasta de entrada acumular muitos arquivos de uma vez (por exemplo, apos um fim de semana), processar todos de uma vez poderia esbarrar em limite de taxa da API. O excedente simplesmente fica pendente e e processado na proxima execucao agendada.

## 12. Log em arquivo

Alem do console, o pipeline grava log em `output/logs/pipeline.log` (rotativo, ate 5MB por arquivo, mantendo os 3 mais recentes). Isso importa quando o pipeline roda sem ninguem olhando a tela, por exemplo via Agendador de Tarefas do Windows a cada poucas horas: sem log em arquivo, uma falha silenciosa so seria percebida ao abrir o relatorio.

## 13. Auditoria: log de extracao e trilha completa

A tabela `log_extracao` registra toda tentativa de extracao, com sucesso ou falha: arquivo, data/hora, status, confianca do modelo, e o erro quando houve. Essa tabela e exposta integralmente na secao "Auditoria e governanca" do relatorio HTML (visualmente discreta, no final da pagina), junto com um resumo escrito das praticas descritas neste documento. A intencao e que qualquer pessoa, numa auditoria, consiga reconstruir o que foi processado e por que, sem depender de alguem explicar de memoria.

## 14. Schema aplicado manualmente, uma vez (Postgres)

Ate a migracao para Postgres/Supabase (ver secao 23), `database.inicializar_schema()` migrava o SQLite automaticamente a cada execucao, adicionando colunas novas via `ALTER TABLE` sem perder dado existente. Isso nao se aplica mais: `CREATE POLICY` (RLS) e outras instrucoes de `sql/schema_postgres.sql` nao sao idempotentes do mesmo jeito, entao o schema Postgres e aplicado manualmente, uma unica vez, no SQL Editor do Supabase (ou de novo, com cuidado, se o arquivo mudar). `database.inicializar_schema()` hoje so confirma que as tabelas esperadas existem, com um erro claro se alguma estiver faltando - nao aplica nenhum DDL sozinho.

## 15. Testes automatizados vs harness de avaliacao

Duas camadas de verificacao, com propositos diferentes:

- `tests/` (pytest): testes unitarios rapidos, que usam um cliente OpenRouter/OpenAI simulado. Verificam se o codigo funciona (parsing de JSON, validacao de schema, logica de banco), nao se a extracao esta correta de verdade. Rodam em segundos, sem custo.
- `scripts/avaliar_extracao.py`: harness de avaliacao que chama a API de verdade via OpenRouter contra os 4 PDFs sinteticos e compara o resultado, campo a campo, com um gabarito conhecido. Mede a qualidade real da extracao, com um numero de acerto, e serve tambem para comparar modelos diferentes (basta mudar OPENROUTER_MODEL no .env e rodar de novo). Custa tempo e credito de API a cada execucao, por isso e rodado manualmente, nao automaticamente.

## 16. Integracao continua (CI)

Um workflow do GitHub Actions (`.github/workflows/testes.yml`) roda a suite de testes automaticamente a cada push ou pull request, uma vez que o projeto seja publicado no GitHub. Como os testes nao chamam a API de verdade (usam um cliente simulado), rodar em CI nao tem custo de API nem exige nenhuma credencial configurada no repositorio.

## 17. Configuracao e segredos

Credenciais ficam exclusivamente no arquivo `.env` (local) ou nas variaveis de ambiente do host de deploy (Render), nunca versionadas (`.env` esta no `.gitignore`). O `.env.example` documenta quais variaveis existem, sem nenhum valor real. Nenhuma chave ou senha e escrita diretamente no codigo em nenhum momento.

Desde a migracao para backend real (Fase 0-6, ver secao 23), a lista de credenciais cresceu: `OPENROUTER_API_KEY` (extracao via LLM), `SUPABASE_URL`/`SUPABASE_ANON_KEY` (publicas por design do Supabase, protegidas por RLS - ver secao 24 - nao precisam do mesmo cuidado que as duas abaixo), `SUPABASE_SERVICE_ROLE_KEY` (ignora RLS - so o pipeline local usa, nunca o site publicado), `DATABASE_URL_DEMO`/`DATABASE_URL_PRODUCAO` (senha do Postgres embutida na string de conexao). O deploy no Render (secao 23) recebe so as variaveis que o site de fato usa (nunca `SUPABASE_SERVICE_ROLE_KEY`, que o site nunca chama) - reduz o que fica exposto no ambiente do servidor publico.

Incidente registrado: durante a Fase 6, a senha do Postgres, a `SUPABASE_SERVICE_ROLE_KEY` e a `OPENROUTER_API_KEY` foram coladas em texto simples nesta conversa com o assistente de IA, para fins de depuracao. Nenhuma delas chegou a ser commitada no repositorio, mas por terem transitado por um canal que nao e o `.env`, as tres foram tratadas como potencialmente comprometidas e rotacionadas (senha do banco resetada no painel do Supabase, `service_role` key antiga revogada e substituida por uma nova, chave do OpenRouter revogada e substituida por uma nova) - cada uma testada e confirmada funcionando antes de a antiga ser desativada. Licao para o futuro: preferir descrever o problema ou colar so um prefixo/trecho mascarado da credencial, nunca o valor completo, mesmo em depuracao pontual.

## 18. Central de alertas unificada

As quatro sinalizacoes de qualidade de dado (duplicidade, valor divergente, baixa confianca, CNPJ invalido) sao reunidas em uma unica consulta, `sql/queries/central_alertas.sql` (uma UNION ALL das quatro), e exibidas como uma tabela unica no relatorio HTML, uma linha por combinacao de OC e tipo de alerta, cada uma com um selo colorido identificando o tipo. As quatro consultas individuais continuam existindo separadamente (`possiveis_duplicatas.sql`, `alertas_valor.sql`, `baixa_confianca.sql`, `cnpj_invalido.sql`) para quem precisar analisar um tipo especifico isoladamente, mas o painel mostra a visao consolidada, pensada para que uma pessoa de negocio veja rapidamente tudo que precisa de atencao, sem navegar por quatro secoes separadas. Desde a Fase 5 do backend real (ver secao 24), cada alerta pode ser marcado como revisado (ou desfeito, se clicado por engano) diretamente no site, por um usuario com papel `admin` ou `revisor` - sem isso, o unico jeito de saber se um alerta ja tinha sido olhado era a memoria de quem revisou.

## 19. Modelo de extracao configuravel (OpenRouter)

A extracao roda via OpenRouter em vez de uma API de um unico provedor, o que permite trocar de modelo (Anthropic, OpenAI, DeepSeek, Z.ai/GLM, etc) mudando apenas `OPENROUTER_MODEL` no `.env`, sem alterar codigo. Isso e util tanto para controle de custo (modelos diferentes tem precos bem diferentes por milhao de tokens) quanto para comparar qualidade de extracao entre eles usando `scripts/avaliar_extracao.py` (secao 15), que roda o mesmo gabarito conhecido contra qualquer modelo configurado e imprime a taxa de acerto. A lista de modelos ja avaliados neste projeto, com preco aproximado de cada um, fica comentada no topo de `src/llm_extractor.py`.

## 20. Separacao entre banco de demonstracao e banco real

`pipeline.py` e `report_generator.py` gravam/leem em arquivos diferentes dependendo do `--modo`: modo demo usa `output/database/oc_agent_demo.db` e gera `output/report/relatorio_demo.html`; modo producao usa `output/database/oc_agent.db` e gera `output/report/relatorio.html`. Nenhum dos dois e o padrao "escondido" do outro - a escolha e sempre explicita via `--modo` (ou `--db`/`--saida` para sobrepor manualmente). O objetivo e simples: dado sintetico usado para demonstrar o projeto nunca deve aparecer misturado com dado real de producao no mesmo painel, na mesma consulta SQL ou no mesmo CSV exportado, o que evitaria uma pessoa de negocio tomar uma decisao real em cima de um numero fictício por engano.

## 21. O painel nunca embute o PDF original, so um link para onde ele esta

Uma versao anterior do relatorio HTML chegou a embutir a imagem da primeira pagina de cada PDF de demonstracao diretamente no painel (util para portfolio, ja que os PDFs sinteticos nao tem dado real). Essa ideia foi revertida deliberadamente antes de valer para producao: um PDF real de OC pode conter dado de saude do paciente (LGPD), entao ele nunca deve ficar embutido ou guardado dentro do relatorio HTML, mesmo que o painel em si so mostre campos comerciais. Em vez disso, `_link_documento()` (em `report_generator.py`) transforma o nome do arquivo de origem - na tabela de OCs recentes, na central de alertas e no log de auditoria - em um link clicavel, construido a partir de `URL_PASTA_ENTRADA_OC` no `.env`. Em producao, essa variavel aponta para a pasta no OneDrive/SharePoint da empresa (a mesma pasta de `PASTA_ENTRADA_OC`, so que pelo link web em vez do caminho local); abrir o link exige a autenticacao Microsoft de quem estiver acessando, o que e o comportamento esperado e desejado - o controle de acesso ao documento continua sendo o do OneDrive/SharePoint da empresa, nao algo que o painel HTML precisa reimplementar. Sem essa variavel configurada (como no modo demo, onde nao ha uma pasta real na nuvem), a coluna mostra so o nome do arquivo, sem link.

## 22. Grants residuais do Supabase, revogados por precaucao

Ao revisar o projeto Supabase ja em uso, foi encontrado que a propria plataforma concede `TRUNCATE`, `REFERENCES` e `TRIGGER` para os papeis `anon` e `authenticated` em toda tabela nova do schema `public`, por padrao - independente do toggle "Automatically expose new tables" (que so afeta `SELECT`/`INSERT`/`UPDATE`/`DELETE`). Ninguem consegue *ler* dado por esses privilegios via a API publica normal (o PostgREST, camada usada pelo site, nao expoe um verbo HTTP equivalente a `TRUNCATE`), mas em tese `TRUNCATE` permitiria apagar uma tabela inteira de uma vez, o que vai direto contra a regra central deste projeto de nunca excluir dado sem revisao humana. `sql/schema_postgres.sql` agora revoga esses tres privilegios de `anon`/`authenticated` em todas as tabelas, mantendo so o `SELECT` (e o `UPDATE` pontual em `ordens_compra`, para o fluxo de revisao) que sao realmente necessarios - defesa em profundidade, mesmo sem uma rota de ataque conhecida hoje. Confirmado por teste real contra a API publica (chave anonima) que a leitura de `dados_clinicos` continua bloqueada (`401`) antes e depois dessa limpeza.

## 23. Backend real (Supabase + FastAPI) substituindo o relatorio estatico

A partir da Fase 0, o projeto ganhou um backend de verdade: Postgres gerenciado, autenticacao e RLS via Supabase, servido por um site FastAPI (`src/webapp/`) com login Microsoft, no lugar do relatorio HTML estatico como unica interface (`report_generator.py` continua existindo, como snapshot offline/fallback). Detalhes completos (Azure App Registration, configuracao do provedor Azure no Supabase, troca do modo pessoal para o modo empresa) ficam em `docs/arquitetura_webapp.md`. Resumo das decisoes relevantes para governanca:

- Dois projetos Supabase separados (demo e producao), nunca o mesmo projeto - mesma filosofia da secao 20 (nunca misturar dado sintetico com dado real), agora tambem valendo para `auth.users` e RLS.
- Deploy no Render (`render.yaml`), plano gratuito, sem disco persistente (o banco mora inteiramente no Supabase). O servico gratuito "dorme" apos ~15 minutos sem trafego (o primeiro acesso depois disso demora ~30-50s) - aceitavel para portfolio, nao tratado como bug.
- Pool de conexoes (`src/webapp/pool.py`), aberto uma vez na subida do processo, reaproveitado entre requisicoes - evita o custo de abrir uma conexao nova (handshake completo via connection pooler do Supabase) a cada pagina carregada.

## 24. Controle de acesso por papel (RBAC via RLS)

Alem de nunca excluir dado automaticamente (secao 2), o backend real adiciona uma segunda camada de controle: quem pode fazer o que. Tres papeis (`perfis.papel`): `leitor` (so visualiza, padrao de todo usuario novo), `revisor` e `admin` (podem marcar/desmarcar uma OC como revisada). A garantia de verdade e a policy de RLS `revisor_ou_admin_pode_revisar` (`sql/schema_postgres.sql`), avaliada pelo proprio Postgres a cada tentativa de `UPDATE` em `ordens_compra` - nao um `if` no codigo do FastAPI. Uma checagem de papel tambem existe no nivel da aplicacao (`webapp/dependencias.exige_papel`, usada nas rotas de revisao) e outra, mais leve, so para decidir se mostra o botao na tela (le o papel via conexao de confianca, sem round-trip extra - nao e usada para autorizar nada); a autorizacao real, que um bug nessas duas camadas de aplicacao nao conseguiria contornar, e sempre a policy no banco. Isso e verificado por teste automatizado real (`tests/test_rls_papeis.py`, roda contra o Supabase de verdade): um usuario `leitor` tenta marcar uma OC como revisada e a policy bloqueia silenciosamente (RLS nao levanta excecao, so devolve zero linhas afetadas - um bug de policy nunca aparece como erro, so como dado que "sumiu"), enquanto `admin`/`revisor` conseguem.

O fluxo de revisao (marcar e desfazer) segue a mesma regra da secao 2: nunca uma exclusao ou correcao automatica, sempre uma acao humana explicita, e reversivel (o botao "(desfazer)" existe exatamente para corrigir um clique errado sem precisar mexer no banco na mao).

## 25. Keep-alive do projeto Supabase demo

Por ser portfolio, o site pode ficar dias sem acesso entre a visita de um recrutador e outro. O Supabase pausa automaticamente projetos do free tier inativos por muito tempo (a reativacao depois disso nao e instantanea) - um workflow do GitHub Actions (`.github/workflows/keep-alive.yml`) chama o endpoint de saude do Supabase Auth do projeto demo uma vez por semana, so para contar como atividade e evitar a pausa. Deliberadamente nao tenta manter o Render sempre acordado (precisaria rodar a cada poucos minutos, o que nao compensa so para evitar uns 30-50s de espera no primeiro acesso).

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
| Referencia ao PDF de origem no relatorio | Link para a pasta (exige login Microsoft) | Embutir o PDF/imagem no painel |
| Usuario `leitor` tenta marcar OC como revisada | RLS bloqueia no banco (policy no Postgres) | Confiar so no gate da aplicacao |
| OC marcada como revisada por engano | Permite desfazer (acao humana, reversivel) | Excluir/corrigir sem acao humana |
