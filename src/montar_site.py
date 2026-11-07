"""Montador do site do mapa: quadrados de 100 m coloridos, filtros, tabelas e método.

Pedido nas issues #16 e #31. Lê, de uma pasta, as quatro saídas do agregador (ou da coleta,
que grava o mesmo formato): quadrados.geojson, quadrados.csv, ruas.csv e resumo.txt. Grava, em
outra pasta, o site pronto: um mapa (index.html), a página de método e fonte (metodo.html) e
as duas tabelas para baixar. Só essas saídas entram: nenhum outro arquivo da pasta de entrada
vai para o site, e nada traz chamado individual, coordenada de chamado ou identificador.

Filtros (issue #31): se a pasta de entrada tem a pasta filtros/ da coleta, o mapa ganha o
painel de filtros. As fatias são conferidas (só números inteiros, nas colunas esperadas) e vão
para a pasta filtros/ do site; o navegador busca só as que o filtro pede. Os filtros mudam só
o mapa: as tabelas para baixar são sempre os totais sem filtro. Sem a pasta filtros/ (saída
do agregador), o site abre sem o painel.

Os totais sem filtro vão num arquivo .js (dados.js). Para ver o mapa de fundo e usar os
filtros, sirva a pasta por http (o OpenStreetMap bloqueia o pedido de uma página aberta do
disco, com duplo clique, porque ela não diz de que site vem). Só o mapa de fundo e a
biblioteca Leaflet vêm de fora do site.

Uso, a partir da raiz do repositório:

    .venv/Scripts/python src/montar_site.py dados/saida --saida dados/site
    Com o nome da versão publicada: --versao v2026.11.06 (a entrega automática passa)
    Para ver as opções: --ajuda

Depois, sirva a pasta e abra o endereço no navegador:

    .venv/Scripts/python -m http.server 8765 --bind 127.0.0.1 -d dados/site
    http://127.0.0.1:8765
"""

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

# ---- Regras do site (mudou uma? registre em decisoes.md) -------------------------------

# Caixa que mostra o município do Rio de Janeiro inteiro: [[sul, oeste], [norte, leste]].
LIMITES_DO_RIO = [[-23.08, -43.80], [-22.74, -43.09]]

# Classes de cor pelo total de chamados do quadrado, da mais clara à mais escura.
# (limite de baixo da classe, cor). A classe vai até o limite de baixo da seguinte.
# Escala de um tom só (claro para escuro), legível por quem não distingue cores.
CLASSES = [
    (1, "#fdd49e"),
    (10, "#fdae6b"),
    (50, "#f16913"),
    (200, "#bd0026"),
    (1000, "#67000d"),
]
CORES_DAS_CLASSES = [cor for _, cor in CLASSES]

# O texto da cor, igual na legenda e na página de método (ver a issue #16).
FRASE_DA_COR = (
    "A cor mostra onde se pede mais, e isso acompanha onde há mais gente e mais movimento. "
    "Não mostra onde a Prefeitura atende pior."
)

# Onde está a fonte, a licença do código e a tabela de origem.
TABELA_DE_ORIGEM = "datario.adm_central_atendimento_1746.chamado"
LINK_DATA_RIO = "https://data.rio/"
LINK_DO_CODIGO = "https://github.com/mapas-abertos/mapa-1746"
LINK_DA_LISTA = (
    f"{LINK_DO_CODIGO}/blob/main/"
    "_referencias/20261106_classificacao_subtipos/grupos_subtipos_1746.csv"
)

# Só problema público, por privacidade (issue #26). A linha do resumo da coleta com os que
# entram no mapa e, na ordem da página, cada grupo que fica de fora, com o nome na página.
CAMPO_DO_PROBLEMA_PUBLICO = "chamados de problema público (entram no mapa)"
GRUPOS_FORA_DO_MAPA = [
    ("denuncia", "Denúncia, que pode apontar vizinho, carro, obra, estabelecimento ou imóvel"),
    ("pessoal", "Pedido pessoal, da própria casa ou da pessoa"),
    ("sem_lugar", "Sem lugar (informação, tributo ou documento)"),
    ("a_revisar", "A revisar (subtipos que ainda vão ser classificados)"),
    ("sem classificação", "Subtipo que não está na lista de classificação"),
]

# Biblioteca do mapa por CDN, com a versão fixa. O "integrity" faz o navegador recusar o
# arquivo se ele mudar. Trocar a versão: calcule o hash novo do arquivo e troque os dois.
LEAFLET = "https://unpkg.com/leaflet@1.9.4/dist"
LEAFLET_JS_HASH = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
LEAFLET_CSS_HASH = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="

# O que aparece no clique quando não há o número (a mediana sem fechados, ou com filtro).
TRACO = "—"

# Filtros do mapa (issue #31). A frase vai no painel e na página de método.
FRASE_DO_FILTRO = (
    "Os filtros mudam só o mapa. As tabelas para baixar trazem sempre os totais sem filtro."
)
SITUACAO_ATENDIDO = "Atendido"  # o tipo de situação que conta como atendido (igual à coleta)
VAZIO = "(vazio)"  # como aparece um valor em branco na base

# A nota do prazo: o bloco que a coleta grava no resumo.txt e os dois valores da conta.
CABECALHO_DO_PRAZO = "prazo (dentro_prazo) por situação, entre os chamados de problema público:"
PRAZO_A_VENCER = "A Vencer"
SITUACAO_NAO_ENCERRADO = "Não Encerrado"

# O canto da tela com a versão publicada; no computador, sem --versao, a versão é local.
VERSAO_LOCAL = "Versão: local (não publicada)"

# ---------------------------------------------------------------------------------------

# O que o agregador (e a coleta) gravam. É só isso que o site lê e leva.
ENTRADAS = ("quadrados.geojson", "quadrados.csv", "ruas.csv", "resumo.txt")
TABELAS = ("ruas.csv", "quadrados.csv")
ARQUIVOS_DO_SITE = (
    "index.html", "metodo.html", "estilo.css", "mapa.js", "filtros.js", "dados.js", "ruas.csv",
    "quadrados.csv",
)

# A pasta das fatias dos filtros, como a coleta grava (ver src/coleta.py).
PASTA_DOS_FILTROS = "filtros"
FORMATO_DAS_FATIAS = ["q", "d", "t", "e", "p", "o", "n", "f"]
CHAVES_DO_INDICE = {"formato", "quadrados", "temas", "estados", "prazos", "orgaos", "meses",
                    "anos", "primeiro_dia", "ultimo_dia", "bairros"}

SEPARADOR = ";"


class EntradaInvalida(ValueError):
    """As saídas do agregador não estão como o esperado. A mensagem diz o que fazer."""


# ---- Leitura --------------------------------------------------------------------------


def _ler_resumo(texto):
    """Linhas 'nome: valor' do resumo.txt, com o nome em minúsculas."""
    campos = {}
    for linha in texto.splitlines():
        nome, separador, valor = linha.partition(":")
        if separador:
            campos[nome.strip().lower()] = valor.strip()
    return campos


def _data_do_resumo(campos, *nomes):
    """Data 'AAAA-MM-DD' de um dos campos, em dia/mês/ano; 'a definir' se não houver."""
    for nome in nomes:
        valor = campos.get(nome, "")[:10]
        try:
            return date.fromisoformat(valor).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return "a definir"


