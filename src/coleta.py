"""Coleta: soma no BigQuery os chamados do 1746 por rua e por quadrado de 100 m.

Pedido na issue #15. Lê a tabela datario.adm_central_atendimento_1746.chamado (só
leitura), com todos os chamados desde 2010, e faz as contas dentro do BigQuery: só os
totais saem de lá. Nenhum chamado individual nem coordenada de chamado chega ao
computador. Grava, numa pasta, os mesmos arquivos do agregador (issue #7):

- ruas.csv: totais por bairro e rua;
- quadrados.csv e quadrados.geojson: totais por quadrado de 100 m x 100 m;
- ruas.geojson: o desenho de cada rua (do cadastro de logradouros), com os totais;
- resumo.txt: chamados lidos, sem rua, sem coordenada (inclusive fora do município), as datas
  e o cruzamento do prazo (dentro_prazo) com a situação;
- filtros/: as fatias dos filtros do mapa (issue #31), ver abaixo.

Só problema público (issue #26, por privacidade): cada par tipo/subtipo do 1746 está num
grupo da lista de classificação (`_referencias/20261106_classificacao_subtipos/`). Só os
chamados do grupo `publico` entram nas ruas e nos quadrados, e o filtro roda dentro do
BigQuery. Os outros grupos (`denuncia`, `pessoal`, `sem_lugar`, `a_revisar`) e os pares que
não estão na lista ficam fora do mapa; o resumo diz quantos em cada grupo e lista os pares
sem classificação, para completar a lista. Tipo e subtipo são comparados sem os espaços do
começo e do fim, dos dois lados.

Chamado com coordenada fora do município (a mais de 100 m do contorno dos bairros do
Rio, no mar ou longe) não entra em quadrado nenhum: conta como "sem coordenada", com
linha própria no resumo. Na rua, ele continua contando. Sem rua, sem coordenada e fora do
município contam só entre os chamados de problema público.

As regras são as do agregador: total, atendidos, fechados e mediana exata de dias até
fechar, para toda rua e todo quadrado, mesmo com 1 chamado (o mínimo saiu na issue #31). A conta
de latitude e longitude para metros (SIRGAS 2000 / UTM 23S, EPSG:31983) é escrita na
própria consulta e conferida, nos testes, contra o pyproj, que o agregador usa.

Filtros do mapa (issue #31): a pasta filtros/ tem o que o site soma quando um filtro está
ligado. Cada linha é um total: neste quadrado de 100 m, neste dia (ou mês, ou ano), deste
tema, com este status, situação, tipo de situação, prazo e órgão, houve N chamados, dos quais
F fechados. Nenhuma linha tem número de chamado, coordenada, rua, subtipo, hora, data de
fechamento ou dias até fechar. São três tipos de fatia, para o site baixar só o que precisa:
- AAAA-MM.json: um mês, com o dia de abertura (data_inicio);
- AAAA.json: um ano, sem o dia;
- tudo.json: todos os anos, sem data.
O indice.json tem as listas (quadrados, temas, estados, prazos, órgãos), os meses e anos, o
primeiro e o último dia com chamados e a caixa de cada bairro (do cadastro de bairros), e
cada fatia guarda só a posição nessas listas, em colunas (FORMATO_DAS_FATIAS).

Antes de rodar, a coleta faz uma simulação (dry run), mostra quantos GB vai ler e para
se passar do limite. O login é o Google do responsável, pelo navegador: nenhuma senha
nem chave fica no código ou em arquivo do projeto.

Uso, a partir da raiz do repositório:

    .venv/Scripts/python src/coleta.py --projeto ID_DO_PROJETO
    (opcional) --saida dados/coleta   pasta dos arquivos (padrão: dados/coleta)
    (opcional) --limite-gb 10         para antes de rodar se a consulta for ler mais que isso
                                      (no PowerShell, com ponto: 0.5; 0,001 chega como 0,1)
    (opcional) --classificacao ARQUIVO  outra lista de classificação (padrão: a do projeto)
    Para ver as opções: --ajuda

O --projeto é o projeto do Google Cloud que roda a consulta (o do sandbox gratuito).
"""

import argparse
import csv
import io
import json
import math
import sys
from array import array
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pydata_google_auth
from google.api_core import exceptions as erros_do_google
from google.auth import exceptions as erros_do_login
from google.cloud import bigquery

from agregador import (
    CABECALHO_QUADRADOS,
    CABECALHO_RUAS,
    CASAS_DA_MEDIANA,
    CASAS_DO_GEOJSON,
    LADO_DO_QUADRADO,
    SITUACAO_ATENDIDO,
    ErroNaLinhaDeComando,
    Formatador,
    LeitorDeOpcoes,
    gravar_quadrados,
    gravar_ruas,
    numeros,
    opcao_do_minimo_que_saiu,
)

# ---- Regras da coleta (mudou uma? registre em decisoes.md) ----------------------------

# Tabelas da Prefeitura no BigQuery (só leitura).
TABELA_CHAMADOS = "datario.adm_central_atendimento_1746.chamado"
TABELA_LOGRADOUROS = "datario.dados_mestres.logradouro"  # um trecho de rua por linha
TABELA_BAIRROS = "datario.dados_mestres.bairro"

# Chamado com coordenada a mais que isso (em metros) do contorno dos bairros do Rio conta
# como "sem coordenada" (fora do município). A folga cobre a beira-mar e as frestas
# entre bairros, e não passa do lado de um quadrado.
TOLERANCIA_DO_MUNICIPIO = 100

# Código de logradouro que conta como "sem rua", além de vazio.
LOGRADOURO_VAZIO = "0"

# Limite de leitura de cada coleta, em GB. O sandbox gratuito tem 1 TB por mês.
LIMITE_GB_PADRAO = 10

# Pasta padrão dos arquivos: dentro de dados/, que não vai para o GitHub.
RAIZ = Path(__file__).resolve().parent.parent
PASTA_PADRAO = RAIZ / "dados" / "coleta"

