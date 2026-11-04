"""Testes da ferramenta de exemplo.

Cada teste nasce do "Quando está pronta" da issue, antes do código (TDD).
"""

from datetime import date

import pytest

from exemplo import dias_uteis_entre


def test_de_sexta_para_segunda_conta_um_dia_util():
    assert dias_uteis_entre(date(2026, 11, 6), date(2026, 11, 9)) == 1


def test_mesmo_dia_conta_zero():
    assert dias_uteis_entre(date(2026, 11, 4), date(2026, 11, 4)) == 0


def test_data_final_antes_da_inicial_da_erro():
    with pytest.raises(ValueError):
        dias_uteis_entre(date(2026, 11, 9), date(2026, 11, 6))