def _ler_entradas(pasta):
    pasta = Path(pasta)
    if not pasta.is_dir():
        raise FileNotFoundError(pasta)
    faltam = [nome for nome in ENTRADAS if not (pasta / nome).is_file()]
    if faltam:
        raise EntradaInvalida(
            f"Na pasta de entrada falta: {', '.join(faltam)}. "
            f"O que fazer: rode o agregador (ou a coleta) e use a pasta onde ele gravou "
            f"os quatro arquivos de saída."
        )
    try:
        geojson = json.loads((pasta / "quadrados.geojson").read_text(encoding="utf-8"))
        features = geojson["features"]
    except (ValueError, KeyError, TypeError):
        raise EntradaInvalida(
            "O quadrados.geojson não é um GeoJSON de quadrados válido. "
            "O que fazer: rode de novo o agregador (ou a coleta) para gravá-lo."
        ) from None
    texto_do_resumo = (pasta / "resumo.txt").read_text(encoding="utf-8")
    for nome in TABELAS:
        if "menos de" in (pasta / nome).read_text(encoding="utf-8-sig"):
            raise _erro_do_minimo(nome)
    return features, _ler_resumo(texto_do_resumo), texto_do_resumo


def _erro_do_minimo(nome):
    return EntradaInvalida(
        f"O {nome} ainda tem \"menos de N\", do tempo do mínimo de chamados, que saiu na "
        f"issue #31. Nada do site foi gravado. O que fazer: rode a coleta de novo e use a "
        f"pasta nova."
    )


# ---- Fatias dos filtros (issue #31) ---------------------------------------------------


def _erro_nos_filtros(nome, problema):
    return EntradaInvalida(
        f"A pasta {PASTA_DOS_FILTROS}/ tem um problema em {nome}: {problema}. Nada do site foi "
        f"gravado. O que fazer: rode a coleta de novo e use a pasta nova, com a pasta "
        f"{PASTA_DOS_FILTROS}/ inteira."
    )


def _ler_json(pasta, nome):
    caminho = pasta / nome
    if not caminho.is_file():
        raise _erro_nos_filtros(nome, "o arquivo não está lá")
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except ValueError:
        raise _erro_nos_filtros(nome, "não é um JSON válido") from None


def _textos(valor):
    return isinstance(valor, list) and all(isinstance(item, str) for item in valor)


def _inteiros(valor):
    return isinstance(valor, list) and all(type(item) is int for item in valor)


def _conferir_indice(indice, ids):
    """O índice só pode ter as listas dos filtros, e os quadrados do quadrados.geojson."""
    if not isinstance(indice, dict) or set(indice) != CHAVES_DO_INDICE:
        raise _erro_nos_filtros("indice.json", "as listas não são as esperadas")
    if indice["formato"] != FORMATO_DAS_FATIAS:
        raise _erro_nos_filtros("indice.json", "o formato das fatias não é o esperado")
    quadrados = indice["quadrados"]
    if not _textos(quadrados) or len(set(quadrados)) != len(quadrados) or set(quadrados) != ids:
        raise _erro_nos_filtros("indice.json", "os quadrados não são os do quadrados.geojson")
    if not all(_textos(indice[nome]) for nome in ("temas", "prazos", "orgaos")):
        raise _erro_nos_filtros("indice.json", "uma lista de filtro não é uma lista de textos")
    if not all(_textos(estado) and len(estado) == 3 for estado in indice["estados"]):
        raise _erro_nos_filtros("indice.json", "os estados não são status, situação e tipo")
    meses, anos = indice["meses"], indice["anos"]
    if not (isinstance(meses, list) and all(isinstance(mes, str) and re.fullmatch(r"\d{4}-\d{2}", mes)
                                            for mes in meses)):
        raise _erro_nos_filtros("indice.json", "a lista de meses não está como AAAA-MM")
    if not _inteiros(anos) or sorted({int(mes[:4]) for mes in meses}) != anos:
        raise _erro_nos_filtros("indice.json", "a lista de anos não bate com a de meses")
    for nome in ("primeiro_dia", "ultimo_dia"):
        try:
            date.fromisoformat(indice[nome])
        except (TypeError, ValueError):
            raise _erro_nos_filtros("indice.json", f"o {nome} não é uma data") from None
    bairros = indice["bairros"]
    if not isinstance(bairros, dict) or not all(
        isinstance(caixa, list) and len(caixa) == 4
        and all(isinstance(lado, (int, float)) and not isinstance(lado, bool) for lado in caixa)
        for caixa in bairros.values()
    ):
        raise _erro_nos_filtros("indice.json", "a caixa de um bairro não tem os quatro lados")


def _conferir_fatia(nome, fatia, indice, com_dia):
    """Uma fatia só pode ter colunas de números inteiros, e cada número dentro das listas."""
    colunas = [c for c in FORMATO_DAS_FATIAS if com_dia or c != "d"]
    if not isinstance(fatia, dict) or set(fatia) != set(colunas):
        raise _erro_nos_filtros(nome, f"as colunas não são {', '.join(colunas)}")
    if not all(_inteiros(fatia[coluna]) for coluna in colunas):
        raise _erro_nos_filtros(nome, "há algo que não é número inteiro")
    if len({len(fatia[coluna]) for coluna in colunas}) != 1:
        raise _erro_nos_filtros(nome, "as colunas têm tamanhos diferentes")
    limites = {"t": len(indice["temas"]), "e": len(indice["estados"]),
               "p": len(indice["prazos"]), "o": len(indice["orgaos"])}
    for coluna, limite in limites.items():
        if any(not 0 <= valor < limite for valor in fatia[coluna]):
            raise _erro_nos_filtros(nome, f"a coluna {coluna} aponta para fora da lista")
    if any(diferenca < 0 for diferenca in fatia["q"]) or sum(fatia["q"]) >= max(
        len(indice["quadrados"]), 1
    ):
        raise _erro_nos_filtros(nome, "a coluna q aponta para fora da lista de quadrados")
    if com_dia and any(not 1 <= dia <= 31 for dia in fatia["d"]):
        raise _erro_nos_filtros(nome, "um dia não está entre 1 e 31")
    if any(n < 1 or not 0 <= f <= n for n, f in zip(fatia["n"], fatia["f"])):
        raise _erro_nos_filtros(nome, "os chamados e os fechados não batem")


def _ler_filtros(pasta, features):
    """(informações para o mapa, ordem dos quadrados, {nome: fatia}), ou (None, None, {}).

    Sem a pasta filtros/ (saída do agregador) ou sem chamado nela, o site fica sem filtros.
    """
    if not (pasta / "indice.json").is_file():
        return None, None, {}
    indice = _ler_json(pasta, "indice.json")
    if isinstance(indice, dict) and indice.get("primeiro_dia") is None:
        return None, None, {}  # a coleta não achou nenhum chamado com quadrado
    _conferir_indice(indice, {f["properties"]["quadrado"] for f in features})
    nomes = [("tudo.json", False)] + [(f"{ano}.json", False) for ano in indice["anos"]] + [
        (f"{mes}.json", True) for mes in indice["meses"]
    ]
    fatias = {}
    for nome, com_dia in nomes:
        fatia = _ler_json(pasta, nome)
        _conferir_fatia(nome, fatia, indice, com_dia)
        fatias[nome] = json.dumps(fatia, separators=(",", ":"))
    info = {
        "temas": indice["temas"],
        "estados": indice["estados"],
        "prazos": indice["prazos"],
        "orgaos": indice["orgaos"],
        "meses": indice["meses"],
        "anos": indice["anos"],
        "primeiro_dia": indice["primeiro_dia"],
        "ultimo_dia": indice["ultimo_dia"],
        "bairros": indice["bairros"],
        "classes": [[limite, cor] for limite, cor in CLASSES],
        "atendido": SITUACAO_ATENDIDO,
    }
    return info, indice["quadrados"], fatias


# ---- Cor e texto do clique ------------------------------------------------------------


def _milhar(numero):
    """1440 -> '1.440' (ponto de milhar, como se lê no Brasil)."""
    return f"{numero:,}".replace(",", ".")


def _decimal(texto):
    """'1.5' -> '1,5' (vírgula decimal)."""
    return texto.replace(".", ",")