# Lista de classificação dos pares tipo/subtipo (issue #26). Só o GRUPO_DO_MAPA entra no mapa.
CLASSIFICACAO_PADRAO = (
    RAIZ / "_referencias" / "20261106_classificacao_subtipos" / "grupos_subtipos_1746.csv"
)
CABECALHO_DA_LISTA = ["grupo", "tipo", "subtipo", "motivo"]
GRUPO_DO_MAPA = "publico"
GRUPOS_FORA_DO_MAPA = ["denuncia", "pessoal", "sem_lugar", "a_revisar"]
GRUPOS = [GRUPO_DO_MAPA, *GRUPOS_FORA_DO_MAPA]
SEM_CLASSIFICACAO = "sem classificação"  # par que não está na lista

# Filtros do mapa (issue #31): as colunas da tabela que viram filtro, com o nome que têm
# nas consultas e nas fatias. O tema é o `tipo`, só dos chamados do grupo publico.
COLUNAS_DOS_FILTROS = {
    "tema": "tipo",
    "status": "status",
    "situacao": "situacao",
    "tipo_situacao": "tipo_situacao",
    "prazo": "dentro_prazo",
    "orgao": "nome_unidade_organizacional",
}
DIMENSOES = list(COLUNAS_DOS_FILTROS)
PASTA_DOS_FILTROS = "filtros"
EXTENSAO_DAS_FATIAS = ".json"  # o único nome de arquivo .json da coleta: as fatias e o índice

# Colunas de cada fatia, nesta ordem. "q" é a posição do quadrado na lista do índice, escrita
# como diferença para a linha anterior (a fatia vem em ordem de quadrado); "d" é o dia do
# mês (só nas fatias de mês); "t", "e", "p" e "o" são as posições do tema, do estado (status,
# situação e tipo de situação juntos), do prazo e do órgão nas listas do índice; "n" são os
# chamados e "f", os fechados.
FORMATO_DAS_FATIAS = ["q", "d", "t", "e", "p", "o", "n", "f"]

# Permissão pedida no login Google: rodar consultas no BigQuery.
ESCOPOS = ["https://www.googleapis.com/auth/bigquery"]

# Grade em metros: SIRGAS 2000 / UTM zona 23S (EPSG:31983), a mesma do agregador.
# Elipsoide GRS 80, meridiano central 45° oeste.
SEMIEIXO_MAIOR = 6378137.0
ACHATAMENTO = 1 / 298.257222101
MERIDIANO_CENTRAL = -45.0
FATOR_DE_ESCALA = 0.9996
FALSO_LESTE = 500000.0
FALSO_NORTE = 10000000.0

# ---------------------------------------------------------------------------------------

GB = 1024**3


def _passos_metros():
    """A conta de latitude e longitude (graus) para x e y (metros), em SQL, passo a passo.

    É a projeção transversa de Mercator pela série de Krüger até a 4ª ordem (Karney,
    2011), a mesma que o pyproj usa: no Rio, a diferença fica abaixo de 1 micrômetro.
    Cada passo é (nome, expressão SQL), e um passo pode usar os anteriores. Só entram
    funções que o BigQuery e o DuckDB (usado nos testes) têm com o mesmo nome.
    """
    n = ACHATAMENTO / (2 - ACHATAMENTO)
    excentricidade = 2 * math.sqrt(n) / (1 + n)
    raio = SEMIEIXO_MAIOR / (1 + n) * (1 + n**2 / 4 + n**4 / 64)
    alfa = [
        n / 2 - 2 * n**2 / 3 + 5 * n**3 / 16 + 41 * n**4 / 180,
        13 * n**2 / 48 - 3 * n**3 / 5 + 557 * n**4 / 1440,
        61 * n**3 / 240 - 103 * n**4 / 140,
        49561 * n**4 / 161280,
    ]
    k = FATOR_DE_ESCALA * raio
    rad = math.pi / 180
    soma_x = " + ".join(
        f"{a!r} * COS({2 * j} * xi) * SINH({2 * j} * eta)" for j, a in enumerate(alfa, 1)
    )
    soma_y = " + ".join(
        f"{a!r} * SIN({2 * j} * xi) * COSH({2 * j} * eta)" for j, a in enumerate(alfa, 1)
    )
    e = repr(excentricidade)
    return [
        ("fi", f"latitude * {rad!r}"),
        ("lam", f"(longitude - ({MERIDIANO_CENTRAL!r})) * {rad!r}"),
        ("t", f"SINH(ATANH(SIN(fi)) - {e} * ATANH({e} * SIN(fi)))"),
        ("xi", "ATAN2(t, COS(lam))"),
        ("eta", "ATANH(SIN(lam) / SQRT(1 + t * t))"),
        ("x", f"{FALSO_LESTE!r} + {k!r} * (eta + {soma_x})"),
        ("y", f"{FALSO_NORTE!r} + {k!r} * (xi + {soma_y})"),
    ]


PASSOS_METROS = _passos_metros()


@dataclass(frozen=True)
class Dialeto:
    """O que muda de um banco de dados para outro. Os testes usam um dialeto do DuckDB."""

    tabela: Callable[[str], str]  # nome da tabela como vai na consulta
    mediana: str  # mediana exata de {coluna} em cada {grupo}, como função de janela
    segundos: str  # segundos de {inicio} a {fim}
    inteiro: str  # tipo de número inteiro
    desenho: str  # junta os trechos de {coluna} num desenho só, em GeoJSON
    contorno: str  # junta os bairros de {coluna} num contorno só, o do município
    dentro: str  # se o ponto {lon}, {lat} está no {contorno} do município, com a {tolerancia}
    texto: Callable[[str], str]  # um texto escrito na consulta, entre apóstrofos
    pares: str  # tabela de pares (tipo, subtipo) escrita na consulta, com as {linhas}
    caixa: str  # a caixa (xmin, ymin, xmax, ymax) dos desenhos de {coluna} juntos


def _texto_no_bigquery(valor):
    """Texto entre apóstrofos, com barra invertida antes do apóstrofo e da barra invertida."""
    return "'" + valor.replace("\\", "\\\\").replace("'", "\\'") + "'"


BIGQUERY = Dialeto(
    tabela=lambda nome: f"`{nome}`",
    mediana="PERCENTILE_CONT({coluna}, 0.5) OVER (PARTITION BY {grupo})",
    segundos="DATETIME_DIFF({fim}, {inicio}, SECOND)",
    inteiro="INT64",
    desenho="ST_ASGEOJSON(ST_UNION_AGG({coluna}))",
    contorno="ST_UNION_AGG({coluna})",
    # SAFE: coordenada impossível (latitude acima de 90°) vira "fora", sem parar a consulta.
    dentro="ST_DWITHIN(SAFE.ST_GEOGPOINT({lon}, {lat}), {contorno}, {tolerancia})",
    texto=_texto_no_bigquery,
    pares="UNNEST(ARRAY<STRUCT<tipo STRING, subtipo STRING>>[{linhas}])",
    caixa="ST_BOUNDINGBOX(ST_UNION_AGG({coluna}))",
)

