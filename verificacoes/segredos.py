"""Barreira contra segredos e arquivos que não podem ir para o GitHub.

Confere todos os arquivos que o git levaria para o GitHub (os ignorados pelo
.gitignore ficam de fora) e barra:
1. arquivos de segredo: .env, chaves e certificados;
2. arquivos de dados (planilhas, documentos, bancos) fora de _referencias/;
3. arquivos grandes demais;
4. senhas, tokens e chaves escritos dentro dos arquivos.

Alarme falso? Escreva nao-e-segredo num comentário na mesma linha e explique no PR.

Uso: python verificacoes/segredos.py
"""

import re
import sys
from pathlib import Path

from comum import RAIZ, arquivos_do_repositorio, mostrar

# ---- Ajuste aqui as regras do seu repositório (e registre a mudança em decisoes.md) ----

# Arquivos de dados só podem entrar nesta pasta (originais que explicam de onde veio o trabalho).
PASTA_DOS_ORIGINAIS = "_referencias/"

# Tamanho máximo de um arquivo, em megabytes.
TAMANHO_MAXIMO_MB = 5

# Arquivos de segredo: nunca entram, em pasta nenhuma.
NOMES_DE_SEGREDO = {".env", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
EXTENSOES_DE_SEGREDO = {".pem", ".key", ".pfx", ".p12", ".ppk", ".jks", ".keystore"}

# Arquivos de dados: só entram em PASTA_DOS_ORIGINAIS.
EXTENSOES_DE_DADOS = {
    ".xlsx", ".xlsm", ".xls", ".csv",  # planilhas
    ".docx", ".doc", ".pdf",  # documentos
    ".db", ".sqlite", ".sqlite3", ".bak",  # bancos e backups
}

# Textos que parecem segredo dentro de um arquivo: (o que é, padrão).
PADROES_DE_SEGREDO = [
    ("token do GitHub", r"\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    ("chave da Anthropic (Claude)", r"\bsk-ant-[A-Za-z0-9_\-]{20,}"),
    ("chave da OpenAI", r"\bsk-(proj-)?[A-Za-z0-9]{20,}"),
    ("chave da AWS", r"\bAKIA[0-9A-Z]{16}\b"),
    ("chave privada", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    (
        "senha ou chave escrita no código",
        r"(?i)\b(senha|password|passwd|secret|segredo|token|api_key|apikey|chave)\b"
        r"\s*[:=]\s*[\"'][^\"'\s]{6,}[\"']",
    ),
]

# Palavra que libera uma linha (alarme falso).
LIBERA_LINHA = "nao-e-segredo"

# ---------------------------------------------------------------------------------------

COMO_TIRAR = (
    "Se o arquivo já foi enviado ao GitHub, tirá-lo não basta: troque a senha ou a chave "
    "no serviço de origem (ver docs/segredos_no_github.md)."
)


def e_arquivo_de_segredo(caminho):
    nome = Path(caminho).name
    if nome == ".env.example":
        return False
    return (
        nome in NOMES_DE_SEGREDO
        or nome.startswith(".env.")
        or Path(nome).suffix.lower() in EXTENSOES_DE_SEGREDO
    )


def e_arquivo_de_dados(caminho):
    return Path(caminho).suffix.lower() in EXTENSOES_DE_DADOS


def parece_binario(conteudo):
    """Arquivo com byte zero no começo é binário (imagem, planilha); não dá para ler como texto."""
    return b"\0" in conteudo[:8000]


def procurar_segredos(caminho, texto):
    erros = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        if LIBERA_LINHA in linha:
            continue
        for descricao, padrao in PADROES_DE_SEGREDO:
            if re.search(padrao, linha):
                erros.append(
                    f"{caminho}, linha {numero}: parece ter um(a) {descricao}. "
                    f"O que fazer: tire o valor do arquivo, guarde no .env (no seu computador) "
                    f"ou nos Secrets do GitHub e leia com os.environ. {COMO_TIRAR}"
                )
                break
    return erros


def verificar(raiz):
    erros = []
    limite_em_bytes = TAMANHO_MAXIMO_MB * 1024 * 1024
    for caminho in arquivos_do_repositorio(raiz):
        if e_arquivo_de_segredo(caminho):
            erros.append(
                f"{caminho}: arquivo de segredo (senha, chave ou certificado) não pode ir para o GitHub. "
                f"O que fazer: tire o arquivo do repositório e confira se o .gitignore cobre esse nome. "
                f"{COMO_TIRAR}"
            )
            continue
        if e_arquivo_de_dados(caminho) and not caminho.startswith(PASTA_DOS_ORIGINAIS):
            erros.append(
                f"{caminho}: arquivo de dados fora de {PASTA_DOS_ORIGINAIS}. "
                f"O que fazer: se é um original que explica de onde veio o trabalho e pode ir para "
                f"o GitHub, mova para {PASTA_DOS_ORIGINAIS}; se não pode ir, mova para dados/ "
                f"(que fica só no seu computador)."
            )
            continue
        arquivo = Path(raiz) / caminho
        if arquivo.stat().st_size > limite_em_bytes:
            tamanho = arquivo.stat().st_size / (1024 * 1024)
            erros.append(
                f"{caminho}: tem {tamanho:.1f} MB; o limite é {TAMANHO_MAXIMO_MB} MB. "
                f"O que fazer: guarde o arquivo fora do repositório (em dados/) e, se for um original, "
                f"registre no LEIA-ME de {PASTA_DOS_ORIGINAIS} onde ele está."
            )
            continue
        conteudo = arquivo.read_bytes()
        if parece_binario(conteudo):
            continue
        erros += procurar_segredos(caminho, conteudo.decode("utf-8", errors="replace"))
    return erros


if __name__ == "__main__":
    sys.exit(mostrar("Segredos e arquivos proibidos", verificar(RAIZ)))
