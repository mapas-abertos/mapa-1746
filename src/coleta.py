"""Coleta: soma no BigQuery os chamados do 1746 por rua e por quadrado de 100 m.

Pedido na issue #15. Lê a tabela datario.adm_central_atendimento_1746.chamado (só
leitura), com todos os chamados desde 2010, e faz as contas dentro do BigQuery: só os
totais saem de lá. Nenhum chamado individual nem coordenada de chamado chega ao
computador. Grava, numa pasta, os mesmos arquivos do agregador (issue #7):

- ruas.csv: totais por bairro e rua;
- quadrados.csv e quadrados.geojson: totais por quadrado de 100 m x 100 m;
- ruas.geojson: o desenho de cada rua (do cadastro de logradouros), com os totais;
- resumo.txt: chamados lidos, sem rua, sem coordenada (inclusive fora do município) e as datas.

Chamado com coordenada fora do município (a mais de 100 m do contorno dos bairros do
Rio, no mar ou longe) não entra em quadrado nenhum: conta como "sem coordenada", com
linha própria no resumo. Na rua, ele continua contando.

As regras são as do agregador: total, atendidos, fechados e mediana exata de dias até
fechar; rua ou quadrado com menos chamados que o mínimo sai como "menos de N". A conta
de latitude e longitude para metros (SIRGAS 2000 / UTM 23S, EPSG:31983) é escrita na
própria consulta e conferida, nos testes, contra o pyproj, que o agregador usa.

Antes de rodar, a coleta faz uma simulação (dry run), mostra quantos GB vai ler e para
se passar do limite. O login é o Google do responsável, pelo navegador: nenhuma senha
nem chave fica no código ou em arquivo do projeto.

Uso, a partir da raiz do repositório:

    .venv/Scripts/python src/coleta.py --projeto ID_DO_PROJETO --minimo N
    (opcional) --saida dados/coleta   pasta dos arquivos (padrão: dados/coleta)
    (opcional) --limite-gb 10         para antes de rodar se a consulta for ler mais que isso
                                      (no PowerShell, com ponto: 0.5; 0,001 chega como 0,1)
    Para ver as opções: --ajuda

O --projeto é o projeto do Google Cloud que roda a consulta (o do sandbox gratuito).
O valor do mínimo fica a definir até a consulta jurídica; por isso não há padrão.
"""

import argparse
import json
import math
import sys
from collections.abc import Callable
from dataclasses import dataclass
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
    FALTA as FALTA_NO_AGREGADOR,
    LADO_DO_QUADRADO,
    SITUACAO_ATENDIDO,
    ErroNaLinhaDeComando,
    Formatador,
    LeitorDeOpcoes,
    gravar_quadrados,
    gravar_ruas,
    ler_minimo,
    numeros,
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
PASTA_PADRAO = Path(__file__).resolve().parent.parent / "dados" / "coleta"

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


BIGQUERY = Dialeto(
    tabela=lambda nome: f"`{nome}`",
    mediana="PERCENTILE_CONT({coluna}, 0.5) OVER (PARTITION BY {grupo})",
    segundos="DATETIME_DIFF({fim}, {inicio}, SECOND)",
    inteiro="INT64",
    desenho="ST_ASGEOJSON(ST_UNION_AGG({coluna}))",
    contorno="ST_UNION_AGG({coluna})",
    # SAFE: coordenada impossível (latitude acima de 90°) vira "fora", sem parar a consulta.
    dentro="ST_DWITHIN(SAFE.ST_GEOGPOINT({lon}, {lat}), {contorno}, {tolerancia})",
)

# Colunas que cada consulta devolve. Qualquer outra faz a coleta parar.
COLUNAS_DO_RESUMO = ["lidos", "sem_rua", "rua_fora_do_cadastro", "sem_coordenada",
                     "coordenada_fora_do_municipio", "mais_recente"]
COLUNAS_DO_DESENHO = ["bairro", "rua", "desenho"]
COLUNAS = {
    "ruas": CABECALHO_RUAS,
    "quadrados": CABECALHO_QUADRADOS,
    "resumo": COLUNAS_DO_RESUMO,
    "desenho_das_ruas": COLUNAS_DO_DESENHO,
}


class LimiteExcedido(ValueError):
    """A simulação mostrou que a consulta vai ler mais que o limite."""


# ---- Consultas ------------------------------------------------------------------------