# Colunas que cada consulta devolve. Qualquer outra faz a coleta parar.
COLUNAS_DO_RESUMO = ["lidos", "problema_publico", "sem_rua", "rua_fora_do_cadastro",
                     "sem_coordenada", "coordenada_fora_do_municipio", "mais_recente"]
COLUNAS_DO_DESENHO = ["bairro", "rua", "desenho"]
COLUNAS_POR_SUBTIPO = ["tipo", "subtipo", "chamados"]
COLUNAS_DO_PRAZO = ["prazo", "situacao", "chamados"]
COLUNAS_DAS_CAIXAS = ["bairro", "oeste", "sul", "leste", "norte"]
COLUNAS = {
    "ruas": CABECALHO_RUAS,
    "quadrados": CABECALHO_QUADRADOS,
    "resumo": COLUNAS_DO_RESUMO,
    "desenho_das_ruas": COLUNAS_DO_DESENHO,
    "por_subtipo": COLUNAS_POR_SUBTIPO,
    "prazo_por_situacao": COLUNAS_DO_PRAZO,
    "caixas_dos_bairros": COLUNAS_DAS_CAIXAS,
    "filtros_por_dia": ["quadrado", "dia", *DIMENSOES, "chamados", "fechados"],
    "filtros_por_ano": ["quadrado", "ano", *DIMENSOES, "chamados", "fechados"],
    "filtros_tudo": ["quadrado", *DIMENSOES, "chamados", "fechados"],
}
# As três consultas dos filtros têm quase uma linha por chamado: são lidas aos poucos.
CONSULTAS_DOS_FILTROS = ["filtros_por_dia", "filtros_por_ano", "filtros_tudo"]


class LimiteExcedido(ValueError):
    """A simulação mostrou que a consulta vai ler mais que o limite."""


class ListaInvalida(ValueError):
    """A lista de classificação falta ou está malformada. A mensagem diz o que fazer."""


# ---- Lista de classificação -----------------------------------------------------------


def ler_classificacao(caminho):
    """Lê a lista de classificação: {(tipo, subtipo): grupo}, sem os espaços das pontas.

    Um par que só se repete por causa dos espaços conta uma vez. Lista que falta ou está
    malformada faz a coleta parar com ListaInvalida, antes de abrir o BigQuery.
    """
    caminho = Path(caminho)
    corrija = (f"O que fazer: corrija a lista em {caminho} (colunas grupo;tipo;subtipo;motivo, "
               f"separadas por ponto e vírgula) e rode de novo.")
    if not caminho.is_file():
        raise ListaInvalida(
            f"Não encontrei a lista de classificação em {caminho}. O que fazer: confira o "
            f"caminho do --classificacao; sem ele, a coleta usa a lista do projeto, em "
            f"{CLASSIFICACAO_PADRAO.relative_to(RAIZ).as_posix()}."
        )
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise ListaInvalida(
            f"A lista de classificação ({caminho}) não está em UTF-8. O que fazer: salve de "
            f"novo em UTF-8 (no Excel: Salvar como › CSV UTF-8) e rode de novo."
        ) from None
    linhas = csv.reader(io.StringIO(texto, newline=""), delimiter=";")
    cabecalho = [coluna.strip() for coluna in next(linhas, [])]
    if cabecalho != CABECALHO_DA_LISTA:
        raise ListaInvalida(
            f"A lista de classificação não começa com o cabeçalho "
            f"{';'.join(CABECALHO_DA_LISTA)}. {corrija}"
        )
    classificacao, onde = {}, {}
    for numero, linha in enumerate(linhas, start=2):
        if not linha:
            continue
        if len(linha) != len(CABECALHO_DA_LISTA):
            raise ListaInvalida(
                f"A linha {numero} da lista de classificação tem {len(linha)} colunas, e não "
                f"{len(CABECALHO_DA_LISTA)}. {corrija}"
            )
        grupo, tipo, subtipo = (valor.strip() for valor in linha[:3])
        if grupo not in GRUPOS:
            raise ListaInvalida(
                f"A linha {numero} da lista de classificação tem o grupo \"{grupo}\", que não "
                f"existe. Os grupos são: {', '.join(GRUPOS)}. {corrija}"
            )
        if not tipo:
            raise ListaInvalida(f"A linha {numero} da lista de classificação está sem tipo. {corrija}")
        par = (tipo, subtipo)
        if par in classificacao and classificacao[par] != grupo:
            raise ListaInvalida(
                f"O par \"{tipo} / {subtipo}\" está em dois grupos na lista de classificação, nas "
                f"linhas {onde[par]} e {numero} ({classificacao[par]} e {grupo}). {corrija}"
            )
        classificacao.setdefault(par, grupo)
        onde.setdefault(par, numero)
    if GRUPO_DO_MAPA not in classificacao.values():
        raise ListaInvalida(
            f"A lista de classificação não tem nenhum par do grupo {GRUPO_DO_MAPA}: o mapa "
            f"sairia vazio. {corrija}"
        )
    return classificacao


# ---- Consultas ------------------------------------------------------------------------


def _sem_espacos(coluna):
    """Tipo ou subtipo sem os espaços das pontas; vazio quando não há."""
    return f"COALESCE(TRIM({coluna}), '')"


