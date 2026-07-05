# Case study

## O problema

Na MDR/Mederi, distribuidora de produtos para saude (OPME), Ordens de Compra chegam por e-mail em PDF, enviadas por dezenas de hospitais e clientes diferentes. Cada hospital usa seu proprio sistema de emissao (alguns usam TOTVS, outros MV2000, outros modelos proprios), entao o layout visual do documento varia de cliente para cliente.

Hoje, os dados dessas OCs (numero do pedido, itens, valores, prazo de pagamento, e quando presente, dados clinicos do procedimento) precisam ser lidos manualmente de cada PDF para virar informacao utilizavel: conferencia de pedido, faturamento, analise de volume por cliente. Esse processo manual nao escala e e sujeito a erro de digitacao.

## A abordagem

A tentacao inicial em um problema assim e escrever um parser por template: identificar coordenadas de texto ou padroes de regex especificos para cada layout de hospital. Essa abordagem foi descartada de proposito. Com dezenas de clientes atuais e novos entrando com frequencia, um parser por template significaria escrever e manter uma nova extracao a cada vez que um hospital novo (ou uma nova versao do sistema de um hospital existente) aparecesse.

Em vez disso, o pipeline usa um modelo de linguagem (Claude) para ler o texto extraido do PDF e devolver os campos ja estruturados, seguindo um schema fixo validado por Pydantic. A logica de "entender o layout" fica a cargo do modelo, nao de codigo escrito a mao. Isso significa que um layout novo, nunca visto antes, tem boas chances de ser extraido corretamente sem nenhuma mudanca no codigo.

Quatro padroes de layout reais (anonimizados) foram usados como referencia para validar essa abordagem: um hospital com cabecalho classico, um sistema TOTVS com tabela larga, um sistema MV2000 com campos linha a linha, e uma grade hospitalar simples com bordas. Os quatro geraram extracoes corretas usando o mesmo prompt e o mesmo schema.

## Decisoes de design que valem destacar

Separacao entre dado comercial e dado de saude. O campo de observacao de uma OC frequentemente contem nome do paciente, convenio e cirurgiao responsavel, por conta do processo de faturamento por procedimento. Esses dados sao extraidos, mas guardados em uma tabela fisicamente separada (`dados_clinicos`), nunca exposta em relatorios ou exportacoes comerciais. Ver [data_model.md](data_model.md) para detalhes.

Modo demo funcional de verdade. O repositorio roda sem nenhuma credencial de infraestrutura, usando PDFs sinteticos que replicam os layouts reais com dados totalmente ficticios. A extracao em si, porem, nao e simulada: o mesmo codigo que roda em producao roda no modo demo, chamando a API de verdade via OpenRouter. A unica coisa que muda entre demo e producao e a origem dos arquivos (a pasta local de exemplo versus uma pasta configuravel onde os PDFs recebidos ja tenham sido salvos).

Idempotencia na carga do banco. Reprocessar o mesmo PDF (por exemplo, apos corrigir um bug de extracao) atualiza o registro existente em vez de duplicar, usando numero da OC e nome do arquivo como chave.

Ingestao por pasta em vez de integracao direta com a caixa de e-mail. A primeira versao do projeto integrava diretamente com o Outlook via Microsoft Graph API, o que exigia um App Registration no Azure AD com permissao de aplicativo para leitura de e-mail, algo que depende de acesso de administrador do tenant e nem sempre esta disponivel para quem so precisa rodar o pipeline. A troca foi ler os PDFs de uma pasta configuravel, que pode ser alimentada de fora do pipeline (por exemplo, por uma regra do Outlook que ja salva os anexos automaticamente em uma pasta do OneDrive ou de rede, ou um fluxo do Power Automate). O resultado e o mesmo (novas OCs entram no pipeline sem digitacao manual), com uma dependencia de infraestrutura a menos.

Duplicidade sinalizada, nunca excluida automaticamente. Uma automacao de ingestao por pasta pode salvar o mesmo PDF mais de uma vez (por exemplo, se o fluxo de automacao rodar de novo antes do arquivo anterior ser processado). Em vez de tentar decidir sozinho qual copia e a duplicata e apagar uma delas, o pipeline apenas sinaliza o grupo (`status_extracao = 'possivel_duplicata'`) e deixa a decisao final para revisao manual, visivel em uma secao propria do relatorio. Esse e um guardrail deliberado: o codigo nunca tem permissao para excluir uma ordem de compra por conta propria.

## Resultado

O pipeline completo (leitura de PDF, extracao via LLM, carga em banco relacional, consultas SQL prontas, exportacao CSV e relatorio HTML) roda ponta a ponta a partir de quatro PDFs de exemplo, sem nenhuma configuracao alem de uma chave de API do Claude. O modo producao esta implementado e funcional, pronto para ser ligado assim que a pasta de entrada for configurada.
