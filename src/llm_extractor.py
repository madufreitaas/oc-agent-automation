"""
Extracao estruturada de dados de OC a partir de texto bruto, via OpenRouter.

A ideia central do projeto: em vez de um parser posicional/regex por
template (que quebra a cada novo layout de hospital), pedimos ao modelo
para ler o texto puro e devolver JSON no schema fixo definido em schema.py.
Isso escala para novos fornecedores/hospitais sem escrever um parser novo
para cada um.

A extracao roda via OpenRouter (https://openrouter.ai), que expoe varios
provedores (Anthropic, OpenAI, DeepSeek, Z.ai/GLM, etc) atras de uma unica
API compativel com o formato da OpenAI. Isso permite comparar modelos
diferentes so trocando o slug do modelo, sem mudar nenhum codigo.
"""

from __future__ import annotations

import json
import logging
import os
import time

from openai import APIConnectionError, InternalServerError, OpenAI, RateLimitError
from pydantic import ValidationError

from schema import OrdemDeCompra

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# --- Como trocar de modelo -------------------------------------------------
# Basta definir OPENROUTER_MODEL no .env com um dos slugs abaixo (ou qualquer
# outro modelo disponivel em https://openrouter.ai/models) - nao precisa
# mexer neste arquivo. O preco muda com frequencia, confira o valor atual no
# site antes de decidir; os numeros abaixo sao uma referencia de 2026-07-04,
# em dolares por 1 milhao de tokens (entrada / saida):
#
#   anthropic/claude-sonnet-5   ~$2-3   / $10-15   - o mais caro, ja validado
#                                                     neste projeto (rubrica de
#                                                     confianca e prompt foram
#                                                     escritos pensando nele)
#   openai/gpt-5.4-mini         ~$0.75  / $4.50    - bom equilibrio custo/qualidade,
#                                                     forte em seguir schema JSON
#   z-ai/glm-5.2                ~$0.85  / $2.70    - intermediario, bom em
#                                                     raciocinio/instrucoes longas
#   deepseek/deepseek-v4-pro    ~$0.44  / $0.87    - o mais barato dos quatro,
#                                                     contexto de 1M tokens
#
# Antes de trocar de vez em producao, rode scripts/avaliar_extracao.py com
# cada candidato (mudando so OPENROUTER_MODEL) e compare a taxa de acerto
# contra os 4 PDFs de demonstracao - preco de tabela nao garante a melhor
# extracao para este schema especifico.
#
# Usado apenas se OPENROUTER_MODEL nao estiver definida em nenhum lugar.
MODELO_PADRAO = "anthropic/claude-sonnet-5"


def modelo_configurado() -> str:
    """Modelo efetivamente usado na proxima extracao: OPENROUTER_MODEL do
    ambiente, ou MODELO_PADRAO se a variavel nao estiver definida. Lido a
    cada chamada (nao uma unica vez no import do modulo), porque o .env so e
    carregado dentro de main()/load_dotenv() em pipeline.py e nos scripts -
    ou seja, depois que este modulo ja foi importado. Se o valor fosse
    fixado em uma constante de modulo, mudar OPENROUTER_MODEL no .env nunca
    teria efeito."""
    return os.environ.get("OPENROUTER_MODEL", MODELO_PADRAO)

# Retry com backoff exponencial para falhas transitorias (rede instavel, rate
# limit, erro temporario do servidor). Erros de autenticacao, requisicao
# invalida, ou de validacao (JSON/schema) nao sao retentados - falham na hora.
TENTATIVAS_PADRAO = 3
ESPERA_BASE_SEGUNDOS = 2.0
EXCECOES_RETENTAVEIS = (APIConnectionError, RateLimitError, InternalServerError)


def _retry_com_backoff(func, tentativas: int = TENTATIVAS_PADRAO, espera_base: float = ESPERA_BASE_SEGUNDOS):
    """Chama func() novamente em caso de falha transitoria, com espera crescente
    (espera_base, espera_base*2, espera_base*4, ...) entre as tentativas."""

    ultimo_erro: Exception | None = None
    for tentativa in range(1, tentativas + 1):
        try:
            return func()
        except EXCECOES_RETENTAVEIS as exc:
            ultimo_erro = exc
            if tentativa < tentativas:
                espera = espera_base * (2 ** (tentativa - 1))
                logger.warning(
                    "Chamada a OpenRouter falhou (tentativa %d/%d), tentando de novo em %.0fs: %s",
                    tentativa,
                    tentativas,
                    espera,
                    exc,
                )
                time.sleep(espera)

    raise ultimo_erro