def montar_consultas(dialeto, classificacao):
    """As consultas da coleta, em SQL, com os nomes de COLUNAS.

    Todas devolvem só linhas somadas. A tabela de chamados é lida em todas, menos no
    desenho das ruas e nas caixas dos bairros, que vêm só dos cadastros. Os pares do grupo
    publico da
    `classificacao` vão escritos na consulta: o filtro roda dentro do BigQuery.
    """
    tabela = dialeto.tabela
    linhas = ", ".join(
        f"({dialeto.texto(tipo)}, {dialeto.texto(subtipo)})"
        for (tipo, subtipo), grupo in sorted(classificacao.items()) if grupo == GRUPO_DO_MAPA
    )
    pares_publicos = dialeto.pares.format(linhas=linhas)
    dentro = dialeto.dentro.format(lon="c.longitude", lat="c.latitude",
                                   contorno="municipio.contorno",
                                   tolerancia=TOLERANCIA_DO_MUNICIPIO)
    dias = dialeto.segundos.format(inicio="c.data_inicio", fim="c.data_fim") + " / 86400"

    def mediana(grupo):
        return dialeto.mediana.format(coluna="dias", grupo=grupo)

    def totais(grupo):
        return f"""
    COUNT(*) AS chamados,
    SUM(CASE WHEN atendido THEN 1 ELSE 0 END) AS atendidos,
    COUNT(dias) AS fechados,
    MAX(mediana) AS mediana_dias_ate_fechar
  FROM (SELECT {grupo}, atendido, dias, {mediana(grupo)} AS mediana FROM"""

    dimensoes = ", ".join(DIMENSOES)
    filtros_lidos = ",\n".join(
        f"    {_sem_espacos('c.' + coluna)} AS {nome}" for nome, coluna in COLUNAS_DOS_FILTROS.items()
    )

    bairros = f"""bairros AS (
  SELECT CAST(id_bairro AS STRING) AS id_bairro, MIN(TRIM(nome)) AS bairro
  FROM {tabela(TABELA_BAIRROS)}
  GROUP BY 1
)"""

    # Um chamado por linha, já com bairro e rua pelo nome. Nada daqui sai do BigQuery.
    chamados = f"""WITH {bairros},
logradouros AS (
  SELECT CAST(id_logradouro AS STRING) AS id_logradouro, MIN(TRIM(nome_completo)) AS rua
  FROM {tabela(TABELA_LOGRADOUROS)}
  GROUP BY 1
),
municipio AS (
  SELECT {dialeto.contorno.format(coluna="geometry")} AS contorno
  FROM {tabela(TABELA_BAIRROS)}
),
pares_publicos AS (
  SELECT tipo, subtipo FROM {pares_publicos}
),
chamados_lidos AS (
  SELECT
    p.tipo IS NOT NULL AS e_publico,
    c.data_inicio,
{filtros_lidos},
    COALESCE(TRIM(c.tipo_situacao) = '{SITUACAO_ATENDIDO}', FALSE) AS atendido,
    {dias} AS dias,
    COALESCE(b.bairro, '') AS bairro,
    c.logradouro_valido,
    NULLIF(l.rua, '') AS rua,
    CASE WHEN c.latitude = 0 OR c.longitude = 0 THEN NULL ELSE c.latitude END AS latitude,
    CASE WHEN c.latitude = 0 OR c.longitude = 0 THEN NULL ELSE c.longitude END AS longitude
  FROM (
    SELECT *,
      CASE WHEN TRIM(id_logradouro) IN ('', '{LOGRADOURO_VAZIO}') THEN NULL
           ELSE TRIM(id_logradouro) END AS logradouro_valido
    FROM {tabela(TABELA_CHAMADOS)}
  ) AS c
  LEFT JOIN bairros AS b ON b.id_bairro = c.id_bairro
  LEFT JOIN logradouros AS l ON l.id_logradouro = c.logradouro_valido
  LEFT JOIN pares_publicos AS p
    ON p.tipo = {_sem_espacos("c.tipo")} AND p.subtipo = {_sem_espacos("c.subtipo")}
),
no_municipio AS (
  SELECT c.*,
    CASE WHEN c.e_publico THEN COALESCE({dentro}, FALSE) ELSE FALSE END AS dentro_do_municipio
  FROM chamados_lidos AS c CROSS JOIN municipio
),
chamados AS (
  SELECT
    e_publico, data_inicio, {dimensoes}, atendido, dias, bairro, logradouro_valido, rua,
    latitude IS NOT NULL AND longitude IS NOT NULL AND NOT dentro_do_municipio
      AS fora_do_municipio,
    CASE WHEN dentro_do_municipio THEN latitude END AS latitude,
    CASE WHEN dentro_do_municipio THEN longitude END AS longitude
  FROM no_municipio
)"""

    ruas = f"""{chamados}
SELECT bairro, rua,{totais("bairro, rua")} chamados WHERE e_publico AND rua IS NOT NULL) AS por_rua
GROUP BY bairro, rua"""

    passos = []
    anterior = "com_coordenada"
    for nome, expressao in PASSOS_METROS:
        passos.append(f"passo_{nome} AS (SELECT *, {expressao} AS {nome} FROM {anterior})")
        anterior = f"passo_{nome}"
    passos = ",\n".join(passos)
    lado = LADO_DO_QUADRADO

    def canto(eixo):
        return f"CAST(CAST(FLOOR({eixo} / {lado}) * {lado} AS {dialeto.inteiro}) AS STRING)"

    # Um chamado com coordenada por linha, já no quadrado. Nada daqui sai do BigQuery.
    no_quadrado = f"""{chamados},
com_coordenada AS (
  SELECT atendido, dias, latitude, longitude, data_inicio, {dimensoes} FROM chamados
  WHERE e_publico AND latitude IS NOT NULL AND longitude IS NOT NULL
),
{passos},
no_quadrado AS (
  SELECT atendido, dias, CAST(data_inicio AS DATE) AS dia, {dimensoes},
    CONCAT({canto("x")}, '_', {canto("y")}) AS quadrado
  FROM {anterior}
)"""

    quadrados = f"""{no_quadrado}
SELECT quadrado,{totais("quadrado")} no_quadrado) AS por_quadrado
GROUP BY quadrado"""

    def filtros(*tempo):
        # Em ordem de tempo primeiro: a coleta grava uma fatia por vez, sem guardar as outras.
        nomes_do_tempo = [t.split(" AS ")[-1] for t in tempo]
        colunas = ", ".join(["quadrado", *tempo, dimensoes])
        nomes = ", ".join(["quadrado", *nomes_do_tempo, dimensoes])
        ordem = ", ".join([*nomes_do_tempo, "quadrado", dimensoes])
        return f"""{no_quadrado}
SELECT {colunas}, COUNT(*) AS chamados, COUNT(dias) AS fechados
FROM no_quadrado
GROUP BY {nomes}
ORDER BY {ordem}"""

    filtros_por_dia = filtros("dia")
    filtros_por_ano = filtros("EXTRACT(YEAR FROM dia) AS ano")
    filtros_tudo = filtros()

    # Quantos chamados de problema público em cada par prazo/situação, na cidade toda.
    prazo_por_situacao = f"""{chamados}
SELECT prazo, situacao, COUNT(*) AS chamados
FROM chamados
WHERE e_publico
GROUP BY prazo, situacao"""

    # A caixa de cada bairro, do cadastro de bairros, para a busca de bairro do site.
    caixas = f"""SELECT b.bairro, b.caixa.xmin AS oeste, b.caixa.ymin AS sul,
  b.caixa.xmax AS leste, b.caixa.ymax AS norte
FROM (
  SELECT TRIM(nome) AS bairro, {dialeto.caixa.format(coluna="geometry")} AS caixa
  FROM {tabela(TABELA_BAIRROS)}
  WHERE geometry IS NOT NULL AND TRIM(nome) != ''
  GROUP BY 1
) AS b"""

    # Sem rua, sem coordenada e fora do município: só entre os chamados de problema público.
    resumo = f"""{chamados}
SELECT
  COUNT(*) AS lidos,
  COALESCE(SUM(CASE WHEN e_publico THEN 1 ELSE 0 END), 0) AS problema_publico,
  COALESCE(SUM(CASE WHEN e_publico AND rua IS NULL THEN 1 ELSE 0 END), 0) AS sem_rua,
  COALESCE(SUM(CASE WHEN e_publico AND rua IS NULL AND logradouro_valido IS NOT NULL
                    THEN 1 ELSE 0 END), 0)
    AS rua_fora_do_cadastro,
  COALESCE(SUM(CASE WHEN e_publico AND (latitude IS NULL OR longitude IS NULL)
                    THEN 1 ELSE 0 END), 0)
    AS sem_coordenada,
  COALESCE(SUM(CASE WHEN e_publico AND fora_do_municipio THEN 1 ELSE 0 END), 0)
    AS coordenada_fora_do_municipio,
  MAX(data_inicio) AS mais_recente
FROM chamados"""

    # Quantos chamados há em cada par tipo/subtipo, na cidade toda: sem lugar nem data.
    por_subtipo = f"""SELECT
  {_sem_espacos("tipo")} AS tipo,
  {_sem_espacos("subtipo")} AS subtipo,
  COUNT(*) AS chamados
FROM {tabela(TABELA_CHAMADOS)}
GROUP BY 1, 2"""

    desenho = f"""WITH {bairros}
SELECT
  COALESCE(b.bairro, '') AS bairro,
  TRIM(l.nome_completo) AS rua,
  {dialeto.desenho.format(coluna="l.geometry")} AS desenho
FROM {tabela(TABELA_LOGRADOUROS)} AS l
LEFT JOIN bairros AS b ON b.id_bairro = CAST(l.id_bairro AS STRING)
WHERE l.geometry IS NOT NULL AND TRIM(l.nome_completo) != ''
GROUP BY 1, 2"""

    return {"ruas": ruas, "quadrados": quadrados, "resumo": resumo, "desenho_das_ruas": desenho,
            "por_subtipo": por_subtipo, "prazo_por_situacao": prazo_por_situacao,
            "caixas_dos_bairros": caixas, "filtros_por_dia": filtros_por_dia,
            "filtros_por_ano": filtros_por_ano, "filtros_tudo": filtros_tudo}


