"""Roda todas as verificações, na mesma ordem do GitHub.

Rode antes de enviar para a nuvem (push). Tudo OK aqui = conferência automática (CI) verde no GitHub.

Uso: python verificacoes/verificar_tudo.py
"""

import os
import subprocess
import sys

import documentos_ia
import rodar_lint
import rodar_testes
import segredos
from comum import RAIZ, mostrar

ETAPAS = [
    ("Documentos de IA", documentos_ia.verificar),
    ("Segredos e arquivos proibidos", segredos.verificar),
    ("Lint do Python", rodar_lint.verificar),
    ("Testes automáticos", rodar_testes.verificar),
]


def barreira_local_ligada():
    """Confere se o git deste computador usa a barreira local (.githooks/pre-commit)."""
    resultado = subprocess.run(
        ["git", "config", "core.hooksPath"],
        cwd=RAIZ,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return resultado.stdout.strip() == ".githooks"


def main():
    # No GitHub (CI) não há commit local; no seu computador, a barreira precisa estar ligada.
    if not os.environ.get("CI") and not barreira_local_ligada():
        print(
            "AVISO - as travas do computador (hooks) estão desligadas.\n"
            "  O que fazer: rode git config core.hooksPath .githooks na pasta do repositório.\n"
        )
    falhas = 0
    for titulo, verificar in ETAPAS:
        falhas += mostrar(titulo, verificar(RAIZ))
    print()
    if falhas:
        print(f"RESULTADO: {falhas} de {len(ETAPAS)} verificações com problema. Corrija antes de enviar para a nuvem (push).")
        return 1
    print("RESULTADO: tudo certo. Pode enviar para a nuvem (push).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
