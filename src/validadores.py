"""
Validadores deterministicos, independentes do LLM.

Servem de segunda camada de verificacao sobre o que o modelo extraiu: um
CNPJ com digito verificador errado e um sinal forte de erro de extracao
(ou de um dado realmente invalido no documento original), que um algoritmo
simples consegue detectar sem nenhuma ambiguidade, ao contrario dos demais
alertas do projeto (duplicidade, divergencia de valor, baixa confianca),
que dependem de julgamento.
"""

from __future__ import annotations

import re


def cnpj_valido(cnpj: str | None) -> bool:
    """Confere o digito verificador de um CNPJ (formato XX.XXX.XXX/XXXX-XX
    ou so os 14 digitos). Retorna True se o CNPJ for None ou vazio (ausencia
    de CNPJ nao e a mesma coisa que CNPJ invalido - ver alerta_cnpj_invalido
    em database.py, que so sinaliza quando ha um CNPJ e ele falha aqui)."""

    if not cnpj:
        return True

    digitos = re.sub(r"\D", "", cnpj)
    if len(digitos) != 14:
        return False
    if digitos == digitos[0] * 14:
        return False

    def _digito_verificador(base: str, pesos: list[int]) -> str:
        soma = sum(int(digito) * peso for digito, peso in zip(base, pesos))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    digito_1 = _digito_verificador(digitos[:12], pesos_1)
    digito_2 = _digito_verificador(digitos[:12] + digito_1, pesos_2)

    return digitos[12:] == digito_1 + digito_2