# ---- Coleta ---------------------------------------------------------------------------


@dataclass
class Soma:
    """Os números de uma rua ou de um quadrado, já somados no BigQuery."""

    chamados: int
    atendidos: int
    fechados: int
    mediana: float | None

    @classmethod
    def da_linha(cls, linha):
        mediana = linha["mediana_dias_ate_fechar"]
        return cls(
            chamados=int(linha["chamados"]),
            atendidos=int(linha["atendidos"]),
            fechados=int(linha["fechados"]),
            mediana=None if mediana is None else round(float(mediana), CASAS_DA_MEDIANA),
        )


@dataclass
class Resumo:
    """O que a coleta leu."""

    gb_lidos: float = 0.0
    lidos: int = 0
    problema_publico: int = 0  # os que entram no mapa
    fora_do_mapa: dict = field(default_factory=dict)  # grupo (ou "sem classificação") -> chamados
    sem_classificacao: list = field(default_factory=list)  # (tipo, subtipo, chamados)
    sem_rua: int = 0
    rua_fora_do_cadastro: int = 0
    sem_coordenada: int = 0
    coordenada_fora_do_municipio: int = 0
    mais_recente: date | None = None
    data_da_coleta: date | None = None
    ruas: int = 0
    ruas_com_desenho: int = 0
    quadrados: int = 0
    prazo_por_situacao: list = field(default_factory=list)  # (prazo, situação, chamados)

    def texto(self):
        return "\n".join([
            "Resumo da coleta (chamados do 1746)",
            f"fonte: {TABELA_CHAMADOS} (BigQuery, só leitura)",
            "período: todos",
            f"chamados lidos: {self.lidos}",
            f"chamados de problema público (entram no mapa): {self.problema_publico}",
            "fora do mapa, por grupo:",
            *(f"  {grupo}: {self.fora_do_mapa.get(grupo, 0)}"
              for grupo in [*GRUPOS_FORA_DO_MAPA, SEM_CLASSIFICACAO]),
            f"pares tipo/subtipo sem classificação: {len(self.sem_classificacao)}",
            *(f"  - {tipo} / {subtipo or '(sem subtipo)'}: {chamados}"
              for tipo, subtipo, chamados in self.sem_classificacao),
            "entre os chamados de problema público:",
            f"sem rua: {self.sem_rua}",
            f"  dos quais com rua fora do cadastro de logradouros: {self.rua_fora_do_cadastro}",
            f"sem coordenada: {self.sem_coordenada}",
            f"  dos quais com coordenada fora do município: {self.coordenada_fora_do_municipio}",
            f"chamado mais recente na base: {self.mais_recente or 'nenhum'}",
            f"data da coleta: {self.data_da_coleta}",
            f"ruas: {self.ruas}",
            f"ruas com desenho: {self.ruas_com_desenho}",
            f"quadrados: {self.quadrados}",
            CABECALHO_DO_PRAZO,
            *(f"  {prazo or VAZIO} / {situacao or VAZIO}: {chamados}"
              for prazo, situacao, chamados in self.prazo_por_situacao),
            f"GB lidos no BigQuery (simulação): {_gb(self.gb_lidos)}",
        ]) + "\n"


