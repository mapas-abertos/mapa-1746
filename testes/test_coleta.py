"""Testes da coleta (issue #15): somar no BigQuery os chamados por rua e por quadrado de 100 m.

Cada teste nasce de um item do "Quando está pronta" da issue, antes do código (TDD).
Todos os chamados daqui são fictícios: ruas, datas e coordenadas inventadas.

Sem acesso ao BigQuery, as mesmas consultas rodam no DuckDB, um banco de dados que fica
na memória do computador. Só três pedaços mudam de um para o outro (o nome das tabelas,
a mediana e a conta de segundos): eles ficam no `Dialeto` da coleta. A consulta de
verdade, no BigQuery, é conferida no teste manual do pull request.
"""

import csv
import json
import math
import re
from datetime import date, datetime
from pathlib import Path

import duckdb
import pytest
from pyproj import Transformer

import coleta
from agregador import agregar
from coleta import BIGQUERY, Dialeto, LimiteExcedido, coletar, main, montar_consultas
from test_agregador import EXEMPLO_DA_ISSUE, LISTA_EXEMPLO

RAIZ = Path(__file__).resolve().parent.parent

CABECALHO_RUAS = ["bairro", "rua", "chamados", "atendidos", "fechados", "mediana_dias_ate_fechar"]
CABECALHO_QUADRADOS = ["quadrado", "chamados", "atendidos", "fechados", "mediana_dias_ate_fechar"]
COLUNAS_DO_RESUMO = ["lidos", "sem_rua", "rua_fora_do_cadastro", "sem_coordenada",
                     "coordenada_fora_do_municipio", "mais_recente"]
COLUNAS_DO_DESENHO = ["bairro", "rua", "desenho"]

# Colunas do chamado que nunca podem sair do BigQuery.
COLUNAS_PROIBIDAS = {"latitude", "longitude", "id_chamado", "numero_logradouro", "x", "y"}

PARA_METROS = Transformer.from_crs("EPSG:4326", "EPSG:31983", always_xy=True)
PARA_GRAUS = Transformer.from_crs("EPSG:31983", "EPSG:4326", always_xy=True)

HOJE = date(2026, 11, 5)
GIB = 1024**3

# O DuckDB faz de conta que é o BigQuery: mesmas consultas, com estes pedaços trocados.
TABELAS_LOCAIS = {
    "datario.adm_central_atendimento_1746.chamado": "chamado",
    "datario.dados_mestres.logradouro": "logradouro",
    "datario.dados_mestres.bairro": "bairro",
}
DUCKDB = Dialeto(
    tabela=lambda nome: TABELAS_LOCAIS[nome],
    mediana="quantile_cont({coluna}, 0.5) OVER (PARTITION BY {grupo})",
    segundos="date_diff('second', {inicio}, {fim})",
    inteiro="BIGINT",
    # Sem a extensão de mapas do DuckDB: o desenho de teste já vem pronto, em GeoJSON.
    desenho="MIN({coluna})",
    # Sem a extensão de mapas, o município de teste é uma caixa em volta do Rio.
    contorno="MIN({coluna})",
    dentro="({lon} BETWEEN -43.80 AND -43.09 AND {lat} BETWEEN -23.09 AND -22.74)",
)


# ---- Base fictícia no DuckDB, no formato das tabelas da Prefeitura ---------------------


def _data(texto):
    return datetime.fromisoformat(texto) if texto.strip() else None


def _numero(texto):
    return float(texto) if texto.strip() else None


def desenho_de_teste(i, j):
    """Um trecho de rua fictício, em GeoJSON, com mais casas decimais que o necessário."""
    lon, lat = -43.2 + i / 1000, -22.9 + j / 1000
    return json.dumps({"type": "LineString",
                       "coordinates": [[lon, lat], [lon + 0.0012345678, lat + 0.0008765432]]})


