"""Lint do Python: procura erros de escrita no código com o ruff.

O ruff responde em inglês. Este script traduz os erros mais comuns e diz o que fazer.
As regras ficam em pyproject.toml, na seção [tool.ruff].

Uso: python verificacoes/rodar_lint.py
"""

import re
import subprocess
import sys

from comum import RAIZ, mostrar

# Tradução dos erros mais comuns do ruff. Erro fora da lista aparece em inglês, como o ruff escreveu.
TRADUCOES = {
    "F401": "import que não é usado; apague o import",
    "F811": "nome definido duas vezes; apague ou renomeie um deles",
    "F821": "nome usado sem ter sido definido (erro de digitação ou import faltando)",
    "F841": "variável criada e nunca usada; apague ou use a variável",
    "F541": "f-string sem nada para preencher; tire o f da frente",
    "E402": "import fora do topo do arquivo; leve o import para o começo",
    "E711": "comparação com None; use 'is None' ou 'is not None'",
    "E712": "comparação com True ou False; use o valor direto (if x:)",
    "E722": "'except:' sem o tipo do erro; diga qual erro espera (ex.: except ValueError:)",
    "E741": "nome de variável ambíguo (l, O ou I); use um nome que diga o que é",
}

DICA_FINAL = (
    "O que fazer: peça ao Claude \"corrija os erros do lint\". Muitos se corrigem sozinhos com "
    "python -m ruff check --fix ."
)


def verificar(raiz):
    try:
        resultado = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--output-format", "concise", "--no-cache", "."],
            cwd=raiz,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as erro:
        return [f"Não consegui rodar o ruff ({erro})."]
    if "No module named ruff" in resultado.stderr:
        return ["O ruff não está instalado. O que fazer: rode pip install -r requirements-dev.txt"]
    if resultado.returncode == 0:
        return []

    erros = []
    for linha in resultado.stdout.splitlines():
        # Formato do ruff: arquivo:linha:coluna: CÓDIGO mensagem
        achado = re.match(r"^(.+?):(\d+):\d+: (\S+) (.*)$", linha)
        if not achado:
            continue
        arquivo, numero, codigo, mensagem = achado.groups()
        explicacao = TRADUCOES.get(codigo, mensagem.replace("[*] ", ""))
        erros.append(f"{arquivo.replace(chr(92), '/')}, linha {numero}: {explicacao} [{codigo}]")
    if not erros:
        erros.append((resultado.stdout + resultado.stderr).strip())
    erros.append(DICA_FINAL)
    return erros


if __name__ == "__main__":
    sys.exit(mostrar("Lint do Python", verificar(RAIZ)))