def _classe(chamados):
    cor = CLASSES[0][1]
    for limite, cor_da_classe in CLASSES:
        if chamados >= limite:
            cor = cor_da_classe
    return cor


def _numero(texto):
    """Número inteiro do CSV, ou None se vazio."""
    return int(texto) if texto.strip().isdigit() else None


def _quadrado_para_o_mapa(feature):
    """Contorno do agregador mais a cor e as linhas que o clique mostra. Sem valores vazios."""
    propriedades = feature["properties"]
    chamados = propriedades["chamados"]
    if _numero(str(chamados)) is None:  # "menos de N", de uma coleta de antes da issue #31
        raise _erro_do_minimo("quadrados.geojson")
    fechados = int(propriedades["fechados"])
    mediana = propriedades["mediana_dias_ate_fechar"]
    linhas = [
        ["Chamados", _milhar(int(chamados))],
        ["Atendidos", _milhar(int(propriedades["atendidos"]))],
        ["Fechados", _milhar(fechados)],
        ["Ainda abertos", _milhar(int(chamados) - fechados)],
        ["Mediana de dias até fechar", TRACO if mediana in ("", None) else _decimal(str(mediana))],
    ]
    cor = _classe(int(chamados))
    return {
        "type": "Feature",
        "properties": {"id": propriedades["quadrado"], "cor": cor, "linhas": linhas},
        "geometry": feature["geometry"],
    }


def _dados_do_mapa(features, info):
    dados = {
        "limites": LIMITES_DO_RIO,
        "quadrados": {
            "type": "FeatureCollection",
            "features": [_quadrado_para_o_mapa(feature) for feature in features],
        },
    }
    if info:
        dados["filtros"] = info
    return dados


# ---- Páginas --------------------------------------------------------------------------


def _legenda():
    itens = []
    for posicao, (inicio, cor) in enumerate(CLASSES):
        if posicao + 1 < len(CLASSES):
            fim = CLASSES[posicao + 1][0] - 1
            rotulo = f"{_milhar(inicio)} a {_milhar(fim)}" if fim > inicio else _milhar(inicio)
        else:
            rotulo = f"{_milhar(inicio)} ou mais"
        itens.append((cor, rotulo))
    linhas = "\n".join(
        f'        <li><span class="amostra" style="background:{cor}"></span>{html.escape(rotulo)}</li>'
        for cor, rotulo in itens
    )
    return linhas


def _rotulo(valor):
    return VAZIO if valor == "" else valor


def _caixas(nome, opcoes):
    """As caixas de marcar de um filtro, em ordem alfabética. opcoes: [(valor, rótulo)]."""
    ordem = sorted(opcoes, key=lambda opcao: (opcao[1] == VAZIO, opcao[1].casefold()))
    return "\n".join(
        f'          <label><input type="checkbox" name="{nome}" value="{html.escape(valor)}"> '
        f"{html.escape(rotulo, quote=False)}</label>"
        for valor, rotulo in ordem
    )


def _grupo(legenda, nome, opcoes, antes="", id_da_lista=""):
    lista = f' id="{id_da_lista}"' if id_da_lista else ""
    return f"""      <fieldset>
        <legend>{legenda}</legend>{antes}
        <div class="opcoes"{lista}>
{_caixas(nome, opcoes)}
        </div>
      </fieldset>"""


def _painel_de_filtros(info):
    """O painel de filtros e a busca de bairro, ou "" se o site não tem filtros."""
    if not info:
        return ""

    def por_posicao(lista):
        return [(str(posicao), _rotulo(valor)) for posicao, valor in enumerate(lista)]

    def do_estado(posicao):
        return [(valor, _rotulo(valor)) for valor in sorted({e[posicao] for e in info["estados"]})]

    datas = f'min="{info["primeiro_dia"]}" max="{info["ultimo_dia"]}"'
    busca_do_orgao = (
        '\n        <input type="search" id="busca-orgao" class="busca" placeholder="Buscar órgão" '
        'aria-label="Buscar órgão pelo nome" autocomplete="off">'
    )
    grupos = "\n".join([
        _grupo("Tema", "tema", por_posicao(info["temas"])),
        _grupo("Status", "status", do_estado(0)),
        _grupo("Situação", "situacao", do_estado(1)),
        _grupo("Tipo de situação", "tipo_situacao", do_estado(2)),
        _grupo("Prazo", "prazo", por_posicao(info["prazos"])),
        _grupo("Órgão responsável", "orgao", por_posicao(info["orgaos"]), busca_do_orgao,
               "lista-orgaos"),
    ])
    bairros = "\n".join(
        f'      <option value="{html.escape(nome)}"></option>' for nome in sorted(info["bairros"])
    )
    return f"""
  <details class="painel">
    <summary>Filtros</summary>
    <form id="form-filtros" class="filtros" action="#">
      <p class="frase-do-filtro">{html.escape(FRASE_DO_FILTRO)}</p>
      <fieldset class="periodo">
        <legend>Período (dia de abertura do chamado)</legend>
        <label>De <input type="date" id="filtro-de" {datas}></label>
        <label>Até <input type="date" id="filtro-ate" {datas}></label>
      </fieldset>
{grupos}
      <p id="aviso-filtros" class="aviso" role="alert"></p>
      <button type="button" id="limpar-filtros" class="botao secundario">Limpar filtros</button>
    </form>
  </details>
  <form id="form-bairro" class="busca-bairro" role="search" action="#">
    <label for="busca-bairro">Bairro</label>
    <input type="search" id="busca-bairro" class="busca" list="lista-bairros" placeholder="Ex.: Tijuca" autocomplete="off">
    <button type="submit" class="botao">Ir</button>
    <datalist id="lista-bairros">
{bairros}
    </datalist>
    <span id="aviso-bairro" class="aviso" role="alert"></span>
  </form>"""


def _versao(rotulo):
    return f'  <p class="versao">{html.escape(rotulo, quote=False)}</p>'


def _pagina_do_mapa(info, rotulo_da_versao):
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mapa 1746 — chamados por quadrado de 100 m</title>
  <link rel="stylesheet" href="{LEAFLET}/leaflet.css" integrity="{LEAFLET_CSS_HASH}" crossorigin="">
  <link rel="stylesheet" href="estilo.css">
</head>
<body class="tela-mapa">
  <header class="topo">
    <h1>Mapa 1746</h1>
    <p class="subtitulo">Chamados do 1746 do Rio de Janeiro, por quadrado de 100 m. Toque num quadrado para ver os números.</p>
    <nav class="botoes">
      <a class="botao" href="ruas.csv" download>Baixar a tabela por rua</a>
      <a class="botao" href="quadrados.csv" download>Baixar a tabela por quadrado</a>
      <a class="botao secundario" href="metodo.html">Método e fonte</a>
    </nav>{_painel_de_filtros(info)}
  </header>
  <div id="mapa" role="application" aria-label="Mapa dos chamados do 1746 por quadrado de 100 m"></div>
  <section class="legenda" aria-label="Legenda">
    <h2>Chamados por quadrado</h2>
    <ul>
{_legenda()}
    </ul>
    <p>{html.escape(FRASE_DA_COR)}</p>
  </section>
{_versao(rotulo_da_versao)}
  <script src="{LEAFLET}/leaflet.js" integrity="{LEAFLET_JS_HASH}" crossorigin=""></script>
  <script src="dados.js"></script>
  <script src="filtros.js"></script>
  <script src="mapa.js"></script>
