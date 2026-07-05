"""
Modelos Pydantic para a saida estruturada da extracao de Ordens de Compra (OC).

Estes modelos definem o contrato entre o LLM (llm_extractor.py) e o banco de
dados (database.py): qualquer PDF, independente do layout de origem, deve ser
normalizado para esta mesma estrutura.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LayoutOrigem(str, Enum):
    HOSPITAL_CLASSICO = "hospital_classico"
    TOTVS_TABELA = "totvs_tabela"
    MV2000 = "mv2000"
    GRADE_HOSPITALAR = "grade_hospitalar"
    DESCONHECIDO = "desconhecido"


class Cliente(BaseModel):
    nome: str
    cnpj: Optional[str] = None
    cidade: Optional[str] = None
    uf: Optional[str] = None


class Fornecedor(BaseModel):
    nome: str
    cnpj: Optional[str] = None


class ItemOC(BaseModel):
    codigo_produto: Optional[str] = None
    descricao: str
    quantidade: float
    unidade: Optional[str] = None
    valor_unitario: float
    valor_total: float
    lote: Optional[str] = None
    referencia: Optional[str] = None


class DadosClinicos(BaseModel):
    """
    Dados de saude do paciente extraidos do campo de observacao da OC.

    Tabela separada e sinalizada como sensivel (LGPD) - nunca deve ser
    exposta nos relatorios comerciais/financeiros nem exportada junto com
    dados agregados de faturamento.
    """

    paciente: Optional[str] = None
    convenio: Optional[str] = None
    carteirinha: Optional[str] = None
    cirurgiao: Optional[str] = None
    data_realizacao: Optional[date] = None
    aviso_cirurgia: Optional[str] = None
    setor: Optional[str] = None


class OrdemDeCompra(BaseModel):
    """Saida completa e validada da extracao de um PDF de OC."""

    numero_oc: str
    data_emissao: Optional[date] = None
    cliente: Cliente
    fornecedor: Fornecedor
    itens: list[ItemOC] = Field(default_factory=list)
    condicao_pagamento_dias: Optional[int] = None
    valor_frete: Optional[float] = None
    valor_total: Optional[float] = None
    tipo_faturamento: Optional[str] = Field(
        default=None,
        description=(
            "Instrucao comercial de faturamento extraida da observacao da OC, quando "
            "presente (ex: 'FATURAR E REPOR', 'FATURAR'). Nao e dado clinico."
        ),
    )
    dados_clinicos: Optional[DadosClinicos] = None

    layout_origem: LayoutOrigem = LayoutOrigem.DESCONHECIDO
    arquivo_origem: Optional[str] = None
    confianca_extracao: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Confianca do LLM na extracao (0 a 1)."
    )
