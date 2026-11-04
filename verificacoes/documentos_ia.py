"""Confere os documentos de IA do repositório.

1. CLAUDE.md e memory.md dentro do limite de palavras.
2. historico.md com títulos datados (## AAAA-MM-DD), o mais recente no topo.
3. "Última atualização" do checklist com data válida, sem data futura e não
   anterior à entrada mais recente do histórico.
4. map.md completo nos dois sentidos: tudo que está no repositório aparece no
   mapa, e tudo que está no mapa existe.
5. Toda pasta tem um LEIA-ME.md (pastas que começam com ponto, como .github/, ficam de fora).

Uso: python verificacoes/documentos_ia.py
"""

import re
import sys
from datetime import date, timedelta
from fnmatch import fnmatchcase

from comum import RAIZ, arquivos_do_repositorio, ler_texto, mostrar, pastas_do_repositorio

# Limite de palavras de cada arquivo. Para mudar um limite, mude aqui e registre em decisoes.md.
LIMITES_DE_PALAVRAS = {"CLAUDE.md": 1500, "memory.md": 600}

# Dias de folga para "data futura": o servidor do GitHub pode estar num fuso à frente do seu.
FOLGA_DE_DIAS = 1

ARQUIVOS_OBRIGATORIOS = [
    "CLAUDE.md",
    "memory.md",
    "map.md",
    "historico.md",
    "decisoes.md",
    "Checklist_Projeto.md",
    "Backlog_Melhorias.md",
]


def contar_palavras(texto):
    """Conta palavras separadas por espaço ou quebra de linha."""
    return len(texto.split())


def verificar_obrigatorios(raiz):
    erros = []
    for nome in ARQUIVOS_OBRIGATORIOS:
        if ler_texto(raiz, nome) is None:
            erros.append(f"{nome} não existe. O que fazer: crie o arquivo na raiz do repositório.")
    return erros


def verificar_limites(raiz):
    erros = []
    for nome, limite in LIMITES_DE_PALAVRAS.items():
        texto = ler_texto(raiz, nome)
        if texto is None:
            continue
        palavras = contar_palavras(texto)
        if palavras > limite:
            erros.append(
                f"{nome} tem {palavras} palavras; o limite é {limite}. "
                f"O que fazer: mova o detalhe para o arquivo certo (andamento no checklist, "
                f"porquê no decisoes.md, o que foi feito no historico.md) até ficar com {limite} ou menos."
            )
    return erros


def ler_data(texto):
    """Converte 'AAAA-MM-DD' em data. Devolve None se a data não existe (ex.: 2026-02-30)."""
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def verificar_historico(raiz, hoje):
    """Devolve (erros, data mais recente do histórico)."""
    texto = ler_texto(raiz, "historico.md")
    if texto is None:
        return [], None
    erros = []
    datas = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        if not linha.startswith("## "):
            continue
        achado = re.match(r"## (\d{4}-\d{2}-\d{2})\b", linha)
        data = ler_data(achado.group(1)) if achado else None
        if data is None:
            erros.append(
                f"historico.md, linha {numero}: o título \"{linha}\" não começa com uma data válida. "
                f"O que fazer: use o formato ## AAAA-MM-DD, por exemplo ## 2026-11-04."
            )
            continue
        if data > hoje + timedelta(days=FOLGA_DE_DIAS):
            erros.append(
                f"historico.md, linha {numero}: a data {data} está no futuro. "
                f"O que fazer: use a data do dia em que o trabalho foi feito."
            )
        if datas and data == datas[-1]:
            erros.append(
                f"historico.md, linha {numero}: a data {data} aparece duas vezes. "
                f"O que fazer: junte as duas entradas numa só, sob um único título."
            )
        elif datas and data > datas[-1]:
            erros.append(
                f"historico.md, linha {numero}: a data {data} está abaixo de {datas[-1]}, que é mais antiga. "
                f"O que fazer: a entrada mais recente fica no topo; mova esta entrada para cima."
            )
        datas.append(data)
    if not datas:
        erros.append(
            "historico.md não tem nenhuma entrada datada. "
            "O que fazer: acrescente no topo um título ## AAAA-MM-DD com o que foi feito."
        )
    return erros, (max(datas) if datas else None)