</body>
</html>
"""


def _porcentagem(parte, total):
    """'53,4%' (uma casa, vírgula decimal); None se não há total para a conta."""
    if total <= 0:
        return None
    return f"{parte / total * 100:.1f}".replace(".", ",") + "%"


def _numero_do_resumo(resumo, *nomes):
    """Inteiro de um dos campos do resumo, ou None se não houver."""
    for nome in nomes:
        valor = resumo.get(nome, "")
        if valor.isdigit():
            return int(valor)
    return None


def _quantos(numero, porcentagem):
    """'10.902.581 chamados (53,4%) não têm', ou '1 chamado não tem' (a conta inclui o verbo)."""
    contagem = f"{_milhar(numero)} chamado" if numero == 1 else f"{_milhar(numero)} chamados"
    if porcentagem:
        contagem += f" ({porcentagem})"
    return contagem, ("não tem" if numero == 1 else "não têm")


def _o_que_fica_de_fora(resumo):
    """Itens da página de método sobre os chamados que não entram no mapa nem na tabela por rua.

    Lê do resumo.txt: chamados lidos (ou contados), sem coordenada, sem rua e, se a coleta
    gravar, coordenada fora do município. O que o resumo não traz não aparece. Se o resumo
    traz os chamados de problema público (issue #26), a conta é sobre eles.
    """
    publicos = _numero_do_resumo(resumo, CAMPO_DO_PROBLEMA_PUBLICO)
    itens = []
    if publicos is not None:
        total = publicos
        base = f"Dos {_milhar(total)} chamados de problema público, "
    else:
        total = _numero_do_resumo(resumo, "contados", "chamados lidos")
        base = f"Dos {_milhar(total)} chamados lidos, " if total is not None else ""
    sem_coordenada = _numero_do_resumo(resumo, "sem coordenada")
    if sem_coordenada is not None:
        contagem, verbo = _quantos(sem_coordenada, _porcentagem(sem_coordenada, total or 0))
        itens.append(
            f"{base}{contagem} {verbo} coordenada e não aparecem no mapa. "
            f"O mapa mostra só os chamados que têm coordenada."
        )
    sem_rua = _numero_do_resumo(resumo, "sem rua")
    if sem_rua is not None:
        contagem, verbo = _quantos(sem_rua, _porcentagem(sem_rua, total or 0))
        itens.append(
            f"{contagem} {verbo} rua e não entram na tabela por rua; "
            f"se têm coordenada, aparecem no mapa."
        )
    fora = _numero_do_resumo(
        resumo, "dos quais com coordenada fora do município", "coordenada fora do município"
    )
    if fora is not None:
        itens.append(
            f"{_milhar(fora)} chamados com coordenada fora do município do Rio foram descartados "
            f"do mapa, porque a coordenada está provavelmente errada."
        )
    return "\n".join(f"      <li>{html.escape(item)}</li>" for item in itens)


def _o_que_o_mapa_mostra(so_problema_publico):
    if so_problema_publico:
        filtro = ("só os chamados de problema público: problema em espaço ou serviço público, "
                  "como iluminação, buraco, limpeza, árvore, drenagem, semáforo e ônibus")
    else:
        filtro = "todos os chamados da base, sem filtro"
    return (
        f"O total de chamados do 1746 do Rio de Janeiro em cada quadrado de 100 m por 100 m, "
        f"somando {filtro}. Um toque num quadrado mostra os números dele: chamados, atendidos, "
        f"fechados, ainda abertos (chamados menos fechados) e a mediana de dias até fechar."
    )


def _por_que_so_problema_publico(resumo):
    """A seção da página de método sobre o filtro de privacidade, ou "" se o resumo não traz.

    Diz o motivo, quantos chamados entram no mapa e quantos ficaram fora em cada grupo.
    """
    publicos = _numero_do_resumo(resumo, CAMPO_DO_PROBLEMA_PUBLICO)
    if publicos is None:
        return ""
    total = _numero_do_resumo(resumo, "chamados lidos")
    if total is not None:
        porcentagem = _porcentagem(publicos, total)
        conta = f" ({porcentagem})" if porcentagem else ""
        entram = (f"Dos {_milhar(total)} chamados lidos, {_milhar(publicos)}{conta} são de "
                  f"problema público e entram no mapa e na tabela por rua.")
    else:
        entram = (f"{_milhar(publicos)} chamados são de problema público e entram no mapa "
                  f"e na tabela por rua.")
    itens = []
    for grupo, rotulo in GRUPOS_FORA_DO_MAPA:
        quantos = _numero_do_resumo(resumo, grupo)
        if quantos is not None:
            contagem, _ = _quantos(quantos, _porcentagem(quantos, total or 0))
            itens.append(f"      <li>{html.escape(rotulo)}: {html.escape(contagem)}.</li>")
    fora = ""
    if itens:
        fora = "\n    <p>Ficaram de fora do mapa:</p>\n    <ul>\n" + "\n".join(itens) + "\n    </ul>"
    return f"""
    <h2>Por que só problema público</h2>
    <p>Por privacidade, como pede a Lei Geral de Proteção de Dados (LGPD): o mapa não pode
    apontar uma pessoa, uma casa ou um estabelecimento. Um quadrado com chamados de denúncia ou
    de pedido pessoal poderia fazer isso. Os chamados de problema público falam do espaço e do
    serviço público, e não de quem mora ali.</p>
    <p>{html.escape(entram)}</p>{fora}
    <p>Cada par tipo/subtipo do 1746 está num grupo, numa lista aberta:
    <a href="{LINK_DA_LISTA}">lista de classificação</a>. Um subtipo novo fica fora do mapa
    até ser classificado.</p>
"""


def _chamados(numero):
    return f"{_milhar(numero)} chamado" if numero == 1 else f"{_milhar(numero)} chamados"


def _data_br(iso):
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def _como_funcionam_os_filtros(info):
    """A seção da página de método sobre os filtros, ou "" se o site não tem filtros."""
    if not info:
        return ""
    return f"""
    <h2>Como funcionam os filtros</h2>
    <p>{html.escape(FRASE_DO_FILTRO)}</p>
    <ul>
      <li><strong>Período.</strong> Conta pela data de abertura do chamado, dia a dia: as duas
      datas entram, e entram os chamados fechados ou não. O calendário vai do primeiro ao último
      dia com chamados na base ({_data_br(info["primeiro_dia"])} a {_data_br(info["ultimo_dia"])}).</li>
      <li><strong>Tema</strong> é o tipo do chamado, só entre os de problema público.
      <strong>Status</strong>, <strong>situação</strong>, <strong>tipo de situação</strong>,
      <strong>prazo</strong> e <strong>órgão responsável</strong> trazem os valores como estão
      na base.</li>
      <li>Num mesmo filtro, marcar mais de um valor soma os chamados de cada um. Com mais de um
      filtro, entram só os chamados que atendem a todos.</li>
      <li>Um quadrado que fica sem chamados some do mapa enquanto o filtro está ligado.</li>
      <li>A busca de bairro só leva o mapa até o bairro e não muda a soma.</li>
      <li>A mediana de dias até fechar só aparece sem filtro. Ela não se soma, e calculá-la com
      filtro pediria publicar os dias até fechar de cada chamado.</li>
    </ul>
"""


def _prazo_por_situacao(texto_do_resumo):
    """[(prazo, situação, chamados)] do bloco que a coleta grava, ou None se não há o bloco."""
    linhas = texto_do_resumo.splitlines()
    cabecalhos = [linha.strip().lower() for linha in linhas]
    if CABECALHO_DO_PRAZO.lower() not in cabecalhos:
        return None
    pares = []
    for linha in linhas[cabecalhos.index(CABECALHO_DO_PRAZO.lower()) + 1:]:
        par, separador, numero = linha.strip().rpartition(":")
        prazo, barra, situacao = par.partition(" / ")
        if not linha.startswith("  ") or not separador or not barra or not numero.strip().isdigit():
            break
        pares.append((prazo, situacao, int(numero)))
    return pares


def _sobre_o_prazo(texto_do_resumo):
    """A nota do prazo na página de método, com os números da coleta, ou "" sem o bloco."""
    pares = _prazo_por_situacao(texto_do_resumo)
    if not pares:
        return ""
    itens = "\n".join(
        f"      <li>{html.escape(f'{prazo} / {situacao}: {_chamados(numero)}', quote=False)}</li>"
        for prazo, situacao, numero in pares
    )
    a_vencer = sum(numero for prazo, _, numero in pares if prazo == PRAZO_A_VENCER)
    nao_encerrados = sum(numero for _, situacao, numero in pares
                         if situacao == SITUACAO_NAO_ENCERRADO)
    nota = ""
    if a_vencer > nao_encerrados:
        nota = html.escape(
            f"{_chamados(a_vencer)} estão com o prazo \"{PRAZO_A_VENCER}\", mas só "
            f"{_milhar(nao_encerrados)} não estão encerrados. A coluna do prazo parece não ser "
            f"atualizada depois que o chamado fecha: use o filtro de prazo com cuidado.",
            quote=False,
        )
        nota = f"\n    <p>{nota}</p>"
    return f"""
    <h2>Sobre o prazo</h2>
    <p>A coleta cruza o prazo (a coluna <code>dentro_prazo</code>) com a situação de cada chamado
    de problema público:</p>
    <ul>
{itens}
    </ul>{nota}
"""


def _pagina_de_metodo(resumo, texto_do_resumo, info, rotulo_da_versao):
    mais_recente = _data_do_resumo(
        resumo, "chamado mais recente na base", "chamado mais recente", "data do chamado mais recente"
    )
    coleta = _data_do_resumo(resumo, "data da coleta", "coleta")
    fora_do_mapa = _o_que_fica_de_fora(resumo)
    privacidade = _por_que_so_problema_publico(resumo)
    o_que_mostra = _o_que_o_mapa_mostra(bool(privacidade))
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Método e fonte — Mapa 1746</title>
  <link rel="stylesheet" href="estilo.css">
</head>
<body class="tela-texto">
  <main class="texto">
    <p><a href="index.html">← Voltar ao mapa</a></p>
    <h1>Método e fonte</h1>

    <h2>O que o mapa mostra</h2>
    <p>{html.escape(o_que_mostra)}</p>
{privacidade}{_como_funcionam_os_filtros(info)}{_sobre_o_prazo(texto_do_resumo)}
    <h2>O que a cor quer dizer</h2>
    <p>{html.escape(FRASE_DA_COR)}</p>

    <h2>Fonte dos dados</h2>
    <ul>
      <li>Tabela de origem: <code>{TABELA_DE_ORIGEM}</code>, os chamados do 1746 da Prefeitura
      do Rio de Janeiro, publicados no <a href="{LINK_DATA_RIO}">Data.Rio</a>.</li>
      <li>Chamado mais recente na base: {mais_recente}.</li>
      <li>Data da coleta: {coleta}.</li>
      <li>Licença dos dados: a definir (será conferida na fonte).</li>
      <li>Licença do código: licença MIT. O código e o método estão abertos em
      <a href="{LINK_DO_CODIGO}">{LINK_DO_CODIGO}</a>.</li>
      <li>Mapa de fundo: © colaboradores do <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>.</li>
    </ul>

    <h2>Como os números são feitos</h2>
    <ul>
      <li><strong>Grade de 100 m.</strong> Cada chamado cai num quadrado de 100 m por 100 m,
      numa grade em metros (SIRGAS 2000 / UTM zona 23S). Este site só tem totais por quadrado
      e por rua: nenhum chamado individual nem coordenada exata. Toda rua e todo quadrado
      mostra o número, mesmo com 1 chamado.</li>
      <li><strong>Atendidos</strong> são os chamados com a situação "Atendido";
      <strong>fechados</strong>, os que têm data de fechamento;
      <strong>ainda abertos</strong>, os chamados menos os fechados.</li>
    </ul>

    <h2>Limites</h2>
    <ul>
{fora_do_mapa}
      <li>A falta de água e de luz em casa não passa pelo 1746, e por isso não aparece aqui.</li>
      <li>Ausência de chamado não é ausência de problema: nem todo problema vira chamado.</li>
      <li>O mapa mostra só os números, sem juntar nem comparar lugares.</li>
    </ul>

    <h2>Tabelas</h2>
    <p>As mesmas tabelas do mapa, em CSV com ponto e vírgula, para abrir no Excel:
    <a href="ruas.csv" download>por rua</a> e <a href="quadrados.csv" download>por quadrado</a>.
    Elas trazem sempre os totais sem filtro.</p>
  </main>
{_versao(rotulo_da_versao)}
</body>
</html>
"""


ESTILO = """\
/* Estilo do site do Mapa 1746. Funciona a partir de 375 px de largura, sem rolar para o lado. */
* { box-sizing: border-box; }
html, body { margin: 0; max-width: 100%; overflow-x: hidden; }
body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: #1f2933; line-height: 1.4; }
a { color: #0b5cad; }
[hidden] { display: none !important; }

/* Tela do mapa: título e botões em cima, mapa no meio, legenda embaixo. */
.tela-mapa { display: flex; flex-direction: column; height: 100vh; height: 100dvh; }
.topo { padding: 8px 12px; background: #fff; border-bottom: 1px solid #d9dee3; }
.topo h1 { margin: 0; font-size: 1.15rem; }
.subtitulo { margin: 2px 0 6px; font-size: 0.85rem; color: #52606d; }
.botoes { display: flex; flex-wrap: wrap; gap: 6px; }
.botao { display: inline-block; padding: 8px 12px; border-radius: 6px; background: #0b5cad; color: #fff;
  font-size: 0.9rem; text-decoration: none; }
.botao.secundario { background: #fff; color: #0b5cad; border: 1px solid #0b5cad; }
#mapa { flex: 1 1 auto; min-height: 200px; width: 100%; }
.legenda { padding: 8px 12px 26px; background: #fff; border-top: 1px solid #d9dee3; font-size: 0.8rem; max-height: 42vh; overflow-y: auto; }
.legenda h2 { margin: 0 0 4px; font-size: 0.9rem; }
.legenda ul { list-style: none; margin: 0 0 6px; padding: 0; display: flex; flex-wrap: wrap; gap: 2px 14px; }
.legenda li { display: flex; align-items: center; gap: 6px; }
.legenda p { margin: 0; }
.amostra { display: inline-block; width: 16px; height: 16px; border: 1px solid rgba(0, 0, 0, 0.35); border-radius: 3px; flex: none; }

/* Painel de filtros e busca de bairro (issue #31). */
.painel { margin-top: 6px; font-size: 0.85rem; }
.painel summary { cursor: pointer; font-weight: 600; color: #0b5cad; padding: 4px 0; }
.filtros { max-height: 40vh; overflow-y: auto; padding: 4px 0; }
.filtros fieldset { border: 1px solid #d9dee3; border-radius: 6px; margin: 0 0 6px; padding: 4px 8px 6px; }
.filtros legend { font-weight: 600; padding: 0 4px; }
.periodo label { display: inline-flex; align-items: center; gap: 4px; margin: 2px 12px 2px 0; }
.periodo input { font: inherit; padding: 4px; }
.opcoes { display: flex; flex-wrap: wrap; gap: 2px 14px; max-height: 9.5rem; overflow-y: auto; }
.opcoes label { display: flex; align-items: center; gap: 4px; }
.busca { font: inherit; padding: 6px 8px; border: 1px solid #9aa5b1; border-radius: 6px; width: 100%; max-width: 20rem; margin: 2px 0 4px; }
.frase-do-filtro { margin: 0 0 6px; color: #52606d; }
.aviso { color: #a61b1b; font-weight: 600; }
.aviso:empty { display: none; }
.busca-bairro { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 6px; font-size: 0.85rem; }
.busca-bairro label { font-weight: 600; }
.busca-bairro .busca { flex: 1 1 10rem; margin: 0; }
.busca-bairro .botao { border: 0; cursor: pointer; font: inherit; }
.filtros .botao { border-radius: 6px; cursor: pointer; font: inherit; }

/* Texto do clique no quadrado. */
.numeros { margin: 0; padding: 0; border-collapse: collapse; font-size: 0.9rem; }
.numeros th { text-align: left; font-weight: normal; padding: 1px 12px 1px 0; }
.numeros td { text-align: right; font-weight: 600; padding: 1px 0; }
.nota { margin: 6px 0 0; font-size: 0.8rem; color: #52606d; }

/* Versão publicada, num canto fixo da tela. */
.versao { position: fixed; left: 0; bottom: 0; margin: 0; padding: 2px 8px; font-size: 0.75rem; color: #52606d;
  background: rgba(255, 255, 255, 0.92); border-top-right-radius: 6px; z-index: 1000; }

/* Página de método. */
.texto { max-width: 42rem; margin: 0 auto; padding: 12px 16px 48px; }
.texto h1 { font-size: 1.5rem; }
.texto h2 { font-size: 1.1rem; margin-top: 1.5rem; }
.texto code { overflow-wrap: anywhere; }
.texto a { overflow-wrap: anywhere; }
"""


MAPA_JS = r"""// Mapa 1746. Lê window.MAPA_DADOS (dados.js) e desenha os quadrados com a biblioteca Leaflet.
// Com o painel de filtros (issue #31), soma de novo cada quadrado com as contas do filtros.js.
(function () {
  var dados = window.MAPA_DADOS;
  var Filtros = window.Filtros;
  var mapa = L.map("mapa", { preferCanvas: true });
  mapa.fitBounds(dados.limites);
  // Abrir ou fechar o painel de filtros muda a altura do mapa: o Leaflet precisa saber.
  if (window.ResizeObserver) {
    new ResizeObserver(function () { mapa.invalidateSize(); }).observe(document.getElementById("mapa"));
  }

  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(mapa);

  // O texto do clique é montado com textContent: nada do dado vira HTML.
  function textoDoClique(linhas, nota) {
    var caixa = document.createElement("div");
    var tabela = document.createElement("table");
    tabela.className = "numeros";
    linhas.forEach(function (linha) {
      var tr = document.createElement("tr");
      var th = document.createElement("th");
      var td = document.createElement("td");
      th.textContent = linha[0];
      td.textContent = linha[1];
      tr.appendChild(th);
      tr.appendChild(td);
      tabela.appendChild(tr);
    });
    caixa.appendChild(tabela);
    if (nota) {
      var paragrafo = document.createElement("p");
      paragrafo.className = "nota";
      paragrafo.textContent = nota;
      caixa.appendChild(paragrafo);
    }
    return caixa;
  }

  function estilo(cor) {
    return { color: cor, weight: 0.5, fillColor: cor, fillOpacity: 0.8 };
  }

  var features = dados.quadrados.features;
  var soma = null; // null: sem filtro, valem os totais prontos do dados.js
  var camadas = [];
  var grupo = L.geoJSON(dados.quadrados, {
    style: function (feature) { return estilo(feature.properties.cor); },
    onEachFeature: function (feature, camada) {
      var posicao = camadas.length;
      camadas.push(camada);
      camada.bindPopup(function () {
        if (!soma) return textoDoClique(feature.properties.linhas);
        return textoDoClique(
          Filtros.linhasDoClique(soma.n[posicao], soma.a[posicao], soma.f[posicao]),
          Filtros.NOTA_DA_MEDIANA
        );
      });
    }
  }).addTo(mapa);

  var info = dados.filtros;
  if (!info) return; // site sem a pasta filtros/: sem painel

  var formulario = document.getElementById("form-filtros");
  var aviso = document.getElementById("aviso-filtros");
  var de = document.getElementById("filtro-de");
  var ate = document.getElementById("filtro-ate");
  var guardadas = {};
  var pedido = 0;

  // Cada fatia é buscada uma vez só, na pasta filtros/ do próprio site.
  function carregar(nome) {
    if (!guardadas[nome]) {
      guardadas[nome] = fetch("filtros/" + nome).then(function (resposta) {
        if (!resposta.ok) throw new Error(nome);
        return resposta.json();
      });
      guardadas[nome].catch(function () { delete guardadas[nome]; });
    }
    return guardadas[nome];
  }

  // Os valores marcados de um filtro, ou null se nenhum está marcado (o filtro está desligado).
  function marcados(nome, comoNumero) {
    var caixas = formulario.querySelectorAll('input[name="' + nome + '"]:checked');
    if (!caixas.length) return null;
    return Array.prototype.map.call(caixas, function (caixa) {
      return comoNumero ? Number(caixa.value) : caixa.value;
    });
  }

  function redesenhar() {
    mapa.closePopup();
    camadas.forEach(function (camada, i) {
      var chamados = soma ? soma.n[i] : 1;
      if (chamados > 0) {
        camada.setStyle(estilo(soma ? Filtros.cor(chamados, info.classes) : features[i].properties.cor));
        if (!grupo.hasLayer(camada)) grupo.addLayer(camada);
      } else if (grupo.hasLayer(camada)) {
        grupo.removeLayer(camada); // com 0 chamados, o quadrado some enquanto o filtro está ligado
      }
    });
  }

  function aplicar() {
    var erro = Filtros.validarPeriodo(de.value, ate.value, info);
    if (erro) { pedido += 1; aviso.textContent = erro; return; }
    var filtro = {
      temas: marcados("tema", true),
      status: marcados("status", false),
      situacoes: marcados("situacao", false),
      tipos_de_situacao: marcados("tipo_situacao", false),
      prazos: marcados("prazo", true),
      orgaos: marcados("orgao", true)
    };
    pedido += 1;
    var meu = pedido;
    if (!Filtros.estaFiltrando(filtro, de.value, ate.value)) {
      aviso.textContent = "";
      soma = null;
      redesenhar();
      return;
    }
    var partes = Filtros.fatiasDoPeriodo(de.value, ate.value, info);
    aviso.textContent = "Carregando…";
    Promise.all(partes.map(function (parte) { return carregar(parte.nome); })).then(function (lidas) {
      if (meu !== pedido) return; // outro filtro foi escolhido enquanto carregava
      var fatias = lidas.map(function (lida, i) { return { dados: lida, dias: partes[i].dias }; });
      soma = Filtros.somar(fatias, filtro, info, features.length);
      aviso.textContent = "";
      redesenhar();
    }).catch(function () {
      if (meu === pedido) aviso.textContent = "Não consegui carregar os filtros. Confira a internet e tente de novo.";
    });
  }

  formulario.addEventListener("submit", function (evento) { evento.preventDefault(); });
  formulario.addEventListener("change", function (evento) {
    if (evento.target.id !== "busca-orgao") aplicar();
  });

  // Ao clicar no campo de data, abre o calendário (onde o navegador deixa).
  [de, ate].forEach(function (campo) {
    campo.addEventListener("click", function () {
      if (typeof campo.showPicker !== "function") return;
      try { campo.showPicker(); } catch (e) { /* o navegador abre o calendário do jeito dele */ }
    });
  });

  var buscaDoOrgao = document.getElementById("busca-orgao");
  var rotulosDosOrgaos = document.getElementById("lista-orgaos").querySelectorAll("label");
  function filtrarOrgaos() {
    var visiveis = {};
    Filtros.filtrarLista(buscaDoOrgao.value, info.orgaos).forEach(function (i) { visiveis[i] = true; });
    Array.prototype.forEach.call(rotulosDosOrgaos, function (rotulo) {
      rotulo.hidden = !visiveis[rotulo.querySelector("input").value];
    });
  }
  buscaDoOrgao.addEventListener("input", filtrarOrgaos);

  document.getElementById("limpar-filtros").addEventListener("click", function () {
    formulario.reset();
    filtrarOrgaos();
    aplicar();
  });

  // A busca de bairro só leva o mapa até o bairro: não muda a soma.
  var campoDoBairro = document.getElementById("busca-bairro");
  var avisoDoBairro = document.getElementById("aviso-bairro");
  document.getElementById("form-bairro").addEventListener("submit", function (evento) {
    evento.preventDefault();
    var caixa = Filtros.acharBairro(campoDoBairro.value, info.bairros);
    if (!caixa) { avisoDoBairro.textContent = Filtros.BAIRRO_NAO_ENCONTRADO; return; }
    avisoDoBairro.textContent = "";
    mapa.fitBounds([[caixa[0], caixa[1]], [caixa[2], caixa[3]]]);
  });
})();
"""


FILTROS_JS = r"""// Mapa 1746: as contas dos filtros (issue #31), sem tela. O mapa.js usa estas funções no
// navegador, e os testes usam as mesmas no Node. As fatias só têm totais por quadrado.
(function (raiz) {
  "use strict";

  var TRACO = "—";
  var NOTA_DA_MEDIANA = "A mediana só aparece sem filtro.";
  var BAIRRO_NAO_ENCONTRADO = "Bairro não encontrado";
  var DATA_FINAL_ANTES = "A data final é antes da data inicial";

  // 1440 -> "1.440"
  function milhar(numero) {
    return String(numero).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  // Para buscar sem ligar para acento, maiúscula e espaço a mais.
  function semAcento(texto) {
    return String(texto).normalize("NFD").replace(/[̀-ͯ]/g, "")
      .toLowerCase().replace(/\s+/g, " ").trim();
  }

  function dataBR(iso) {
    var partes = iso.split("-");
    return partes[2] + "/" + partes[1] + "/" + partes[0];
  }

  // As datas vêm do campo de data, como "AAAA-MM-DD" (ou "" se vazio): a ordem do texto é a do dia.
  function validarPeriodo(de, ate, info) {
    if (de && ate && ate < de) return DATA_FINAL_ANTES;
    var fora = [de, ate].some(function (dia) {
      return dia && (dia < info.primeiro_dia || dia > info.ultimo_dia);
    });
    if (fora) return "Escolha datas entre " + dataBR(info.primeiro_dia) + " e " + dataBR(info.ultimo_dia);
    return null;
  }

  function doisDigitos(numero) { return (numero < 10 ? "0" : "") + numero; }
  function dia(ano, mes, numero) { return ano + "-" + doisDigitos(mes) + "-" + doisDigitos(numero); }
  function ultimoDoMes(ano, mes) { return new Date(Date.UTC(ano, mes, 0)).getUTCDate(); }
  function maior(a, b) { return a > b ? a : b; }
  function menor(a, b) { return a < b ? a : b; }

  // As fatias que o período pede: tudo.json sem data; o ano inteiro quando o período cobre o
  // ano; senão, os meses, com os dias das pontas. [{nome, dias: [de, até] ou null}]
  function fatiasDoPeriodo(de, ate, info) {
    var inicio = maior(de || info.primeiro_dia, info.primeiro_dia);
    var fim = menor(ate || info.ultimo_dia, info.ultimo_dia);
    if (inicio === info.primeiro_dia && fim === info.ultimo_dia) {
      return [{ nome: "tudo.json", dias: null }];
    }
    var partes = [];
    if (fim < inicio) return partes;
    info.anos.forEach(function (ano) {
      var comeco = maior(dia(ano, 1, 1), info.primeiro_dia);
      var final = menor(dia(ano, 12, 31), info.ultimo_dia);
      if (final < inicio || comeco > fim) return;
      if (inicio <= comeco && fim >= final) {
        partes.push({ nome: ano + ".json", dias: null });
        return;
      }
      info.meses.forEach(function (mes) {
        if (Number(mes.slice(0, 4)) !== ano) return;
        var numero = Number(mes.slice(5, 7));
        var primeiro = maior(dia(ano, numero, 1), info.primeiro_dia);
        var ultimo = menor(dia(ano, numero, ultimoDoMes(ano, numero)), info.ultimo_dia);
        if (ultimo < inicio || primeiro > fim) return;
        if (inicio <= primeiro && fim >= ultimo) {
          partes.push({ nome: mes + ".json", dias: null });
        } else {
          partes.push({ nome: mes + ".json", dias: [
            Number(maior(inicio, primeiro).slice(8)), Number(menor(fim, ultimo).slice(8))
          ] });
        }
      });
    });
    return partes;
  }

  function conjunto(valores) {
    if (!valores) return null; // filtro desligado: vale tudo
    var marcados = {};
    valores.forEach(function (valor) { marcados[valor] = true; });
    return marcados;
  }

  function estaFiltrando(filtro, de, ate) {
    if (de || ate) return true;
    return ["temas", "status", "situacoes", "tipos_de_situacao", "prazos", "orgaos"]
      .some(function (nome) { return Boolean(filtro[nome]); });
  }

  // Soma as fatias com o filtro: {n: chamados, a: atendidos, f: fechados}, por posição do quadrado.
  function somar(fatias, filtro, info, quantos) {
    var n = new Float64Array(quantos), a = new Float64Array(quantos), f = new Float64Array(quantos);
    var temas = conjunto(filtro.temas), prazos = conjunto(filtro.prazos), orgaos = conjunto(filtro.orgaos);
    var status = conjunto(filtro.status), situacoes = conjunto(filtro.situacoes);
    var tipos = conjunto(filtro.tipos_de_situacao);
    var estadoEntra = info.estados.map(function (estado) {
      return (!status || status[estado[0]] === true) && (!situacoes || situacoes[estado[1]] === true)
        && (!tipos || tipos[estado[2]] === true);
    });
    var atendido = info.estados.map(function (estado) { return estado[2] === info.atendido; });
    fatias.forEach(function (fatia) {
      var c = fatia.dados, dias = fatia.dias, quadrado = 0;
      for (var i = 0; i < c.q.length; i++) {
        quadrado += c.q[i]; // a coluna q vem como diferença para a linha anterior
        if (dias && (c.d[i] < dias[0] || c.d[i] > dias[1])) continue;
        if (temas && !temas[c.t[i]]) continue;
        if (prazos && !prazos[c.p[i]]) continue;
        if (orgaos && !orgaos[c.o[i]]) continue;
        if (!estadoEntra[c.e[i]]) continue;
        n[quadrado] += c.n[i];
        f[quadrado] += c.f[i];
        if (atendido[c.e[i]]) a[quadrado] += c.n[i];
      }
    });
    return { n: n, a: a, f: f };
  }

  function linhasDoClique(chamados, atendidos, fechados) {
    return [
      ["Chamados", milhar(chamados)],
      ["Atendidos", milhar(atendidos)],
      ["Fechados", milhar(fechados)],
      ["Ainda abertos", milhar(chamados - fechados)],
      ["Mediana de dias até fechar", TRACO]
    ];
  }

  function cor(chamados, classes) {
    var escolhida = classes[0][1];
    classes.forEach(function (classe) { if (chamados >= classe[0]) escolhida = classe[1]; });
    return escolhida;
  }

  // As posições dos nomes que têm o texto buscado (todas, se a busca está vazia).
  function filtrarLista(texto, nomes) {
    var busca = semAcento(texto);
    var posicoes = [];
    nomes.forEach(function (nome, i) {
      if (semAcento(nome).indexOf(busca) >= 0) posicoes.push(i);
    });
    return posicoes;
  }

  // A caixa do bairro [sul, oeste, norte, leste]: o nome igual ou, se só um tem o texto, esse.
  function acharBairro(texto, bairros) {
    var busca = semAcento(texto);
    if (!busca) return null;
    var nomes = Object.keys(bairros);
    var iguais = nomes.filter(function (nome) { return semAcento(nome) === busca; });
    if (iguais.length) return bairros[iguais[0]];
    var parecidos = nomes.filter(function (nome) { return semAcento(nome).indexOf(busca) >= 0; });
    return parecidos.length === 1 ? bairros[parecidos[0]] : null;
  }

  var Filtros = {
    NOTA_DA_MEDIANA: NOTA_DA_MEDIANA,
    BAIRRO_NAO_ENCONTRADO: BAIRRO_NAO_ENCONTRADO,
    validarPeriodo: validarPeriodo,
    fatiasDoPeriodo: fatiasDoPeriodo,
    estaFiltrando: estaFiltrando,
    somar: somar,
    linhasDoClique: linhasDoClique,
    cor: cor,
    filtrarLista: filtrarLista,
    acharBairro: acharBairro
  };
  if (typeof module !== "undefined" && module.exports) module.exports = Filtros;
  else raiz.Filtros = Filtros;
})(this);
"""


# ---- Montagem -------------------------------------------------------------------------


def _gravar_tabela(origem, destino):
    """Copia a tabela com a marca de UTF-8 no início, para o Excel abrir os acentos certos."""
    conteudo = Path(origem).read_text(encoding="utf-8-sig")
    Path(destino).write_text(conteudo, encoding="utf-8-sig", newline="")


def montar_site(entrada, saida, versao=None):
    """Lê as saídas do agregador (ou da coleta) em `entrada` e grava o site na pasta `saida`.

    `versao`: o nome da versão publicada (ex.: v2026.11.06), que aparece num canto da tela.
    Sem ele, aparece "Versão: local (não publicada)".
    """
    entrada = Path(entrada)
    # Tudo é lido e conferido antes de gravar qualquer coisa: nada de site pela metade.
    features, resumo, texto_do_resumo = _ler_entradas(entrada)
    info, ordem, fatias = _ler_filtros(entrada / PASTA_DOS_FILTROS, features)
    if ordem:  # na ordem do índice: a posição do quadrado é a mesma das fatias
        posicao = {quadrado: i for i, quadrado in enumerate(ordem)}
        features = sorted(features, key=lambda f: posicao[f["properties"]["quadrado"]])
    dados = _dados_do_mapa(features, info)
    rotulo_da_versao = f"Versão {versao}" if versao else VERSAO_LOCAL

    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "index.html").write_text(_pagina_do_mapa(info, rotulo_da_versao), encoding="utf-8")
    (saida / "metodo.html").write_text(
        _pagina_de_metodo(resumo, texto_do_resumo, info, rotulo_da_versao), encoding="utf-8"
    )
    (saida / "estilo.css").write_text(ESTILO, encoding="utf-8")
    (saida / "mapa.js").write_text(MAPA_JS, encoding="utf-8")
    (saida / "filtros.js").write_text(FILTROS_JS, encoding="utf-8")
    corpo = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    (saida / "dados.js").write_text(f"window.MAPA_DADOS = {corpo};\n", encoding="utf-8")
    for nome in TABELAS:
        _gravar_tabela(entrada / nome, saida / nome)
    _gravar_fatias(saida / PASTA_DOS_FILTROS, fatias)


