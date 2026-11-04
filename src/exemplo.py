"""Ferramenta de exemplo: conta dias úteis entre duas datas.

Serve para mostrar o ciclo (issue, teste, código, PR). Apague este arquivo e o teste
dele (testes/test_exemplo.py) quando a primeira ferramenta de verdade entrar, e tire
os dois do map.md.
"""

from datetime import date, timedelta


def dias_uteis_entre(inicio: date, fim: date) -> int:
    """Quantos dias de segunda a sexta há depois de `inicio` até `fim`, contando `fim`.

    Feriados não entram na conta.
    """
    if fim < inicio:
        raise ValueError("A data final vem antes da inicial.")
    dias = 0
    dia = inicio
    while dia < fim:
        dia += timedelta(days=1)
        if dia.weekday() < 5:  # 0 = segunda ... 4 = sexta
            dias += 1
    return dias
