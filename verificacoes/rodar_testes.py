"""Testes automáticos: confere que o código tem teste e roda os testes com o pytest.

O repositório trabalha com teste primeiro (TDD): cada ferramenta em src/ tem um teste
em testes/, escrito a partir do "Quando está pronta" da issue.
As pastas de teste ficam em pyproject.toml, na seção [tool.pytest.ini_options].

Uso: python verificacoes/rodar_testes.py
"""

import subprocess
import sys
from pathlib import Path

from comum import RAIZ, arquivos_do_repositorio, mostrar

# Código de saída do pytest quando não encontra nenhum teste.
NENHUM_TESTE = 5


def falta_teste(arquivos):
    """Erro se existe código em src/ e nenhum arquivo de teste em testes/."""
    codigo = [
        a for a in arquivos
        if a.startswith("src/") and a.endswith(".py") and Path(a).name != "__init__.py"
    ]
    testes = [
        a for a in arquivos
        if a.startswith("testes/") and Path(a).name.startswith("test_") and a.endswith(".py")
    ]
    if codigo and not testes:
        return [
            f"Há código em src/ ({len(codigo)} arquivo(s)) e nenhum teste em testes/. "
            f"O que fazer: peça ao Claude o teste de cada ferramenta, a partir do "
            f"\"Quando está pronta\" do chamado (issue), num arquivo testes/test_<nome>.py."
        ]
    return []


def verificar(raiz):
    erros = falta_teste(arquivos_do_repositorio(raiz))
    try:
        resultado = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=raiz,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as erro:
        return erros + [f"Não consegui rodar o pytest ({erro})."]
    if "No module named pytest" in resultado.stderr:
        return erros + ["O pytest não está instalado. O que fazer: rode pip install -r requirements-dev.txt"]
    if resultado.returncode not in (0, NENHUM_TESTE):
        ultimas_linhas = "\n    ".join(resultado.stdout.strip().splitlines()[-15:])
        erros.append(
            "Algum teste falhou. Resumo do pytest (em inglês):\n    "
            + ultimas_linhas
            + "\n  O que fazer: peça ao Claude \"rode os testes e corrija o que falhou\". "
            "Se o teste está certo, quem muda é o código, não o teste."
        )
    return erros


if __name__ == "__main__":
    sys.exit(mostrar("Testes automáticos", verificar(RAIZ)))