def _gravar_fatias(pasta, fatias):
    """Troca as fatias do site pelas novas; sem fatias, a pasta sai."""
    if pasta.is_dir():
        for antiga in pasta.glob("*.json"):
            antiga.unlink()
        if not fatias and not any(pasta.iterdir()):
            pasta.rmdir()
    if fatias:
        pasta.mkdir(exist_ok=True)
        for nome, conteudo in fatias.items():
            (pasta / nome).write_text(conteudo, encoding="utf-8")


# ---- Linha de comando -----------------------------------------------------------------


class _ErroNaLinhaDeComando(Exception):
    """Algo errado nas opções. A mensagem já diz o que fazer."""


class _Formatador(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, "uso: " if prefix is None else prefix)


class _LeitorDeOpcoes(argparse.ArgumentParser):
    def error(self, message):
        # O argparse só fala inglês: aqui a mensagem é trocada por uma em português.
        if "unrecognized arguments" in message:
            raise _ErroNaLinhaDeComando(
                f"Não conheço {message.partition(': ')[2]}. O que fazer: {VEJA_A_AJUDA}"
            )
        if "expected one argument" in message and "--versao" in message:
            raise _ErroNaLinhaDeComando(
                "Falta o valor do --versao. O que fazer: escreva o nome da versão logo depois, "
                "por exemplo --versao v2026.11.06."
            )
        if "expected one argument" in message:
            raise _ErroNaLinhaDeComando(
                "Falta o valor do --saida. O que fazer: escreva a pasta logo depois, "
                "por exemplo --saida dados/site."
            )
        raise _ErroNaLinhaDeComando(f"Não entendi a linha de comando. O que fazer: {VEJA_A_AJUDA}")