PROMPT_SISTEMA = """\
Voce e um assistente especializado em extrair dados estruturados de Ordens \
de Compra (OC) emitidas por hospitais para uma distribuidora de produtos \
para saude (OPME).

Cada OC pode vir em um layout visual diferente (o texto abaixo foi extraido \
de um PDF e pode ter espacamento ou quebras de linha irregulares). Sua \
tarefa e ler o texto e devolver APENAS um objeto JSON, sem nenhum texto \
adicional, correspondendo exatamente a este schema:

{schema_json}

Regras importantes:
- numero_oc: numero do pedido/ordem de compra, sem prefixos como "No" ou "#".
- data_emissao: formato ISO (AAAA-MM-DD). Se so houver dia/mes/ano no \
formato brasileiro (DD/MM/AAAA), converta.
- cliente: o hospital que EMITIU a ordem de compra (comprador).
- fornecedor: a empresa que vai FORNECER os produtos (geralmente MDR ou \
Mederi, varia o CNPJ conforme a filial).
- itens: um item por produto listado, com quantidade e valores numericos \
(use ponto como separador decimal, nunca virgula).
- dados_clinicos: preencha somente se houver informacao de paciente, \
convenio, cirurgiao, etc no campo de observacao. Caso contrario, omita ou \
use null nos campos.
- tipo_faturamento: extraia a instrucao comercial de faturamento quando \
presente no campo de observacao, por exemplo "FATURAR E REPOR" ou \
"FATURAR". Nao e dado clinico, e informacao logistica/comercial (indica se \
o pedido e reposicao de estoque consignado ou faturamento simples). Use \
null se essa instrucao nao aparecer no texto.
- Nomes de solicitante/aprovador da OC (pessoa do hospital que solicitou ou \
aprovou o pedido) nao fazem parte do schema e devem ser ignorados.
- layout_origem: classifique como "hospital_classico", "totvs_tabela", \
"mv2000", "grade_hospitalar" ou "desconhecido", conforme as pistas visuais \
do texto (ex: cabecalho "MV 2000", rodape TOTVS, tabela com bordas, etc).
- confianca_extracao: calcule seguindo este criterio objetivo, nao uma \
impressao geral:
  * 0.90 a 1.00: todos os campos obrigatorios (numero_oc, cliente, \
fornecedor, e cada item com descricao/quantidade/valor) foram encontrados \
de forma explicita e sem ambiguidade no texto, o layout foi claramente \
reconhecido, e nenhum valor precisou ser inferido ou calculado \
indiretamente.
  * 0.70 a 0.89: os campos obrigatorios foram encontrados, mas algum campo \
opcional (tipo_faturamento, dados_clinicos) ficou ambiguo ou parcialmente \
ilegivel, ou o texto tinha pequenos sinais de desalinhamento (colunas de \
tabela misturadas) que exigiram uma inferencia pequena.
  * 0.50 a 0.69: pelo menos um campo obrigatorio foi obtido de forma \
indireta (por exemplo, quantidade ou valor unitario tiveram que ser \
calculados a partir de outros numeros porque nao apareciam explicitos), ou \
o layout nao bateu claramente com nenhum dos padroes conhecidos.
  * abaixo de 0.50: um ou mais campos obrigatorios estao ausentes, \
ilegiveis, ou o texto extraido do PDF parece corrompido ou incompleto \
(muitos caracteres estranhos, texto cortado no meio).
- Se um campo nao existir no texto, use null (nunca invente valores).

Responda SOMENTE com o JSON, sem explicacoes, sem markdown, sem crases.
"""


class ExtractionError(Exception):
    """Erro ao extrair ou validar dados estruturados a partir do texto da OC."""


def _client() -> OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ExtractionError(
            "OPENROUTER_API_KEY nao configurada. Defina a variavel de ambiente "
            "(ou .env) para rodar a extracao real via OpenRouter."
        )
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)


def _schema_json() -> str:
    return json.dumps(OrdemDeCompra.model_json_schema(), ensure_ascii=False, indent=2)


def _limpar_resposta_json(texto: str) -> str:
    """Remove cercas de codigo markdown que o modelo eventualmente inclua."""

    texto = texto.strip()
    if texto.startswith("```"):
        linhas = texto.splitlines()
        linhas = linhas[1:]
        if linhas and linhas[-1].strip().startswith("```"):
            linhas = linhas[:-1]
        texto = "\n".join(linhas)
    return texto.strip()


def extrair_ordem_de_compra(
    texto_oc: str,
    arquivo_origem: str | None = None,
    modelo: str | None = None,
) -> OrdemDeCompra:
    """Envia o texto bruto de uma OC ao modelo (via OpenRouter) e retorna um
    OrdemDeCompra validado. O modelo usado e o de modelo_configurado()
    (OPENROUTER_MODEL no .env), a menos que outro seja passado explicitamente."""

    modelo = modelo or modelo_configurado()
    client = _client()

    resposta = _retry_com_backoff(
        lambda: client.chat.completions.create(
            model=modelo,
            max_tokens=4096,
            extra_headers={"X-Title": "oc-agent-automation"},
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA.format(schema_json=_schema_json())},
                {"role": "user", "content": texto_oc},
            ],
        )
    )

    bloco_texto = resposta.choices[0].message.content or ""
    json_bruto = _limpar_resposta_json(bloco_texto)

    try:
        dados = json.loads(json_bruto)
    except json.JSONDecodeError as exc:
        raise ExtractionError(
            f"Resposta do modelo nao e JSON valido para {arquivo_origem}: {exc}\n"
            f"Resposta bruta: {json_bruto[:500]}"
        ) from exc

    if arquivo_origem:
        dados["arquivo_origem"] = arquivo_origem

    try:
        return OrdemDeCompra.model_validate(dados)
    except ValidationError as exc:
        raise ExtractionError(
            f"JSON retornado pelo modelo nao corresponde ao schema para {arquivo_origem}: {exc}"
        ) from exc