# O cruzamento do prazo com a situação, no resumo (issue #31). O montador do site lê este bloco.
CABECALHO_DO_PRAZO = "prazo (dentro_prazo) por situação, entre os chamados de problema público:"
VAZIO = "(vazio)"


def _gb(valor):
    """GB com vírgula: uma casa a partir de 1 GB; abaixo, casas até mostrar 2 algarismos."""
    if valor == 0:
        return "0"
    if valor >= 1:
        texto = f"{valor:.1f}"
    else:
        casas = 1 - math.floor(math.log10(valor))
        texto = f"{valor:.{casas}f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def _como_data(valor):
    if isinstance(valor, datetime):
        return valor.date()
    return valor


def _contar_por_grupo(resumo, linhas, classificacao):
    """Soma, no resumo, os chamados de cada grupo a partir da contagem por par tipo/subtipo.

    Confere a conta com a do BigQuery: se não bater (o total lido ou os de problema
    público), para sem gravar nada.
    """
    fora = {grupo: 0 for grupo in [*GRUPOS_FORA_DO_MAPA, SEM_CLASSIFICACAO]}
    publicos, total, sem_classificacao = 0, 0, []
    for linha in linhas:
        tipo, subtipo, chamados = linha["tipo"], linha["subtipo"], int(linha["chamados"])
        total += chamados
        grupo = classificacao.get((tipo, subtipo))
        if grupo is None:
            fora[SEM_CLASSIFICACAO] += chamados
            sem_classificacao.append((tipo, subtipo, chamados))
        elif grupo == GRUPO_DO_MAPA:
            publicos += chamados
        else:
            fora[grupo] += chamados
    if total != resumo.lidos or publicos != resumo.problema_publico:
        raise ValueError(
            f"A conta por grupo não bate com a do mapa: {total} chamados lidos e {publicos} de "
            f"problema público na contagem por tipo e subtipo, contra {resumo.lidos} e "
            f"{resumo.problema_publico} no resumo. Nada foi gravado. O que fazer: rode a coleta "
            f"de novo; se repetir, abra um \"Defeito numa ferramenta\" com esta mensagem."
        )
    resumo.fora_do_mapa = fora
    resumo.sem_classificacao = sorted(sem_classificacao, key=lambda par: (-par[2], par[0], par[1]))


def coletar(cliente, saida, *, classificacao, limite_gb=LIMITE_GB_PADRAO,
            dialeto=BIGQUERY, hoje=None, avisar=print):
    """Roda as consultas no BigQuery (`cliente`) e grava os totais na pasta `saida`.

    Só os chamados do grupo publico da `classificacao` ({(tipo, subtipo): grupo}, como
    devolve ler_classificacao) entram nas ruas e nos quadrados. Primeiro simula todas as
    consultas e para, sem rodar nenhuma, se juntas forem ler mais que `limite_gb`.
    Devolve o Resumo.
    """
    if limite_gb <= 0:
        raise ValueError(
            "O --limite-gb precisa ser maior que zero. "
            f"O que fazer: informe o limite em GB, por exemplo --limite-gb {LIMITE_GB_PADRAO}."
        )
    consultas = montar_consultas(dialeto, classificacao)
    limite_bytes = int(limite_gb * GB)

    simulacao = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    total = sum(
        cliente.query(sql, job_config=simulacao).total_bytes_processed or 0
        for sql in consultas.values()
    )
    resumo = Resumo(gb_lidos=total / GB, data_da_coleta=hoje or date.today())
    avisar(
        f"Simulação: a coleta vai ler {_gb(resumo.gb_lidos)} GB no BigQuery "
        f"(limite: {_gb(limite_gb)} GB)."
    )
    if total > limite_bytes:
        raise LimiteExcedido(
            f"A coleta vai ler {_gb(resumo.gb_lidos)} GB, acima do limite de {_gb(limite_gb)} GB. "
            f"Nada foi rodado. O que fazer: confira se a consulta mudou; se o tamanho estiver "
            f"certo, rode de novo com um limite maior, por exemplo --limite-gb "
            f"{math.ceil(resumo.gb_lidos)}."
        )

    # Primeiro roda todas e confere as colunas: se uma estiver errada, nada é gravado.
    resultados = {}
    for nome, sql in consultas.items():
        avisar(f"Rodando a consulta {nome}...")
        configuracao = bigquery.QueryJobConfig(maximum_bytes_billed=limite_bytes)
        resultado = cliente.query(sql, job_config=configuracao).result()
        colunas = [campo.name for campo in resultado.schema]
        if colunas != COLUNAS[nome]:
            raise ValueError(
                f"A consulta {nome} devolveu as colunas {', '.join(colunas)}, e não só "
                f"{', '.join(COLUNAS[nome])}. Nada foi gravado. O que fazer: confira a "
                f"consulta em src/coleta.py; nenhuma coluna do chamado pode sair do BigQuery."
            )
        resultados[nome] = resultado
    for nome in consultas:
        if nome not in CONSULTAS_DOS_FILTROS:
            resultados[nome] = [dict(linha.items()) for linha in resultados[nome]]

    ruas = {(linha["bairro"], linha["rua"]): Soma.da_linha(linha) for linha in resultados["ruas"]}
    quadrados = {}
    for linha in resultados["quadrados"]:
        x, y = linha["quadrado"].split("_")
        quadrados[(int(x), int(y))] = Soma.da_linha(linha)
    desenhos = {(linha["bairro"], linha["rua"]): linha["desenho"]
                for linha in resultados["desenho_das_ruas"]}
    (linha,) = resultados["resumo"]
    resumo.lidos = int(linha["lidos"])
    resumo.problema_publico = int(linha["problema_publico"])
    _contar_por_grupo(resumo, resultados["por_subtipo"], classificacao)
    resumo.sem_rua = int(linha["sem_rua"])
    resumo.rua_fora_do_cadastro = int(linha["rua_fora_do_cadastro"])
    resumo.sem_coordenada = int(linha["sem_coordenada"])
    resumo.coordenada_fora_do_municipio = int(linha["coordenada_fora_do_municipio"])
    resumo.mais_recente = _como_data(linha["mais_recente"])
    resumo.ruas = len(ruas)
    resumo.quadrados = len(quadrados)
    resumo.prazo_por_situacao = sorted(
        (linha["prazo"], linha["situacao"], int(linha["chamados"]))
        for linha in resultados["prazo_por_situacao"]
    )

    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    gravar_ruas(saida / "ruas.csv", ruas)
    gravar_quadrados(saida, quadrados)
    resumo.ruas_com_desenho = gravar_desenho_das_ruas(saida / "ruas.geojson", ruas, desenhos)
    gravar_filtros(saida / PASTA_DOS_FILTROS, sorted(quadrados), resultados, avisar)
    (saida / "resumo.txt").write_text(resumo.texto(), encoding="utf-8")
    return resumo


