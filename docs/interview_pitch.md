# Roteiro para entrevista

Notas de apoio para falar sobre este projeto em uma entrevista tecnica ou conversa de portfolio.

## Pitch de 30 segundos

Este projeto automatiza a leitura de Ordens de Compra em PDF que uma distribuidora de produtos para saude recebe de dezenas de hospitais clientes, cada um com um layout de documento diferente. Em vez de escrever um parser para cada layout, o pipeline usa um LLM com um schema fixo para normalizar qualquer PDF em dados estruturados, que sao carregados em um banco relacional e ficam disponiveis para consulta SQL, exportacao e um relatorio final.

## Perguntas que provavelmente vao surgir

Por que usar um LLM em vez de um parser tradicional?
Porque o numero de layouts diferentes cresce com o numero de clientes, e um parser posicional ou baseado em regex precisaria de manutencao constante. A troca e previsibilidade determinista por generalizacao: o LLM lida bem com um layout nunca visto, ao custo de nao ser 100% garantido campo a campo. Por isso o schema e validado com Pydantic e cada extracao carrega um campo de confianca, para que erros sejam detectaveis em vez de silenciosos.

Como voce garante que o LLM nao alucina dados?
O prompt instrui explicitamente a usar null quando um campo nao existe no texto, em vez de inventar. A saida e validada contra um schema Pydantic estrito antes de tocar o banco, entao uma resposta malformada falha a validacao e e registrada em log, nao e silenciosamente aceita. Alem disso, existe um harness de avaliacao (`scripts/avaliar_extracao.py`) que roda a extracao de verdade contra os 4 PDFs sinteticos e compara campo a campo com o gabarito conhecido, dando um numero real de acerto em vez de so uma alegacao de confianca. Isso nao elimina o risco de erro de extracao, mas o torna mensuravel e auditavel.

Como voce lidou com dado sensivel (LGPD)?
Dados clinicos (paciente, convenio, cirurgiao) foram isolados em uma tabela separada desde o desenho do schema, sem participar de nenhuma consulta comercial ou exportacao. Essa decisao foi tomada antes de escrever qualquer codigo de extracao, nao como um ajuste posterior.

Por que existe um modo demo separado do modo producao?
Para que o projeto seja avaliavel (por um recrutador, por exemplo) sem exigir acesso a uma pasta real de OCs. O modo demo troca apenas a origem dos arquivos (PDFs sinteticos locais versus os PDFs pendentes em uma pasta configurada), mantendo identica a logica de extracao e carga.

Por que ler de uma pasta em vez de integrar direto com a caixa de e-mail?
A primeira versao integrava com o Outlook via Microsoft Graph API, o que exigia um App Registration no Azure AD com permissao de aplicativo, dependente de acesso de administrador do tenant. Ler de uma pasta configuravel resolve o mesmo problema (novas OCs entram no pipeline sem digitacao manual) sem essa dependencia: a pasta pode ser alimentada por uma regra do Outlook que ja salva anexos automaticamente, por uma pasta de rede, ou por upload manual. E uma decisao de simplificar a superficie de infraestrutura sem abrir mao da automacao.

Como o sistema lida com PDFs duplicados (o mesmo arquivo salvo mais de uma vez pela automacao)?
O pipeline detecta quando a mesma OC (mesmo numero e mesmo cliente) aparece em arquivos de origem diferentes e sinaliza os registros com um status de possivel duplicata, sem excluir nada automaticamente. A decisao de o que fazer com cada grupo (manter, corrigir, excluir) fica sempre com uma pessoa, revisando uma secao dedicada do relatorio. Foi uma escolha deliberada: um sistema automatizado nunca deveria ter permissao para apagar dado de producao sozinho, mesmo com boa justificativa aparente.

Como voce garantiria que uma auditoria conseguisse entender o que a automacao fez?
A tabela log_extracao registra toda tentativa de extracao (sucesso ou falha), com arquivo, data/hora, confianca do modelo e o erro quando houve. Essa tabela e exposta em uma secao propria do relatorio, junto com um resumo escrito das praticas de governanca do projeto (separacao de dado clinico, politica de nao exclusao automatica). A ideia e que qualquer pessoa de fora, numa auditoria, consiga reconstruir o que foi processado e por que, sem depender de alguem explicar de memoria.

O que voce faria diferente com mais tempo?
Adicionar reprocessamento automatico de OCs marcadas com baixa confianca de extracao, e um mecanismo de validacao cruzada (por exemplo, conferir se a soma dos itens bate com o valor total declarado no documento) antes de aceitar uma extracao como definitiva.

## O que este projeto demonstra

Modelagem de dados com separacao clara de responsabilidades e sensibilidade (comercial versus clinico/LGPD). Uso pratico de LLM como componente de um pipeline de producao, com validacao de schema em vez de confianca cega na resposta do modelo. Decisao consciente de reduzir dependencia de infraestrutura externa (pasta configuravel em vez de integracao direta com uma API de e-mail) sem perder automacao. Harness de avaliacao separado dos testes unitarios, medindo a qualidade real da extracao (nao so a corretude do codigo) contra um gabarito conhecido. Guardrails de governanca pensados desde o desenho: nenhuma exclusao automatica de dado, duplicidade sinalizada para revisao humana, trilha de auditoria completa via log_extracao. Organizacao de projeto pensada para ser lida por outra pessoa: documentacao em camadas, modo demo funcional, testes automatizados.