def verificar_checklist(raiz, hoje, ultima_do_historico):
    texto = ler_texto(raiz, "Checklist_Projeto.md")
    if texto is None:
        return []
    achado = re.search(r"\*\*Última atualização:\*\*\s*(\S+)", texto)
    if not achado:
        return [
            "Checklist_Projeto.md não tem a linha **Última atualização:** AAAA-MM-DD. "
            "O que fazer: acrescente essa linha logo abaixo do título."
        ]
    data = ler_data(achado.group(1))
    if data is None:
        return [
            f"Checklist_Projeto.md: \"{achado.group(1)}\" não é uma data válida em **Última atualização:**. "
            f"O que fazer: use o formato AAAA-MM-DD, por exemplo 2026-11-04."
        ]
    if data > hoje + timedelta(days=FOLGA_DE_DIAS):
        return [
            f"Checklist_Projeto.md: a última atualização ({data}) está no futuro. "
            f"O que fazer: use a data de hoje."
        ]
    if ultima_do_historico and data < ultima_do_historico:
        return [
            f"Checklist_Projeto.md: a última atualização ({data}) é anterior à entrada mais recente "
            f"do historico.md ({ultima_do_historico}). O que fazer: confira o checklist, marque o que "
            f"foi resolvido e atualize a data."
        ]
    return []


def itens_do_mapa(texto):
    """Lê os caminhos listados no map.md.

    Um item é um caminho entre crases:
    - numa linha de lista ("- `caminho` — descrição"), antes do travessão;
    - numa linha de tabela ("| `caminho` | descrição |"), na primeira coluna.
    O que vem depois do travessão (ou nas outras colunas) é descrição e não é conferido.
    """
    itens = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        linha = linha.strip()
        if linha.startswith("|"):
            trecho = linha.strip("|").split("|")[0]
        elif linha.startswith("- "):
            trecho = linha[2:].split(" — ")[0]
        else:
            continue
        for caminho in re.findall(r"`([^`]+)`", trecho):
            itens.append((numero, caminho.strip().removeprefix("./")))
    return itens


def casa_com_padrao(caminho, padrao):
    """Diz se um caminho combina com um item com coringa (*), pasta por pasta.

    Exemplo: "src/*.py" combina com "src/exemplo.py", mas não com "src/util/exemplo.py".
    """
    partes_caminho = caminho.rstrip("/").split("/")
    partes_padrao = padrao.rstrip("/").split("/")
    if len(partes_caminho) != len(partes_padrao):
        return False
    return all(fnmatchcase(c, p) for c, p in zip(partes_caminho, partes_padrao))


def verificar_mapa(raiz, arquivos, pastas):
    texto = ler_texto(raiz, "map.md")
    if texto is None:
        return []
    erros = []
    itens = itens_do_mapa(texto)
    nomes = {item for _, item in itens}
    padroes = [item for item in nomes if "*" in item]

    # Sentido 1: tudo que está no mapa existe.
    for numero, item in itens:
        if "*" in item:
            existe = any(casa_com_padrao(c, item) for c in arquivos + pastas)
        elif item.endswith("/"):
            existe = item in pastas
        else:
            existe = item in arquivos
        if not existe:
            erros.append(
                f"map.md, linha {numero}: `{item}` está no mapa mas não existe no repositório. "
                f"O que fazer: corrija o caminho ou tire a linha do mapa."
            )

    # Sentido 2: tudo que está no repositório aparece no mapa.
    for pasta in pastas:
        if pasta not in nomes:
            erros.append(
                f"A pasta `{pasta}` não aparece no map.md. "
                f"O que fazer: acrescente uma linha \"- `{pasta}` — para que serve\"."
            )
    for arquivo in arquivos:
        listado = arquivo in nomes or any(casa_com_padrao(arquivo, p) for p in padroes)
        if not listado:
            erros.append(
                f"O arquivo `{arquivo}` não aparece no map.md. "
                f"O que fazer: acrescente uma linha \"- `{arquivo}` — o que é\" "
                f"(ou um item com coringa, como `pasta/*.py`)."
            )
    return erros


def verificar_leia_me(arquivos, pastas):
    erros = []
    for pasta in pastas:
        if any(parte.startswith(".") for parte in pasta.split("/") if parte):
            continue
        if f"{pasta}LEIA-ME.md" not in arquivos:
            erros.append(
                f"A pasta `{pasta}` não tem LEIA-ME.md. "
                f"O que fazer: crie `{pasta}LEIA-ME.md` dizendo para que serve a pasta e o que entra nela."
            )
    return erros


def verificar(raiz, hoje=None):
    hoje = hoje or date.today()
    arquivos = arquivos_do_repositorio(raiz)
    pastas = pastas_do_repositorio(arquivos)
    erros = verificar_obrigatorios(raiz)
    erros += verificar_limites(raiz)
    erros_historico, ultima = verificar_historico(raiz, hoje)
    erros += erros_historico
    erros += verificar_checklist(raiz, hoje, ultima)
    erros += verificar_mapa(raiz, arquivos, pastas)
    erros += verificar_leia_me(arquivos, pastas)
    return erros


if __name__ == "__main__":
    sys.exit(mostrar("Documentos de IA", verificar(RAIZ)))