VEJA_A_AJUDA = "veja as opções com python src/montar_site.py --ajuda."


def _ler_opcoes(argv):
    leitor = _LeitorDeOpcoes(
        prog="montar_site.py",
        usage="%(prog)s ENTRADA --saida PASTA [--versao NOME]",
        description="Monta o site do mapa a partir das saídas do agregador.",
        formatter_class=_Formatador,
        add_help=False,
    )
    leitor.add_argument("entrada", nargs="?", metavar="ENTRADA",
                        help="pasta com quadrados.geojson, quadrados.csv, ruas.csv e resumo.txt")
    leitor.add_argument("--saida", metavar="PASTA", help="pasta onde gravar o site")
    leitor.add_argument("--versao", metavar="NOME",
                        help="nome da versão publicada, que aparece no site (ex.: v2026.11.06)")
    leitor.add_argument("-h", "--ajuda", action="help", help="mostra esta ajuda e sai")
    opcoes = leitor.parse_args(argv)
    faltas = []
    if opcoes.entrada is None:
        faltas.append(
            "Falta a pasta de entrada. O que fazer: escreva a pasta das saídas do agregador "
            "logo depois de montar_site.py, por exemplo dados/saida."
        )
    if opcoes.saida is None:
        faltas.append(
            "Falta a --saida. O que fazer: informe a pasta onde gravar o site, "
            "por exemplo --saida dados/site."
        )
    if faltas:
        raise _ErroNaLinhaDeComando("\n".join(faltas))
    return opcoes


def main(argv=None):
    try:
        opcoes = _ler_opcoes(argv)
    except _ErroNaLinhaDeComando as erro:
        for linha in str(erro).splitlines():
            print(f"ERRO: {linha}", file=sys.stderr)
        return 2
    try:
        montar_site(opcoes.entrada, opcoes.saida, versao=opcoes.versao)
    except FileNotFoundError:
        print(
            f"ERRO: não achei a pasta {opcoes.entrada}. "
            f"O que fazer: confira o caminho da pasta onde o agregador gravou os arquivos.",
            file=sys.stderr,
        )
        return 1
    except (ValueError, UnicodeDecodeError) as erro:  # inclui EntradaInvalida
        if isinstance(erro, UnicodeDecodeError):
            erro = "um dos arquivos de entrada não está em UTF-8. O que fazer: rode de novo o agregador."
        print(f"ERRO: {erro}", file=sys.stderr)
        return 1
    print(f"Site gravado em {opcoes.saida}.")
    print(
        f"Para ver: python -m http.server 8765 --bind 127.0.0.1 -d {opcoes.saida} "
        f"e abra http://127.0.0.1:8765 no navegador."
    )
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
