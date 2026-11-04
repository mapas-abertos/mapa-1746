"""Funções usadas por todas as verificações.

Cada verificação devolve uma lista de erros em português. Lista vazia = tudo certo.
"""

import subprocess
import sys
from pathlib import Path

# Mensagens sempre em UTF-8, para os acentos saírem certos em qualquer terminal.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Pasta raiz do repositório (a pasta acima de verificacoes/).
RAIZ = Path(__file__).resolve().parent.parent


def arquivos_do_repositorio(raiz):
    """Lista os arquivos que o git leva para o GitHub: os já salvos e os novos.

    Os arquivos ignorados pelo .gitignore (como .env e dados/) ficam de fora.
    Os caminhos usam / como separador, igual ao GitHub.
    """
    try:
        resultado = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=raiz,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit(
            "ERRO: esta pasta não é um repositório git, ou o git não está instalado.\n"
            "O que fazer: rode as verificações de dentro da pasta do repositório."
        )
    caminhos = resultado.stdout.decode("utf-8").split("\0")
    # Um arquivo apagado mas ainda não salvo no git aparece na lista; ele é descartado aqui.
    return sorted({c for c in caminhos if c and (Path(raiz) / c).is_file()})


def pastas_do_repositorio(arquivos):
    """Lista as pastas que contêm os arquivos, terminadas em / (ex.: "src/", "src/util/")."""
    pastas = set()
    for arquivo in arquivos:
        partes = arquivo.split("/")[:-1]
        for i in range(1, len(partes) + 1):
            pastas.add("/".join(partes[:i]) + "/")
    return sorted(pastas)


def ler_texto(raiz, caminho):
    """Lê um arquivo de texto em UTF-8. Devolve None se o arquivo não existe."""
    arquivo = Path(raiz) / caminho
    if not arquivo.is_file():
        return None
    return arquivo.read_text(encoding="utf-8", errors="replace")


def mostrar(titulo, erros):
    """Mostra o resultado de uma verificação e devolve o código de saída (0 = passou)."""
    if not erros:
        print(f"OK - {titulo}: nenhum problema.")
        return 0
    print(f"ERRO - {titulo}: {len(erros)} problema(s).\n")
    for erro in erros:
        print(f"  * {erro}\n")
    return 1