def montar_consultas(dialeto=BIGQUERY):
    """As quatro consultas da coleta, em SQL: {"ruas", "quadrados", "resumo", "desenho_das_ruas"}.

    Todas devolvem só linhas somadas. A tabela de chamados é lida nas três primeiras;
    o desenho das ruas vem só do cadastro de logradouros.
    """
    tabela = dialeto.tabela
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
chamados_lidos AS (
  SELECT
    c.data_inicio,
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
),
no_municipio AS (
  SELECT c.*, COALESCE({dentro}, FALSE) AS dentro_do_municipio
  FROM chamados_lidos AS c CROSS JOIN municipio
),
chamados AS (
  SELECT
    data_inicio, atendido, dias, bairro, logradouro_valido, rua,
    latitude IS NOT NULL AND longitude IS NOT NULL AND NOT dentro_do_municipio
      AS fora_do_municipio,
    CASE WHEN dentro_do_municipio THEN latitude END AS latitude,
    CASE WHEN dentro_do_municipio THEN longitude END AS longitude
  FROM no_municipio
)"""

    ruas = f"""{chamados}
SELECT bairro, rua,{totais("bairro, rua")} chamados WHERE rua IS NOT NULL) AS por_rua
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

    quadrados = f"""{chamados},
com_coordenada AS (
  SELECT atendido, dias, latitude, longitude FROM chamados
  WHERE latitude IS NOT NULL AND longitude IS NOT NULL
),
{passos},
no_quadrado AS (
  SELECT atendido, dias, CONCAT({canto("x")}, '_', {canto("y")}) AS quadrado FROM {anterior}
)
SELECT quadrado,{totais("quadrado")} no_quadrado) AS por_quadrado
GROUP BY quadrado"""

    resumo = f"""{chamados}
SELECT
  COUNT(*) AS lidos,
  COALESCE(SUM(CASE WHEN rua IS NULL THEN 1 ELSE 0 END), 0) AS sem_rua,
  COALESCE(SUM(CASE WHEN rua IS NULL AND logradouro_valido IS NOT NULL THEN 1 ELSE 0 END), 0)
    AS rua_fora_do_cadastro,
  COALESCE(SUM(CASE WHEN latitude IS NULL OR longitude IS NULL THEN 1 ELSE 0 END), 0)
    AS sem_coordenada,
  COALESCE(SUM(CASE WHEN fora_do_municipio THEN 1 ELSE 0 END), 0)
    AS coordenada_fora_do_municipio,
  MAX(data_inicio) AS mais_recente
FROM chamados"""

    desenho = f"""WITH {bairros}
SELECT
  COALESCE(b.bairro, '') AS bairro,
  TRIM(l.nome_completo) AS rua,
  {dialeto.desenho.format(coluna="l.geometry")} AS desenho
FROM {tabela(TABELA_LOGRADOUROS)} AS l
LEFT JOIN bairros AS b ON b.id_bairro = CAST(l.id_bairro AS STRING)
WHERE l.geometry IS NOT NULL AND TRIM(l.nome_completo) != ''
GROUP BY 1, 2"""

    return {"ruas": ruas, "quadrados": quadrados, "resumo": resumo, "desenho_das_ruas": desenho}


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

    minimo: int
    gb_lidos: float = 0.0
    lidos: int = 0
    sem_rua: int = 0
    rua_fora_do_cadastro: int = 0
    sem_coordenada: int = 0
    coordenada_fora_do_municipio: int = 0
    mais_recente: date | None = None
    data_da_coleta: date | None = None
    ruas: int = 0
    ruas_com_desenho: int = 0
    quadrados: int = 0

    def texto(self):
        return "\n".join([
            "Resumo da coleta (chamados do 1746)",
            f"fonte: {TABELA_CHAMADOS} (BigQuery, só leitura)",
            "período: todos",
            f"chamados lidos: {self.lidos}",
            f"sem rua: {self.sem_rua}",
            f"  dos quais com rua fora do cadastro de logradouros: {self.rua_fora_do_cadastro}",
            f"sem coordenada: {self.sem_coordenada}",
            f"  dos quais com coordenada fora do município: {self.coordenada_fora_do_municipio}",
            f"chamado mais recente na base: {self.mais_recente or 'nenhum'}",
            f"data da coleta: {self.data_da_coleta}",
            f"ruas: {self.ruas}",
            f"ruas com desenho: {self.ruas_com_desenho}",
            f"quadrados: {self.quadrados}",
            f"mínimo para mostrar o número: {self.minimo}",
            f"GB lidos no BigQuery (simulação): {_gb(self.gb_lidos)}",
        ]) + "\n"


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


