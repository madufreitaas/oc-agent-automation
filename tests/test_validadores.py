from validadores import cnpj_valido


def test_cnpj_valido_aceita_cnpj_correto_formatado():
    assert cnpj_valido("11.222.333/0000-09") is True


def test_cnpj_valido_aceita_cnpj_correto_so_digitos():
    assert cnpj_valido("11222333000009") is True


def test_cnpj_valido_rejeita_digito_verificador_errado():
    assert cnpj_valido("11.222.333/0000-10") is False


def test_cnpj_valido_rejeita_quantidade_errada_de_digitos():
    assert cnpj_valido("123") is False


def test_cnpj_valido_rejeita_sequencia_repetida():
    assert cnpj_valido("00.000.000/0000-00") is False
    assert cnpj_valido("11.111.111/1111-11") is False


def test_cnpj_valido_aceita_none_e_vazio():
    # ausencia de CNPJ nao e a mesma coisa que CNPJ invalido
    assert cnpj_valido(None) is True
    assert cnpj_valido("") is True