def _arredondar(valor):
    if isinstance(valor, float):
        return round(valor, CASAS_DO_GEOJSON)
    if isinstance(valor, list):
        return [_arredondar(item) for item in valor]
    if isinstance(valor, dict):
        return {chave: _arredondar(item) for chave, item in valor.items()}
    return valor


def gravar_desenho_das_ruas(caminho, ruas, desenhos):
    """Grava ruas.geojson: cada rua com desenho no cadastro, com os totais. Devolve quantas."""
    features = []
    for bairro, rua in sorted(ruas):
        desenho = desenhos.get((bairro, rua))
        if desenho is None:
            continue
        features.append({
            "type": "Feature",
            "properties": dict(zip(CABECALHO_RUAS, [bairro, rua, *numeros(ruas[(bairro, rua)])])),
            "geometry": _arredondar(json.loads(desenho)),
        })
    geojson = {"type": "FeatureCollection", "features": features}
    caminho.write_text(json.dumps(geojson, ensure_ascii=False, separators=(",", ":")),
                       encoding="utf-8")
    return len(features)


# ---- Filtros do mapa (issue #31) ------------------------------------------------------


class Lista:
    """Uma lista de valores (temas, estados, prazos, órgãos): cada valor novo ganha a próxima posição."""

    def __init__(self):
        self.posicao = {}

    def __call__(self, valor):
        return self.posicao.setdefault(valor, len(self.posicao))

    def valores(self):
        return list(self.posicao)


class Fatia:
    """As linhas de uma fatia, em colunas de números inteiros."""

    def __init__(self, com_dia):
        self.colunas = {nome: array("l") for nome in FORMATO_DAS_FATIAS if com_dia or nome != "d"}

    def somar(self, valores):
        for nome, valor in valores.items():
            self.colunas[nome].append(valor)

    def __len__(self):
        return len(self.colunas["q"])

    def gravar(self, caminho):
        """Grava em ordem de quadrado, com o "q" escrito como diferença para a linha anterior."""
        # A ordenação é estável: no mesmo quadrado, fica a ordem da consulta.
        ordem = sorted(range(len(self)), key=self.colunas["q"].__getitem__)
        partes = []
        for nome, coluna in self.colunas.items():
            valores = [coluna[i] for i in ordem]
            if nome == "q":
                valores = [valor - anterior for valor, anterior in zip(valores, [0, *valores])]
            partes.append(f'"{nome}":[{",".join(map(str, valores))}]')
        caminho.write_text("{" + ",".join(partes) + "}", encoding="utf-8")


def gravar_filtros(pasta, quadrados, resultados, avisar=print):
    """Grava as fatias dos filtros e o indice.json na `pasta`. Ver o começo deste arquivo."""
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in pasta.glob(f"*{EXTENSAO_DAS_FATIAS}"):  # de uma coleta anterior
        antigo.unlink()
    posicao_do_quadrado = {f"{x}_{y}": i for i, (x, y) in enumerate(quadrados)}
    temas, estados, prazos, orgaos = Lista(), Lista(), Lista(), Lista()

    def valores(linha):
        quadrado = posicao_do_quadrado.get(linha["quadrado"])
        if quadrado is None:
            raise ValueError(
                "Uma fatia dos filtros tem um quadrado que não está em quadrados.csv. Nada do "
                "site muda. O que fazer: rode a coleta de novo; se repetir, abra um \"Defeito "
                "numa ferramenta\" com esta mensagem."
            )
        return {
            "q": quadrado,
            "t": temas(linha["tema"]),
            "e": estados((linha["status"], linha["situacao"], linha["tipo_situacao"])),
            "p": prazos(linha["prazo"]),
            "o": orgaos(linha["orgao"]),
            "n": int(linha["chamados"]),
            "f": int(linha["fechados"]),
        }

    meses, primeiro, ultimo = [], None, None
    mes, fatia = None, None
    for linha in resultados["filtros_por_dia"]:
        dia = _como_data(linha["dia"])
        if (dia.year, dia.month) != mes:
            if fatia is not None:
                fatia.gravar(pasta / f"{mes[0]:04d}-{mes[1]:02d}{EXTENSAO_DAS_FATIAS}")
            mes, fatia = (dia.year, dia.month), Fatia(com_dia=True)
            meses.append(f"{dia.year:04d}-{dia.month:02d}")
            if dia.month == 1 or len(meses) == 1:
                avisar(f"Gravando as fatias de {dia.year}...")
        fatia.somar({**valores(linha), "d": dia.day})
        primeiro, ultimo = primeiro or dia, dia  # a consulta vem em ordem de dia
    if fatia is not None:
        fatia.gravar(pasta / f"{mes[0]:04d}-{mes[1]:02d}{EXTENSAO_DAS_FATIAS}")

    anos, ano, fatia = [], None, None
    for linha in resultados["filtros_por_ano"]:
        if int(linha["ano"]) != ano:
            if fatia is not None:
                fatia.gravar(pasta / f"{ano:04d}{EXTENSAO_DAS_FATIAS}")
            ano, fatia = int(linha["ano"]), Fatia(com_dia=False)
            anos.append(ano)
        fatia.somar(valores(linha))
    if fatia is not None:
        fatia.gravar(pasta / f"{ano:04d}{EXTENSAO_DAS_FATIAS}")

    tudo = Fatia(com_dia=False)
    for linha in resultados["filtros_tudo"]:
        tudo.somar(valores(linha))
    tudo.gravar(pasta / f"tudo{EXTENSAO_DAS_FATIAS}")

    bairros = {
        linha["bairro"]: [round(float(linha[lado]), CASAS_DO_GEOJSON)
                          for lado in ("sul", "oeste", "norte", "leste")]
        for linha in sorted(resultados["caixas_dos_bairros"], key=lambda linha: linha["bairro"])
    }
    indice = {
        "formato": FORMATO_DAS_FATIAS,
        "quadrados": list(posicao_do_quadrado),
        "temas": temas.valores(),
        "estados": [list(estado) for estado in estados.valores()],
        "prazos": prazos.valores(),
        "orgaos": orgaos.valores(),
        "meses": meses,
        "anos": anos,
        "primeiro_dia": primeiro.isoformat() if primeiro else None,
        "ultimo_dia": ultimo.isoformat() if ultimo else None,
        "bairros": bairros,
    }
    (pasta / f"indice{EXTENSAO_DAS_FATIAS}").write_text(json.dumps(indice, ensure_ascii=False, separators=(",", ":")),
                                       encoding="utf-8")