def montar_base(texto, *, fora_do_cadastro=(), sem_desenho=()):
    """Cria no DuckDB as três tabelas a partir de uma lista no formato do agregador.

    Cada rua ganha um código de logradouro e dois trechos (como no cadastro de verdade).
    Ruas em `fora_do_cadastro` ficam com código, mas sem trecho no cadastro.
    """
    conexao = duckdb.connect()
    conexao.execute("""
        CREATE TABLE chamado (
            id_chamado VARCHAR, data_inicio TIMESTAMP, data_fim TIMESTAMP, tipo VARCHAR,
            subtipo VARCHAR, tipo_situacao VARCHAR, id_bairro VARCHAR, id_logradouro VARCHAR,
            numero_logradouro BIGINT, latitude DOUBLE, longitude DOUBLE)""")
    conexao.execute("CREATE TABLE bairro (id_bairro BIGINT, nome VARCHAR, geometry VARCHAR)")
    conexao.execute("""
        CREATE TABLE logradouro (
            id_trecho BIGINT, id_logradouro BIGINT, nome VARCHAR, nome_completo VARCHAR,
            id_bairro BIGINT, geometry VARCHAR)""")

    bairros, logradouros = {}, {}
    linhas = list(csv.DictReader(texto.splitlines(), delimiter=";"))
    for numero, linha in enumerate(linhas, start=1):
        bairro, rua = linha["bairro"].strip(), linha["rua"].strip()
        id_bairro = bairros.setdefault(bairro, len(bairros) + 1)
        if rua == "":
            id_logradouro = None
        elif rua == "0":
            id_logradouro = "0"
        else:
            id_logradouro = str(logradouros.setdefault((bairro, rua), 100 + len(logradouros)))
        conexao.execute(
            "INSERT INTO chamado VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [f"CH-{90000 + numero}", _data(linha["data_inicio"]), _data(linha["data_fim"]),
             linha["tipo"], linha["subtipo"], linha["tipo_situacao"], str(id_bairro),
             id_logradouro, 700 + numero, _numero(linha["latitude"]), _numero(linha["longitude"])],
        )
    for bairro, id_bairro in bairros.items():
        conexao.execute("INSERT INTO bairro VALUES (?, ?, NULL)", [id_bairro, bairro])
    trecho = 0
    for i, ((bairro, rua), id_logradouro) in enumerate(logradouros.items()):
        if rua in fora_do_cadastro:
            continue
        for j in range(2):
            trecho += 1
            desenho = None if rua in sem_desenho else desenho_de_teste(i, j)
            # No cadastro, "nome" é o nome do bairro e "nome_completo" é o da rua.
            conexao.execute(
                "INSERT INTO logradouro VALUES (?, ?, ?, ?, ?, ?)",
                [trecho, id_logradouro, bairro, rua, bairros[bairro], desenho],
            )
    return conexao


class Campo:
    def __init__(self, nome):
        self.name = nome


class Resultado(list):
    """Faz de conta que é o resultado do BigQuery: as linhas e os nomes das colunas."""

    def __init__(self, linhas, colunas):
        super().__init__(linhas)
        self.schema = [Campo(nome) for nome in colunas]


class Trabalho:
    def __init__(self, resultado=None, total_bytes_processed=0):
        self._resultado = resultado
        self.total_bytes_processed = total_bytes_processed

    def result(self):
        return self._resultado


class ClienteFalso:
    """Faz de conta que é o cliente do BigQuery, rodando as consultas no DuckDB."""

    def __init__(self, conexao, bytes_por_consulta=GIB // 2, colunas_a_mais=()):
        self.conexao = conexao
        self.bytes_por_consulta = bytes_por_consulta
        self.colunas_a_mais = colunas_a_mais
        self.eventos = []  # ("simulação" ou "consulta", sql, configuração)
        self.colunas = {}  # sql -> colunas devolvidas

    def query(self, sql, job_config=None):
        if job_config is not None and job_config.dry_run:
            self.eventos.append(("simulação", sql, job_config))
            return Trabalho(total_bytes_processed=self.bytes_por_consulta)
        self.eventos.append(("consulta", sql, job_config))
        resposta = self.conexao.sql(sql)
        colunas = list(resposta.columns) + list(self.colunas_a_mais)
        linhas = [dict(zip(colunas, [*valores, *("?" for _ in self.colunas_a_mais)]))
                  for valores in resposta.fetchall()]
        self.colunas[sql] = colunas
        return Trabalho(Resultado(linhas, colunas))


def rodar(tmp_path, texto=LISTA_EXEMPLO, minimo=5, *, cliente=None, **opcoes):
    cliente = cliente or ClienteFalso(montar_base(texto))
    saida = tmp_path / "coleta"
    avisos = []
    resumo = coletar(
        cliente, saida, minimo=minimo, dialeto=DUCKDB, hoje=HOJE, avisar=avisos.append, **opcoes
    )
    return resumo, saida, cliente, avisos


def rodar_agregador(tmp_path, texto, minimo):
    entrada = tmp_path / "chamados.csv"
    entrada.write_text(texto, encoding="utf-8")
    saida = tmp_path / "agregador"
    agregar(entrada, saida, minimo=minimo)
    return saida


def ler_csv(caminho):
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo, delimiter=";"))