def coletar(cliente, saida, *, minimo, limite_gb=LIMITE_GB_PADRAO, dialeto=BIGQUERY, hoje=None,
            avisar=print):
    """Roda as consultas no BigQuery (`cliente`) e grava os totais na pasta `saida`.

    Primeiro simula todas as consultas e para, sem rodar nenhuma, se juntas forem ler
    mais que `limite_gb`. Devolve o Resumo.
    """
    if minimo < 1:
        raise ValueError(
            "O --minimo precisa ser 1 ou mais. "
            "O que fazer: informe o mínimo de chamados para mostrar o número, por exemplo --minimo 5."
        )
    if limite_gb <= 0:
        raise ValueError(
            "O --limite-gb precisa ser maior que zero. "
            f"O que fazer: informe o limite em GB, por exemplo --limite-gb {LIMITE_GB_PADRAO}."
        )
    consultas = montar_consultas(dialeto)
    limite_bytes = int(limite_gb * GB)

    simulacao = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    total = sum(
        cliente.query(sql, job_config=simulacao).total_bytes_processed or 0
        for sql in consultas.values()
    )
    resumo = Resumo(minimo=minimo, gb_lidos=total / GB, data_da_coleta=hoje or date.today())
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
        resultados[nome] = [dict(linha.items()) for linha in resultado]

    ruas = {(linha["bairro"], linha["rua"]): Soma.da_linha(linha) for linha in resultados["ruas"]}
    quadrados = {}
    for linha in resultados["quadrados"]:
        x, y = linha["quadrado"].split("_")
        quadrados[(int(x), int(y))] = Soma.da_linha(linha)
    desenhos = {(linha["bairro"], linha["rua"]): linha["desenho"]
                for linha in resultados["desenho_das_ruas"]}
    (linha,) = resultados["resumo"]
    resumo.lidos = int(linha["lidos"])
    resumo.sem_rua = int(linha["sem_rua"])
    resumo.rua_fora_do_cadastro = int(linha["rua_fora_do_cadastro"])
    resumo.sem_coordenada = int(linha["sem_coordenada"])
    resumo.coordenada_fora_do_municipio = int(linha["coordenada_fora_do_municipio"])
    resumo.mais_recente = _como_data(linha["mais_recente"])
    resumo.ruas = len(ruas)
    resumo.quadrados = len(quadrados)

    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    gravar_ruas(saida / "ruas.csv", ruas, minimo)
    gravar_quadrados(saida, quadrados, minimo)
    resumo.ruas_com_desenho = gravar_desenho_das_ruas(saida / "ruas.geojson", ruas, desenhos,
                                                      minimo)
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


def gravar_desenho_das_ruas(caminho, ruas, desenhos, minimo):
    """Grava ruas.geojson: cada rua com desenho no cadastro, com os totais. Devolve quantas."""
    features = []
    for bairro, rua in sorted(ruas):
        desenho = desenhos.get((bairro, rua))
        if desenho is None:
            continue
        features.append({
            "type": "Feature",
            "properties": dict(zip(CABECALHO_RUAS, [bairro, rua, *numeros(ruas[(bairro, rua)], minimo)])),
            "geometry": _arredondar(json.loads(desenho)),
        })
    geojson = {"type": "FeatureCollection", "features": features}
    caminho.write_text(json.dumps(geojson, ensure_ascii=False, separators=(",", ":")),
                       encoding="utf-8")
    return len(features)


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
    "minimo": FALTA_NO_AGREGADOR["minimo"],
}

EXEMPLO = {
    "--projeto": "--projeto meu-projeto",
    "--minimo": "--minimo 5",
    "--saida": "--saida dados/coleta",
    "--limite-gb": f"--limite-gb {LIMITE_GB_PADRAO}",
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
        usage="%(prog)s --projeto ID --minimo N [--saida PASTA] [--limite-gb GB]",
        description="Soma no BigQuery os chamados do 1746 por rua e por quadrado de 100 m.",
        formatter_class=Formatador,
        add_help=False,
        exemplos=EXEMPLO,
        veja_a_ajuda=VEJA_A_AJUDA,
    )
    opcoes = leitor.add_argument_group("opções")
    opcoes.add_argument("--projeto", metavar="ID",
                        help="projeto do Google Cloud que roda a consulta (sandbox gratuito)")
    opcoes.add_argument(
        "--minimo", type=ler_minimo, metavar="N",
        help="rua ou quadrado com menos chamados que N sai como \"menos de N\"",
    )
    opcoes.add_argument("--saida", metavar="PASTA",
                        help="pasta onde gravar os arquivos (padrão: dados/coleta)")
    opcoes.add_argument(
        "--limite-gb", type=_ler_limite, metavar="GB", default=LIMITE_GB_PADRAO,
        help=f"para antes de rodar se a consulta for ler mais que isso (padrão: {LIMITE_GB_PADRAO}); "
             "no PowerShell, escreva com ponto (0.5): com vírgula, 0,001 chega como 0,1",
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
        cliente = (abrir or abrir_cliente)(opcoes.projeto)
    except (erros_do_login.GoogleAuthError, pydata_google_auth.exceptions.PyDataCredentialsError):
        print(
            "ERRO: não consegui entrar com o login Google. "
            "O que fazer: rode de novo e, no navegador, entre com a sua conta e aceite o acesso ao BigQuery.",
            file=sys.stderr,
        )
        return 1
    try:
        resumo = coletar(cliente, saida, minimo=opcoes.minimo, limite_gb=opcoes.limite_gb,
                         dialeto=dialeto)
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