# ---- Login --------------------------------------------------------------------------


def abrir_cliente(projeto):
    """Abre o BigQuery com o login Google do responsável (OAuth, pelo navegador).

    Na primeira vez, o navegador pede o login e a permissão; depois, o login fica guardado
    no perfil do usuário no computador, fora do projeto. Nenhuma chave fica em arquivo.
    """
    credenciais = pydata_google_auth.get_user_credentials(ESCOPOS, use_local_webserver=True)
    return bigquery.Client(project=projeto, credentials=credenciais)


# ---- Linha de comando -----------------------------------------------------------------

VEJA_A_AJUDA = "veja as opções com python src/coleta.py --ajuda."

FALTA = {
    "projeto": (
        "o --projeto",
        "informe o projeto do Google Cloud que roda a consulta (o do sandbox gratuito), "
        "por exemplo --projeto meu-projeto.",
    ),
}

EXEMPLO = {
    "--projeto": "--projeto meu-projeto",
    "--saida": "--saida dados/coleta",
    "--limite-gb": f"--limite-gb {LIMITE_GB_PADRAO}",
    "--classificacao": "--classificacao _referencias/minha_lista.csv",
}


def _ler_limite(texto):
    try:
        limite = float(texto.replace(",", "."))
    except ValueError:
        limite = math.nan
    if not math.isfinite(limite) or limite <= 0:
        raise argparse.ArgumentTypeError(
            f"O --limite-gb tem de ser um número maior que zero, e veio \"{texto}\". "
            f"O que fazer: informe o limite em GB, por exemplo {EXEMPLO['--limite-gb']}."
        )
    return limite


def _leitor_de_opcoes():
    leitor = LeitorDeOpcoes(
        prog="coleta.py",
        usage="%(prog)s --projeto ID [--saida PASTA] [--limite-gb GB] "
              "[--classificacao ARQUIVO]",
        description="Soma no BigQuery os chamados do 1746 por rua e por quadrado de 100 m.",
        formatter_class=Formatador,
        add_help=False,
        exemplos=EXEMPLO,
        veja_a_ajuda=VEJA_A_AJUDA,
    )
    opcoes = leitor.add_argument_group("opções")
    opcoes.add_argument("--projeto", metavar="ID",
                        help="projeto do Google Cloud que roda a consulta (sandbox gratuito)")
    opcao_do_minimo_que_saiu(opcoes)
    opcoes.add_argument("--saida", metavar="PASTA",
                        help="pasta onde gravar os arquivos (padrão: dados/coleta)")
    opcoes.add_argument(
        "--limite-gb", type=_ler_limite, metavar="GB", default=LIMITE_GB_PADRAO,
        help=f"para antes de rodar se a consulta for ler mais que isso (padrão: {LIMITE_GB_PADRAO}); "
             "no PowerShell, escreva com ponto (0.5): com vírgula, 0,001 chega como 0,1",
    )
    opcoes.add_argument(
        "--classificacao", metavar="ARQUIVO",
        help="lista de classificação dos tipos e subtipos (padrão: a do projeto, em _referencias/)",
    )
    opcoes.add_argument("-h", "--ajuda", action="help", help="mostra esta ajuda e sai")
    return leitor


def _ler_opcoes(argv):
    opcoes = _leitor_de_opcoes().parse_args(argv)
    faltam = [nome for nome in FALTA if getattr(opcoes, nome) is None]
    if faltam:
        raise ErroNaLinhaDeComando("\n".join(
            f"Falta {FALTA[nome][0]}. O que fazer: {FALTA[nome][1]}" for nome in faltam
        ))
    return opcoes


def main(argv=None, *, abrir=None, dialeto=BIGQUERY):
    try:
        opcoes = _ler_opcoes(argv)
    except ErroNaLinhaDeComando as erro:
        for linha in str(erro).splitlines():
            print(f"ERRO: {linha}", file=sys.stderr)
        return 2
    saida = Path(opcoes.saida) if opcoes.saida else PASTA_PADRAO
    try:
        classificacao = ler_classificacao(opcoes.classificacao or CLASSIFICACAO_PADRAO)
    except ListaInvalida as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 1
    try:
        cliente = (abrir or abrir_cliente)(opcoes.projeto)
    except (erros_do_login.GoogleAuthError, pydata_google_auth.exceptions.PyDataCredentialsError):
        print(
            "ERRO: não consegui entrar com o login Google. "
            "O que fazer: rode de novo e, no navegador, entre com a sua conta e aceite o acesso ao BigQuery.",
            file=sys.stderr,
        )
        return 1
    try:
        resumo = coletar(cliente, saida, classificacao=classificacao,
                         limite_gb=opcoes.limite_gb, dialeto=dialeto)
    except erros_do_google.GoogleAPIError as erro:
        print(
            f"ERRO: o BigQuery recusou a consulta ({type(erro).__name__}): "
            f"{getattr(erro, 'message', erro)} "
            "O que fazer: confira o --projeto e se o seu login tem acesso ao BigQuery nele.",
            file=sys.stderr,
        )
        return 1
    except ValueError as erro:  # inclui LimiteExcedido
        print(f"ERRO: {erro}", file=sys.stderr)
        return 1
    print(resumo.texto(), end="")
    print(f"Arquivos gravados em {saida}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