def ler_json(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


# ---- A consulta segue a mesma regra do agregador --------------------------------------


@pytest.mark.parametrize("minimo", [1, 5, 7])
def test_coleta_grava_os_mesmos_arquivos_que_o_agregador(tmp_path, minimo):
    # Total, atendidos, fechados e mediana por bairro e rua e por quadrado, e o "menos de N".
    _, saida, _, _ = rodar(tmp_path, minimo=minimo)
    do_agregador = rodar_agregador(tmp_path, LISTA_EXEMPLO, minimo)
    for nome in ("ruas.csv", "quadrados.csv", "quadrados.geojson"):
        assert (saida / nome).read_text(encoding="utf-8") == (
            do_agregador / nome
        ).read_text(encoding="utf-8"), f"{nome} saiu diferente do agregador"


def test_exemplo_da_issue_da_a_linha_esperada_em_ruas_csv(tmp_path):
    resumo, saida, _, _ = rodar(tmp_path, EXEMPLO_DA_ISSUE, minimo=1)
    linhas = (saida / "ruas.csv").read_text(encoding="utf-8").splitlines()
    assert linhas == [";".join(CABECALHO_RUAS), "Centro;Rua Exemplo;2;1;1;3.0"]
    assert resumo.sem_rua == 1
    assert resumo.sem_coordenada == 1


def test_mediana_e_exata(tmp_path):
    # Tijuca, Rua A: fechados em 10, 4, 2 e 1 dias. A mediana exata é (2 + 4) / 2 = 3.
    _, saida, _, _ = rodar(tmp_path, minimo=1)
    ruas = {(r["bairro"], r["rua"]): r for r in ler_csv(saida / "ruas.csv")}
    assert ruas[("Tijuca", "Rua A")]["mediana_dias_ate_fechar"] == "3.0"
    assert ruas[("Centro", "Rua A")]["mediana_dias_ate_fechar"] == "1.5"


def test_rua_com_varios_trechos_no_cadastro_nao_conta_duas_vezes(tmp_path):
    # Cada rua da base fictícia tem dois trechos no cadastro de logradouros.
    _, saida, _, _ = rodar(tmp_path, minimo=1)
    total = sum(int(r["chamados"]) for r in ler_csv(saida / "ruas.csv"))
    assert total == 17  # 19 chamados, 2 sem rua


def test_rua_fora_do_cadastro_conta_como_sem_rua(tmp_path):
    cliente = ClienteFalso(montar_base(LISTA_EXEMPLO, fora_do_cadastro={"Rua C"}))
    resumo, saida, _, _ = rodar(tmp_path, minimo=1, cliente=cliente)
    assert "Rua C" not in {r["rua"] for r in ler_csv(saida / "ruas.csv")}
    assert resumo.sem_rua == 3
    assert resumo.rua_fora_do_cadastro == 1
    assert "rua fora do cadastro de logradouros: 1" in (saida / "resumo.txt").read_text(
        encoding="utf-8"
    )


# ---- Coordenada fora do município ----------------------------------------------------

# Chamados inventados com coordenada fora do Rio: no mar, perto do Equador, no interior
# e uma coordenada impossível (latitude acima de 90°).
FORA_DO_RIO = [
    (-23.30, -43.20),  # no mar, ao sul de Copacabana
    (-0.49, -48.00),  # perto do Equador
    (-21.80, -44.70),  # interior de Minas Gerais
    (2290668.0, -43.17),  # coordenada impossível
]


def lista_com_chamados_fora_do_rio():
    return LISTA_EXEMPLO + "".join(
        f"2025-08-0{i} 10:00;2025-08-0{i} 22:00;Limpeza;Remoção de entulho;Atendido;"
        f"Centro;Rua A;{lat};{lon}\n"
        for i, (lat, lon) in enumerate(FORA_DO_RIO, start=1)
    )


def test_chamado_fora_do_municipio_nao_entra_em_nenhum_quadrado(tmp_path):
    _, saida, _, _ = rodar(tmp_path, lista_com_chamados_fora_do_rio(), minimo=1)
    do_agregador = rodar_agregador(tmp_path, LISTA_EXEMPLO, 1)
    for nome in ("quadrados.csv", "quadrados.geojson"):
        assert (saida / nome).read_text(encoding="utf-8") == (
            do_agregador / nome
        ).read_text(encoding="utf-8"), f"{nome} traz chamado de fora do Rio"


def test_chamado_fora_do_municipio_conta_como_sem_coordenada_com_linha_propria(tmp_path):
    resumo, saida, _, _ = rodar(tmp_path, lista_com_chamados_fora_do_rio(), minimo=1)
    assert resumo.lidos == 19 + 4
    assert resumo.sem_coordenada == 4 + 4
    assert resumo.coordenada_fora_do_municipio == 4
    texto = (saida / "resumo.txt").read_text(encoding="utf-8")
    assert "sem coordenada: 8" in texto
    assert "coordenada fora do município: 4" in texto


def test_chamado_fora_do_municipio_continua_contando_na_rua(tmp_path):
    _, saida, _, _ = rodar(tmp_path, lista_com_chamados_fora_do_rio(), minimo=1)
    ruas = {(r["bairro"], r["rua"]): r for r in ler_csv(saida / "ruas.csv")}
    assert ruas[("Centro", "Rua A")]["chamados"] == "10"  # 6 do exemplo e os 4 de fora


def test_resumo_sem_chamado_fora_do_municipio_mostra_zero(tmp_path):
    resumo, saida, _, _ = rodar(tmp_path)
    assert resumo.coordenada_fora_do_municipio == 0
    assert "coordenada fora do município: 0" in (saida / "resumo.txt").read_text(encoding="utf-8")


def test_bigquery_confere_o_ponto_contra_o_contorno_dos_bairros():
    consulta = montar_consultas(BIGQUERY)["quadrados"]
    assert "ST_UNION_AGG(geometry) AS contorno" in consulta
    assert "FROM `datario.dados_mestres.bairro`" in consulta.split("AS contorno")[1].split(")")[0]
    # Longitude antes da latitude, e uma coordenada impossível vira "fora", sem erro.
    assert (
        "ST_DWITHIN(SAFE.ST_GEOGPOINT(c.longitude, c.latitude), municipio.contorno, "
        f"{coleta.TOLERANCIA_DO_MUNICIPIO})"
    ) in consulta


def test_tolerancia_do_contorno_e_de_no_maximo_um_quadrado():
    assert 0 <= coleta.TOLERANCIA_DO_MUNICIPIO <= 100


# ---- A conta de metros dentro da consulta dá o mesmo quadrado que o pyproj ------------

# Pontos fictícios espalhados pelo Rio, de Sepetiba a Paquetá.
PONTOS_DO_RIO = [
    (-43.1729, -22.9068),  # Centro
    (-43.1822, -22.9711),  # Copacabana
    (-43.2330, -22.9250),  # Tijuca
    (-43.3659, -23.0004),  # Barra da Tijuca
    (-43.4636, -23.0186),  # Recreio
    (-43.5591, -22.9035),  # Campo Grande
    (-43.6847, -22.9194),  # Santa Cruz
    (-43.7100, -22.9700),  # Sepetiba
    (-43.5700, -23.0500),  # Guaratiba
    (-43.3640, -22.8066),  # Pavuna
    (-43.2050, -22.8030),  # Ilha do Governador
    (-43.1077, -22.7616),  # Paquetá
]

FUNCOES_SQL = {
    "SIN": math.sin, "COS": math.cos, "SQRT": math.sqrt, "ATAN2": math.atan2,
    "SINH": math.sinh, "COSH": math.cosh, "ATANH": math.atanh, "FLOOR": math.floor,
}


def metros_pela_consulta(longitude, latitude):
    """Faz, em Python, a conta escrita na consulta: o mesmo texto, passo a passo."""
    valores = {"latitude": latitude, "longitude": longitude}
    for nome, expressao in coleta.PASSOS_METROS:
        valores[nome] = eval(expressao, {"__builtins__": {}, **FUNCOES_SQL}, valores)
    return valores["x"], valores["y"]


def quadrado_pelo_pyproj(longitude, latitude):
    x, y = PARA_METROS.transform(longitude, latitude)
    return math.floor(x / 100) * 100, math.floor(y / 100) * 100


def pontos_perto_da_borda():
    """Pontos a menos de 1 m da borda de um quadrado, dos dois lados, em x e em y."""
    pontos = []
    for longitude, latitude in PONTOS_DO_RIO:
        x, y = PARA_METROS.transform(longitude, latitude)
        borda_x, borda_y = round(x / 100) * 100, round(y / 100) * 100
        for distancia in (0.9, 0.5, 0.1, 0.01, 0.001):
            for lado in (-1, 1):
                pontos.append(PARA_GRAUS.transform(borda_x + lado * distancia, y))
                pontos.append(PARA_GRAUS.transform(x, borda_y + lado * distancia))
    return pontos


def grade_sobre_o_rio():
    return [(-43.80 + i * 0.07, -23.08 + j * 0.035) for i in range(11) for j in range(11)]


def test_conta_de_metros_da_o_mesmo_quadrado_que_o_pyproj():
    pontos = PONTOS_DO_RIO + grade_sobre_o_rio() + pontos_perto_da_borda()
    assert len(pontos) > 200
    for longitude, latitude in pontos:
        x, y = metros_pela_consulta(longitude, latitude)
        assert (math.floor(x / 100) * 100, math.floor(y / 100) * 100) == quadrado_pelo_pyproj(
            longitude, latitude
        ), f"quadrado diferente do pyproj em {longitude}, {latitude}"


def test_conta_de_metros_erra_menos_de_um_milimetro():
    for longitude, latitude in PONTOS_DO_RIO + grade_sobre_o_rio():
        x, y = metros_pela_consulta(longitude, latitude)
        x_pyproj, y_pyproj = PARA_METROS.transform(longitude, latitude)
        assert abs(x - x_pyproj) < 0.001 and abs(y - y_pyproj) < 0.001, (longitude, latitude)


def test_a_conta_conferida_e_a_que_esta_na_consulta_do_bigquery():
    consulta = montar_consultas(BIGQUERY)["quadrados"]
    for nome, expressao in coleta.PASSOS_METROS:
        assert f"{expressao} AS {nome}" in consulta, f"o passo {nome} não está na consulta"


def test_pontos_perto_da_borda_caem_no_mesmo_quadrado_que_no_agregador(tmp_path):
    cabecalho = LISTA_EXEMPLO.splitlines()[0]
    texto = cabecalho + "\n" + "".join(
        f"2025-03-01 08:00;;Limpeza;Remoção de entulho;Não consta;Centro;Rua A;{lat};{lon}\n"
        for lon, lat in pontos_perto_da_borda()
    )
    _, saida, _, _ = rodar(tmp_path, texto, minimo=1)
    do_agregador = rodar_agregador(tmp_path, texto, 1)
    assert (saida / "quadrados.csv").read_text(encoding="utf-8") == (
        do_agregador / "quadrados.csv"
    ).read_text(encoding="utf-8")


# ---- A consulta só devolve linhas somadas ---------------------------------------------


def test_cada_consulta_devolve_so_as_colunas_do_formato_de_saida(tmp_path):
    _, _, cliente, _ = rodar(tmp_path)
    consultas = montar_consultas(DUCKDB)
    esperadas = {
        "ruas": CABECALHO_RUAS,
        "quadrados": CABECALHO_QUADRADOS,
        "resumo": COLUNAS_DO_RESUMO,
        "desenho_das_ruas": COLUNAS_DO_DESENHO,
    }
    assert set(consultas) == set(esperadas)
    for nome, colunas in esperadas.items():
        devolvidas = cliente.colunas[consultas[nome]]
        assert devolvidas == colunas, f"a consulta {nome} devolveu {devolvidas}"
        assert not set(devolvidas) & COLUNAS_PROIBIDAS


def test_desenho_das_ruas_nao_le_a_tabela_de_chamados():
    consulta = montar_consultas(BIGQUERY)["desenho_das_ruas"]
    assert "adm_central_atendimento_1746" not in consulta
    assert "latitude" not in consulta and "longitude" not in consulta


def test_coleta_para_se_a_consulta_devolver_coluna_a_mais(tmp_path):
    cliente = ClienteFalso(montar_base(LISTA_EXEMPLO), colunas_a_mais=("latitude",))
    with pytest.raises(ValueError, match="latitude"):
        rodar(tmp_path, cliente=cliente)
    assert not (tmp_path / "coleta").exists()


def test_nenhuma_saida_tem_coordenada_identificador_ou_numero_de_porta(tmp_path):
    _, saida, _, _ = rodar(tmp_path, minimo=1)
    conexao = montar_base(LISTA_EXEMPLO)
    proibidos = set()
    for id_chamado, porta, latitude, longitude in conexao.sql(
        "SELECT id_chamado, numero_logradouro, latitude, longitude FROM chamado"
    ).fetchall():
        proibidos |= {id_chamado, str(porta)}
        proibidos |= {repr(v) for v in (latitude, longitude) if v}
    arquivos = {a.name for a in saida.iterdir()}
    assert arquivos == {"ruas.csv", "quadrados.csv", "quadrados.geojson", "ruas.geojson",
                        "resumo.txt"}
    for arquivo in saida.iterdir():
        texto = arquivo.read_text(encoding="utf-8")
        for proibido in proibidos:
            assert not re.search(rf"(?<![\d.]){re.escape(proibido)}(?![\d])", texto), (
                f"{arquivo.name} traz {proibido}"
            )


# ---- ruas.geojson: o desenho das ruas, do cadastro de logradouros, com os totais -----


def test_ruas_geojson_traz_o_desenho_e_os_mesmos_totais_do_csv(tmp_path):
    _, saida, _, _ = rodar(tmp_path, minimo=5)
    geojson = ler_json(saida / "ruas.geojson")
    assert geojson["type"] == "FeatureCollection"
    do_csv = {(r["bairro"], r["rua"]): r for r in ler_csv(saida / "ruas.csv")}
    do_geojson = {(f["properties"]["bairro"], f["properties"]["rua"]): f
                  for f in geojson["features"]}
    assert set(do_geojson) == set(do_csv)
    for chave, feature in do_geojson.items():
        assert list(feature["properties"]) == CABECALHO_RUAS
        for coluna in CABECALHO_RUAS:
            valor = feature["properties"][coluna]
            assert do_csv[chave][coluna] == ("" if valor is None else str(valor)), (chave, coluna)
        assert feature["geometry"]["type"] == "LineString"
    assert do_geojson[("Glória", "Rua C")]["properties"]["chamados"] == "menos de 5"


def test_ruas_geojson_arredonda_o_desenho_em_6_casas(tmp_path):
    _, saida, _, _ = rodar(tmp_path, minimo=1)
    for feature in ler_json(saida / "ruas.geojson")["features"]:
        for ponto in feature["geometry"]["coordinates"]:
            for numero in ponto:
                assert numero == round(numero, 6)


def test_rua_sem_desenho_fica_so_no_csv(tmp_path):
    cliente = ClienteFalso(montar_base(LISTA_EXEMPLO, sem_desenho={"Rua C"}))
    resumo, saida, _, _ = rodar(tmp_path, minimo=1, cliente=cliente)
    ruas = {f["properties"]["rua"] for f in ler_json(saida / "ruas.geojson")["features"]}
    assert "Rua C" not in ruas
    assert "Rua C" in {r["rua"] for r in ler_csv(saida / "ruas.csv")}
    assert resumo.ruas == 4 and resumo.ruas_com_desenho == 3


# ---- Simulação (dry run) antes de rodar, com limite configurável ----------------------


def test_simulacao_vem_antes_de_tudo_e_mostra_os_gb(tmp_path):
    _, _, cliente, avisos = rodar(tmp_path)
    tipos = [tipo for tipo, _, _ in cliente.eventos]
    assert tipos == ["simulação"] * 4 + ["consulta"] * 4
    for _, _, configuracao in cliente.eventos[:4]:
        assert configuracao.use_query_cache is False
    # 4 consultas de 0,5 GB cada.
    assert any("2,0 GB" in aviso for aviso in avisos), avisos


def test_para_antes_de_rodar_se_passar_do_limite(tmp_path):
    cliente = ClienteFalso(montar_base(LISTA_EXEMPLO), bytes_por_consulta=3 * GIB)
    with pytest.raises(LimiteExcedido) as erro:
        rodar(tmp_path, cliente=cliente, limite_gb=10)
    assert "12,0 GB" in str(erro.value) and "10" in str(erro.value)
    assert "O que fazer:" in str(erro.value)
    assert [tipo for tipo, _, _ in cliente.eventos] == ["simulação"] * 4
    assert not (tmp_path / "coleta").exists()


def test_consulta_de_verdade_tambem_tem_o_limite(tmp_path):
    _, _, cliente, _ = rodar(tmp_path, limite_gb=3)
    for tipo, _, configuracao in cliente.eventos:
        if tipo == "consulta":
            assert configuracao.maximum_bytes_billed == 3 * GIB


def test_limite_vem_da_linha_de_comando(tmp_path, capsys):
    cliente = ClienteFalso(montar_base(LISTA_EXEMPLO), bytes_por_consulta=3 * GIB)
    codigo = main(
        ["--projeto", "projeto-de-teste", "--minimo", "5", "--saida", str(tmp_path / "s"),
         "--limite-gb", "11"],
        abrir=lambda projeto: cliente, dialeto=DUCKDB,
    )
    assert codigo != 0
    erro = capsys.readouterr().err
    assert "12,0 GB" in erro and "11" in erro
    assert not (tmp_path / "s").exists()


@pytest.mark.parametrize("valor, texto", [
    (0, "0"), (0.001, "0,001"), (0.0123, "0,012"), (0.5, "0,5"), (0.25, "0,25"),
    (0.999, "1"), (1, "1,0"), (12.04, "12,0"),
])
def test_gb_menor_que_1_aparece_com_casas_suficientes(valor, texto):
    assert coleta._gb(valor) == texto


def test_limite_menor_que_1_gb_aparece_como_foi_pedido(tmp_path):
    cliente = ClienteFalso(montar_base(LISTA_EXEMPLO), bytes_por_consulta=1024**2)
    with pytest.raises(LimiteExcedido) as erro:
        rodar(tmp_path, cliente=cliente, limite_gb=0.001)
    # 4 consultas de 1 MB cada: 0,0039 GB, acima de 0,001 GB.
    assert "0,0039 GB" in str(erro.value) and "limite de 0,001 GB" in str(erro.value)


def test_limite_com_virgula_ou_ponto_pela_linha_de_comando(tmp_path, capsys):
    for limite in ("0,001", "0.001"):
        cliente = ClienteFalso(montar_base(LISTA_EXEMPLO), bytes_por_consulta=1024**2)
        codigo = main(["--projeto", "p", "--minimo", "5", "--saida", str(tmp_path / "s"),
                       "--limite-gb", limite], abrir=lambda projeto: cliente, dialeto=DUCKDB)
        assert codigo != 0
        assert "limite: 0,001 GB" in capsys.readouterr().out


def test_limite_padrao_cabe_no_sandbox_gratuito():
    assert 0 < coleta.LIMITE_GB_PADRAO <= 1024 / 10  # pelo menos 10 coletas no 1 TB do mês


# ---- Mínimo, como no agregador --------------------------------------------------------


def test_minimo_tem_de_ser_pelo_menos_1(tmp_path):
    with pytest.raises(ValueError, match="mínimo"):
        rodar(tmp_path, minimo=0)


def test_quadrado_abaixo_do_minimo_sai_como_menos_de_n(tmp_path):
    _, saida, _, _ = rodar(tmp_path, minimo=5)
    linha = {q["quadrado"]: q for q in ler_csv(saida / "quadrados.csv")}["687400_7465600"]
    assert linha["chamados"] == "menos de 5"
    assert linha["atendidos"] == linha["fechados"] == linha["mediana_dias_ate_fechar"] == ""


# ---- Resumo ---------------------------------------------------------------------------


def test_resumo_traz_lidos_sem_rua_sem_coordenada_e_as_datas(tmp_path):
    resumo, saida, _, _ = rodar(tmp_path)
    texto = (saida / "resumo.txt").read_text(encoding="utf-8")
    assert resumo.lidos == 19
    for trecho in (
        "chamados lidos: 19",
        "sem rua: 2",
        "sem coordenada: 4",
        "coordenada fora do município: 0",
        "chamado mais recente na base: 2025-07-01",
        "data da coleta: 2026-11-05",
        "mínimo para mostrar o número: 5",
        "datario.adm_central_atendimento_1746.chamado",
    ):
        assert trecho in texto, f"o resumo não traz \"{trecho}\""


def test_total_dos_quadrados_e_lidos_menos_sem_coordenada(tmp_path):
    resumo, saida, _, _ = rodar(tmp_path, minimo=1)
    total = sum(int(q["chamados"]) for q in ler_csv(saida / "quadrados.csv"))
    assert total == resumo.lidos - resumo.sem_coordenada == 15


# ---- Saída em dados/, que não vai para o GitHub ---------------------------------------


def test_pasta_padrao_fica_em_dados_que_nao_vai_para_o_github():
    assert coleta.PASTA_PADRAO == RAIZ / "dados" / "coleta"
    linhas = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "dados/" in linhas


def test_sem_saida_grava_na_pasta_padrao(tmp_path, monkeypatch):
    monkeypatch.setattr(coleta, "PASTA_PADRAO", tmp_path / "padrao")
    cliente = ClienteFalso(montar_base(LISTA_EXEMPLO))
    codigo = main(["--projeto", "p", "--minimo", "5"], abrir=lambda projeto: cliente,
                  dialeto=DUCKDB)
    assert codigo == 0
    assert (tmp_path / "padrao" / "ruas.csv").exists()


# ---- Login do responsável (OAuth), sem senha nem chave no código ----------------------


def test_codigo_nao_tem_chave_nem_arquivo_de_credencial():
    fonte = (RAIZ / "src" / "coleta.py").read_text(encoding="utf-8").lower()
    for proibido in ("service_account", "private_key", "google_application_credentials",
                     "keyfile", "client_secret", ".json\""):
        assert proibido not in fonte, f"o código cita {proibido}"


def test_login_e_o_do_responsavel_pelo_navegador(monkeypatch):
    chamadas = {}

    def login(escopos, **opcoes):
        chamadas["escopos"] = escopos
        return "credencial-do-login"

    class Cliente:
        def __init__(self, project, credentials):
            chamadas["cliente"] = (project, credentials)

    monkeypatch.setattr(coleta.pydata_google_auth, "get_user_credentials", login)
    monkeypatch.setattr(coleta.bigquery, "Client", Cliente)
    coleta.abrir_cliente("projeto-de-teste")
    assert chamadas["cliente"] == ("projeto-de-teste", "credencial-do-login")
    assert chamadas["escopos"] == ["https://www.googleapis.com/auth/bigquery"]


# ---- Mensagens da linha de comando, em português --------------------------------------

INGLES = ("error:", "usage:", "the following arguments", "invalid", "expected", "unrecognized",
          "options:", "show this help")


def rodar_comando(capsys, *argumentos):
    def nao_abrir(projeto):
        raise AssertionError("não devia chegar a abrir o BigQuery")
    codigo = main(list(argumentos), abrir=nao_abrir, dialeto=DUCKDB)
    return codigo, capsys.readouterr().err


def confere_mensagem(codigo, mensagem, *trechos):
    assert codigo != 0
    assert "O que fazer:" in mensagem, mensagem
    for trecho in trechos:
        assert trecho in mensagem, mensagem
    for ingles in INGLES:
        assert ingles not in mensagem.lower(), f"mensagem em inglês: {mensagem}"


def test_sem_minimo_diz_em_portugues_o_que_fazer(capsys):
    codigo, mensagem = rodar_comando(capsys, "--projeto", "p")
    confere_mensagem(codigo, mensagem, "Falta o --minimo", "--minimo 5")


def test_sem_projeto_diz_em_portugues_o_que_fazer(capsys):
    codigo, mensagem = rodar_comando(capsys, "--minimo", "5")
    confere_mensagem(codigo, mensagem, "Falta o --projeto")


def test_limite_que_nao_e_numero_diz_em_portugues_o_que_fazer(capsys):
    codigo, mensagem = rodar_comando(capsys, "--projeto", "p", "--minimo", "5",
                                     "--limite-gb", "dez")
    confere_mensagem(codigo, mensagem, "--limite-gb")


def test_opcao_desconhecida_diz_em_portugues_o_que_fazer(capsys):
    codigo, mensagem = rodar_comando(capsys, "--projeto", "p", "--minimo", "5", "--cor", "azul")
    confere_mensagem(codigo, mensagem, "--cor", "coleta.py --ajuda")


def test_ajuda_em_portugues(capsys):
    with pytest.raises(SystemExit) as saida:
        main(["--ajuda"])
    assert saida.value.code == 0
    ajuda = capsys.readouterr().out
    assert "uso:" in ajuda and "--minimo" in ajuda and "--limite-gb" in ajuda
    for ingles in INGLES:
        assert ingles not in ajuda.lower(), f"ajuda em inglês: {ingles}"
