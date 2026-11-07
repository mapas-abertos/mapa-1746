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
from coleta import (
    BIGQUERY,
    CLASSIFICACAO_PADRAO,
    Dialeto,
    LimiteExcedido,
    ListaInvalida,
    coletar,
    ler_classificacao,
    main,
    montar_consultas,
)
from test_agregador import EXEMPLO_DA_ISSUE, LISTA_EXEMPLO

RAIZ = Path(__file__).resolve().parent.parent

CABECALHO_RUAS = ["bairro", "rua", "chamados", "atendidos", "fechados", "mediana_dias_ate_fechar"]
CABECALHO_QUADRADOS = ["quadrado", "chamados", "atendidos", "fechados", "mediana_dias_ate_fechar"]
COLUNAS_DO_RESUMO = ["lidos", "problema_publico", "sem_rua", "rua_fora_do_cadastro", "sem_coordenada",
                     "coordenada_fora_do_municipio", "mais_recente"]
COLUNAS_DO_DESENHO = ["bairro", "rua", "desenho"]
COLUNAS_POR_SUBTIPO = ["tipo", "subtipo", "chamados"]
DIMENSOES = ["tema", "status", "situacao", "tipo_situacao", "prazo", "orgao"]

# Classificação fictícia dos três pares da lista de exemplo: todos de problema público,
# para os testes que já existiam (antes da issue #26) continuarem com os mesmos totais.
CLASSIFICACAO_DO_EXEMPLO = {
    ("Iluminação Pública", "Reparo de lâmpada apagada"): "publico",
    ("Limpeza", "Remoção de entulho"): "publico",
    ("Conservação", "Tapa-buraco"): "publico",
}

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
    texto=lambda valor: "'" + valor.replace("'", "''") + "'",
    pares="(VALUES {linhas}) AS pares(tipo, subtipo)",
    # Sem a extensão de mapas, o desenho de teste do bairro já é a caixa: "oeste,sul,leste,norte".
    caixa=("struct_pack(xmin := CAST(split_part(MIN({coluna}), ',', 1) AS DOUBLE), "
           "ymin := CAST(split_part(MIN({coluna}), ',', 2) AS DOUBLE), "
           "xmax := CAST(split_part(MIN({coluna}), ',', 3) AS DOUBLE), "
           "ymax := CAST(split_part(MIN({coluna}), ',', 4) AS DOUBLE))"),
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


# Valores fictícios das colunas dos filtros (issue #31) quando a lista não traz a coluna.
ORGAO_DO_TIPO = {
    "Iluminação Pública": "Órgão Fictício da Luz",
    "Limpeza": "Órgão Fictício da Limpeza",
    "Conservação": "Órgão Fictício das Ruas",
}

# A caixa fictícia de cada bairro, em graus: oeste, sul, leste, norte.
CAIXA_DO_BAIRRO = {
    "Centro": (-43.19, -22.92, -43.16, -22.89),
    "Tijuca": (-43.26, -22.94, -43.22, -22.91),
    "Glória": (-43.18, -22.93, -43.17, -22.91),
}


def _filtros_da_linha(linha):
    """status, situação, prazo e órgão do chamado: da lista, ou inventados a partir dele."""
    fechado = bool(linha["data_fim"].strip())
    return [
        linha.get("status") or ("Fechado" if fechado else "Aberto"),
        linha.get("situacao") or ("Encerrado" if fechado else "Não Encerrado"),
        linha.get("dentro_prazo") or "No prazo",
        linha.get("orgao") or ORGAO_DO_TIPO.get(linha["tipo"].strip(), "Órgão Fictício"),
    ]


def montar_base(texto, *, fora_do_cadastro=(), sem_desenho=()):
    """Cria no DuckDB as três tabelas a partir de uma lista no formato do agregador.

    Cada rua ganha um código de logradouro e dois trechos (como no cadastro de verdade).
    Ruas em `fora_do_cadastro` ficam com código, mas sem trecho no cadastro. As colunas dos
    filtros (status, situacao, dentro_prazo e orgao) podem vir na lista; sem elas, valem os
    valores de _filtros_da_linha.
    """
    conexao = duckdb.connect()
    conexao.execute("""
        CREATE TABLE chamado (
            id_chamado VARCHAR, data_inicio TIMESTAMP, data_fim TIMESTAMP, tipo VARCHAR,
            subtipo VARCHAR, tipo_situacao VARCHAR, id_bairro VARCHAR, id_logradouro VARCHAR,
            numero_logradouro BIGINT, latitude DOUBLE, longitude DOUBLE, status VARCHAR,
            situacao VARCHAR, dentro_prazo VARCHAR, nome_unidade_organizacional VARCHAR)""")
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
            "INSERT INTO chamado VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [f"CH-{90000 + numero}", _data(linha["data_inicio"]), _data(linha["data_fim"]),
             linha["tipo"], linha["subtipo"], linha["tipo_situacao"], str(id_bairro),
             id_logradouro, 700 + numero, _numero(linha["latitude"]), _numero(linha["longitude"]),
             *_filtros_da_linha(linha)],
        )
    for bairro, id_bairro in bairros.items():
        caixa = CAIXA_DO_BAIRRO.get(bairro)
        conexao.execute("INSERT INTO bairro VALUES (?, ?, ?)",
                        [id_bairro, bairro, ",".join(map(str, caixa)) if caixa else None])
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


def rodar(tmp_path, texto=LISTA_EXEMPLO, *, cliente=None,
          classificacao=CLASSIFICACAO_DO_EXEMPLO, **opcoes):
    cliente = cliente or ClienteFalso(montar_base(texto))
    saida = tmp_path / "coleta"
    avisos = []
    resumo = coletar(
        cliente, saida, classificacao=classificacao, dialeto=DUCKDB, hoje=HOJE,
        avisar=avisos.append, **opcoes
    )
    return resumo, saida, cliente, avisos


def rodar_agregador(tmp_path, texto):
    entrada = tmp_path / "chamados.csv"
    entrada.write_text(texto, encoding="utf-8")
    saida = tmp_path / "agregador"
    agregar(entrada, saida)
    return saida


def ler_csv(caminho):
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo, delimiter=";"))


def ler_json(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


# ---- A consulta segue a mesma regra do agregador --------------------------------------


def test_coleta_grava_os_mesmos_arquivos_que_o_agregador(tmp_path):
    # Total, atendidos, fechados e mediana por bairro e rua e por quadrado.
    _, saida, _, _ = rodar(tmp_path)
    do_agregador = rodar_agregador(tmp_path, LISTA_EXEMPLO)
    for nome in ("ruas.csv", "quadrados.csv", "quadrados.geojson"):
        assert (saida / nome).read_text(encoding="utf-8") == (
            do_agregador / nome
        ).read_text(encoding="utf-8"), f"{nome} saiu diferente do agregador"


def test_exemplo_da_issue_da_a_linha_esperada_em_ruas_csv(tmp_path):
    resumo, saida, _, _ = rodar(tmp_path, EXEMPLO_DA_ISSUE)
    linhas = (saida / "ruas.csv").read_text(encoding="utf-8").splitlines()
    assert linhas == [";".join(CABECALHO_RUAS), "Centro;Rua Exemplo;2;1;1;3.0"]
    assert resumo.sem_rua == 1
    assert resumo.sem_coordenada == 1


def test_mediana_e_exata(tmp_path):
    # Tijuca, Rua A: fechados em 10, 4, 2 e 1 dias. A mediana exata é (2 + 4) / 2 = 3.
    _, saida, _, _ = rodar(tmp_path)
    ruas = {(r["bairro"], r["rua"]): r for r in ler_csv(saida / "ruas.csv")}
    assert ruas[("Tijuca", "Rua A")]["mediana_dias_ate_fechar"] == "3.0"
    assert ruas[("Centro", "Rua A")]["mediana_dias_ate_fechar"] == "1.5"


def test_rua_com_varios_trechos_no_cadastro_nao_conta_duas_vezes(tmp_path):
    # Cada rua da base fictícia tem dois trechos no cadastro de logradouros.
    _, saida, _, _ = rodar(tmp_path)
    total = sum(int(r["chamados"]) for r in ler_csv(saida / "ruas.csv"))
    assert total == 17  # 19 chamados, 2 sem rua


def test_rua_fora_do_cadastro_conta_como_sem_rua(tmp_path):
    cliente = ClienteFalso(montar_base(LISTA_EXEMPLO, fora_do_cadastro={"Rua C"}))
    resumo, saida, _, _ = rodar(tmp_path, cliente=cliente)
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
    _, saida, _, _ = rodar(tmp_path, lista_com_chamados_fora_do_rio())
    do_agregador = rodar_agregador(tmp_path, LISTA_EXEMPLO)
    for nome in ("quadrados.csv", "quadrados.geojson"):
        assert (saida / nome).read_text(encoding="utf-8") == (
            do_agregador / nome
        ).read_text(encoding="utf-8"), f"{nome} traz chamado de fora do Rio"


def test_chamado_fora_do_municipio_conta_como_sem_coordenada_com_linha_propria(tmp_path):
    resumo, saida, _, _ = rodar(tmp_path, lista_com_chamados_fora_do_rio())
    assert resumo.lidos == 19 + 4
    assert resumo.sem_coordenada == 4 + 4
    assert resumo.coordenada_fora_do_municipio == 4
    texto = (saida / "resumo.txt").read_text(encoding="utf-8")
    assert "sem coordenada: 8" in texto
    assert "coordenada fora do município: 4" in texto


def test_chamado_fora_do_municipio_continua_contando_na_rua(tmp_path):
    _, saida, _, _ = rodar(tmp_path, lista_com_chamados_fora_do_rio())
    ruas = {(r["bairro"], r["rua"]): r for r in ler_csv(saida / "ruas.csv")}
    assert ruas[("Centro", "Rua A")]["chamados"] == "10"  # 6 do exemplo e os 4 de fora


def test_resumo_sem_chamado_fora_do_municipio_mostra_zero(tmp_path):
    resumo, saida, _, _ = rodar(tmp_path)
    assert resumo.coordenada_fora_do_municipio == 0
    assert "coordenada fora do município: 0" in (saida / "resumo.txt").read_text(encoding="utf-8")


def test_bigquery_confere_o_ponto_contra_o_contorno_dos_bairros():
    consulta = montar_consultas(BIGQUERY, CLASSIFICACAO_DO_EXEMPLO)["quadrados"]
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
    consulta = montar_consultas(BIGQUERY, CLASSIFICACAO_DO_EXEMPLO)["quadrados"]
    for nome, expressao in coleta.PASSOS_METROS:
        assert f"{expressao} AS {nome}" in consulta, f"o passo {nome} não está na consulta"


def test_pontos_perto_da_borda_caem_no_mesmo_quadrado_que_no_agregador(tmp_path):
    cabecalho = LISTA_EXEMPLO.splitlines()[0]
    texto = cabecalho + "\n" + "".join(
        f"2025-03-01 08:00;;Limpeza;Remoção de entulho;Não consta;Centro;Rua A;{lat};{lon}\n"
        for lon, lat in pontos_perto_da_borda()
    )
    _, saida, _, _ = rodar(tmp_path, texto)
    do_agregador = rodar_agregador(tmp_path, texto)
    assert (saida / "quadrados.csv").read_text(encoding="utf-8") == (
        do_agregador / "quadrados.csv"
    ).read_text(encoding="utf-8")


# ---- A consulta só devolve linhas somadas ---------------------------------------------


def test_cada_consulta_devolve_so_as_colunas_do_formato_de_saida(tmp_path):
    _, _, cliente, _ = rodar(tmp_path)
    consultas = montar_consultas(DUCKDB, CLASSIFICACAO_DO_EXEMPLO)
    esperadas = {
        "ruas": CABECALHO_RUAS,
        "quadrados": CABECALHO_QUADRADOS,
        "resumo": COLUNAS_DO_RESUMO,
        "desenho_das_ruas": COLUNAS_DO_DESENHO,
        "por_subtipo": COLUNAS_POR_SUBTIPO,
        "prazo_por_situacao": ["prazo", "situacao", "chamados"],
        "caixas_dos_bairros": ["bairro", "oeste", "sul", "leste", "norte"],
        "filtros_por_dia": ["quadrado", "dia", *DIMENSOES, "chamados", "fechados"],
        "filtros_por_ano": ["quadrado", "ano", *DIMENSOES, "chamados", "fechados"],
        "filtros_tudo": ["quadrado", *DIMENSOES, "chamados", "fechados"],
    }
    assert set(consultas) == set(esperadas)
    for nome, colunas in esperadas.items():
        devolvidas = cliente.colunas[consultas[nome]]
        assert devolvidas == colunas, f"a consulta {nome} devolveu {devolvidas}"
        assert not set(devolvidas) & COLUNAS_PROIBIDAS


def test_desenho_das_ruas_nao_le_a_tabela_de_chamados():
    for nome in ("desenho_das_ruas", "caixas_dos_bairros"):
        consulta = montar_consultas(BIGQUERY, CLASSIFICACAO_DO_EXEMPLO)[nome]
        assert "adm_central_atendimento_1746" not in consulta, nome
        assert "latitude" not in consulta and "longitude" not in consulta, nome


def test_coleta_para_se_a_consulta_devolver_coluna_a_mais(tmp_path):
    cliente = ClienteFalso(montar_base(LISTA_EXEMPLO), colunas_a_mais=("latitude",))
    with pytest.raises(ValueError, match="latitude"):
        rodar(tmp_path, cliente=cliente)
    assert not (tmp_path / "coleta").exists()


def test_nenhuma_saida_tem_coordenada_identificador_ou_numero_de_porta(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
    conexao = montar_base(LISTA_EXEMPLO)
    proibidos = set()
    for id_chamado, porta, latitude, longitude in conexao.sql(
        "SELECT id_chamado, numero_logradouro, latitude, longitude FROM chamado"
    ).fetchall():
        proibidos |= {id_chamado, str(porta)}
        proibidos |= {repr(v) for v in (latitude, longitude) if v}
    arquivos = {a.name for a in saida.iterdir()}
    assert arquivos == {"ruas.csv", "quadrados.csv", "quadrados.geojson", "ruas.geojson",
                        "resumo.txt", "filtros"}
    for arquivo in saida.rglob("*.*"):
        texto = arquivo.read_text(encoding="utf-8")
        for proibido in proibidos:
            assert not re.search(rf"(?<![\d.]){re.escape(proibido)}(?![\d])", texto), (
                f"{arquivo.name} traz {proibido}"
            )


# ---- ruas.geojson: o desenho das ruas, do cadastro de logradouros, com os totais -----


def test_ruas_geojson_traz_o_desenho_e_os_mesmos_totais_do_csv(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
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
    assert do_geojson[("Glória", "Rua C")]["properties"]["chamados"] == 1


def test_ruas_geojson_arredonda_o_desenho_em_6_casas(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
    for feature in ler_json(saida / "ruas.geojson")["features"]:
        for ponto in feature["geometry"]["coordinates"]:
            for numero in ponto:
                assert numero == round(numero, 6)


def test_rua_sem_desenho_fica_so_no_csv(tmp_path):
    cliente = ClienteFalso(montar_base(LISTA_EXEMPLO, sem_desenho={"Rua C"}))
    resumo, saida, _, _ = rodar(tmp_path, cliente=cliente)
    ruas = {f["properties"]["rua"] for f in ler_json(saida / "ruas.geojson")["features"]}
    assert "Rua C" not in ruas
    assert "Rua C" in {r["rua"] for r in ler_csv(saida / "ruas.csv")}
    assert resumo.ruas == 4 and resumo.ruas_com_desenho == 3


# ---- Simulação (dry run) antes de rodar, com limite configurável ----------------------


QUANTAS = len(montar_consultas(DUCKDB, CLASSIFICACAO_DO_EXEMPLO))


def test_simulacao_vem_antes_de_tudo_e_mostra_os_gb(tmp_path):
    _, _, cliente, avisos = rodar(tmp_path)
    tipos = [tipo for tipo, _, _ in cliente.eventos]
    assert tipos == ["simulação"] * QUANTAS + ["consulta"] * QUANTAS
    for _, _, configuracao in cliente.eventos[:QUANTAS]:
        assert configuracao.use_query_cache is False
    # Consultas de 0,5 GB cada.
    assert any(f"{coleta._gb(QUANTAS / 2)} GB" in aviso for aviso in avisos), avisos


def test_para_antes_de_rodar_se_passar_do_limite(tmp_path):
    cliente = ClienteFalso(montar_base(LISTA_EXEMPLO), bytes_por_consulta=3 * GIB)
    with pytest.raises(LimiteExcedido) as erro:
        rodar(tmp_path, cliente=cliente, limite_gb=10)
    assert f"{coleta._gb(3 * QUANTAS)} GB" in str(erro.value) and "10" in str(erro.value)
    assert "O que fazer:" in str(erro.value)
    assert [tipo for tipo, _, _ in cliente.eventos] == ["simulação"] * QUANTAS
    assert not (tmp_path / "coleta").exists()


def test_consulta_de_verdade_tambem_tem_o_limite(tmp_path):
    # Cada consulta do teste lê 0,5 GB: o limite cabe todas.
    _, _, cliente, _ = rodar(tmp_path, limite_gb=QUANTAS)
    for tipo, _, configuracao in cliente.eventos:
        if tipo == "consulta":
            assert configuracao.maximum_bytes_billed == QUANTAS * GIB


def test_limite_vem_da_linha_de_comando(tmp_path, capsys):
    cliente = ClienteFalso(montar_base(LISTA_EXEMPLO), bytes_por_consulta=3 * GIB)
    codigo = main(
        ["--projeto", "projeto-de-teste", "--saida", str(tmp_path / "s"),
         "--limite-gb", "11"],
        abrir=lambda projeto: cliente, dialeto=DUCKDB,
    )
    assert codigo != 0
    erro = capsys.readouterr().err
    assert f"{coleta._gb(3 * QUANTAS)} GB" in erro and "11" in erro
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
    # Consultas de 1 MB cada, acima de 0,001 GB.
    assert f"{coleta._gb(QUANTAS / 1024)} GB" in str(erro.value)
    assert "limite de 0,001 GB" in str(erro.value)


def test_limite_com_virgula_ou_ponto_pela_linha_de_comando(tmp_path, capsys):
    for limite in ("0,001", "0.001"):
        cliente = ClienteFalso(montar_base(LISTA_EXEMPLO), bytes_por_consulta=1024**2)
        codigo = main(["--projeto", "p", "--saida", str(tmp_path / "s"),
                       "--limite-gb", limite], abrir=lambda projeto: cliente, dialeto=DUCKDB)
        assert codigo != 0
        assert "limite: 0,001 GB" in capsys.readouterr().out


def test_limite_padrao_cabe_no_sandbox_gratuito():
    assert 0 < coleta.LIMITE_GB_PADRAO <= 1024 / 10  # pelo menos 10 coletas no 1 TB do mês


# ---- Sem mínimo de chamados (issue #31) ----------------------------------------------

MENSAGEM_DO_MINIMO = "A opção --minimo saiu (ver decisoes.md). Rode sem ela."


def test_quadrado_com_1_chamado_mostra_1_e_nao_menos_de_n(tmp_path):
    linhas = LISTA_EXEMPLO.splitlines()
    _, saida, _, _ = rodar(tmp_path, "\n".join([linhas[0], linhas[9]]) + "\n")
    (linha,) = ler_csv(saida / "quadrados.csv")
    assert linha["chamados"] == "1"
    (feature,) = ler_json(saida / "quadrados.geojson")["features"]
    assert feature["properties"]["chamados"] == 1
    for arquivo in saida.rglob("*.*"):
        assert "menos de" not in arquivo.read_text(encoding="utf-8"), arquivo.name


def test_rua_com_1_chamado_mostra_o_numero(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
    linha = {(r["bairro"], r["rua"]): r for r in ler_csv(saida / "ruas.csv")}[("Glória", "Rua C")]
    assert linha["chamados"] == "1"


def test_linha_de_comando_com_minimo_para_e_diz_que_a_opcao_saiu(capsys):
    for argumentos in (["--minimo", "5"], ["--minimo"]):
        codigo, mensagem = rodar_comando(capsys, "--projeto", "p", *argumentos)
        assert codigo != 0
        assert MENSAGEM_DO_MINIMO in mensagem


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
        "datario.adm_central_atendimento_1746.chamado",
    ):
        assert trecho in texto, f"o resumo não traz \"{trecho}\""
    assert "mínimo" not in texto


def test_total_dos_quadrados_e_lidos_menos_sem_coordenada(tmp_path):
    resumo, saida, _, _ = rodar(tmp_path)
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
    codigo = main(["--projeto", "p"], abrir=lambda projeto: cliente,
                  dialeto=DUCKDB)
    assert codigo == 0
    assert (tmp_path / "padrao" / "ruas.csv").exists()


# ---- Login do responsável (OAuth), sem senha nem chave no código ----------------------


def test_codigo_nao_tem_chave_nem_arquivo_de_credencial():
    fonte = (RAIZ / "src" / "coleta.py").read_text(encoding="utf-8").lower()
    for proibido in ("service_account", "private_key", "google_application_credentials",
                     "keyfile", "client_secret", "credentials.json", "token.json"):
        assert proibido not in fonte, f"o código cita {proibido}"
    # O único .json da coleta é o das fatias dos filtros (issue #31), num lugar só.
    assert fonte.count('.json"') == 1
    assert 'extensao_das_fatias = ".json"' in fonte


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


def test_sem_projeto_diz_em_portugues_o_que_fazer(capsys):
    codigo, mensagem = rodar_comando(capsys)
    confere_mensagem(codigo, mensagem, "Falta o --projeto")


def test_limite_que_nao_e_numero_diz_em_portugues_o_que_fazer(capsys):
    codigo, mensagem = rodar_comando(capsys, "--projeto", "p", "--limite-gb", "dez")
    confere_mensagem(codigo, mensagem, "--limite-gb")


def test_opcao_desconhecida_diz_em_portugues_o_que_fazer(capsys):
    codigo, mensagem = rodar_comando(capsys, "--projeto", "p", "--cor", "azul")
    confere_mensagem(codigo, mensagem, "--cor", "coleta.py --ajuda")


def test_ajuda_em_portugues(capsys):
    with pytest.raises(SystemExit) as saida:
        main(["--ajuda"])
    assert saida.value.code == 0
    ajuda = capsys.readouterr().out
    assert "uso:" in ajuda and "--limite-gb" in ajuda
    assert "--minimo" not in ajuda
    for ingles in INGLES:
        assert ingles not in ajuda.lower(), f"ajuda em inglês: {ingles}"


# ---- Só problema público (issue #26) --------------------------------------------------

# Cada par tipo/subtipo do 1746 está num grupo da lista de classificação. Por privacidade,
# só o grupo "publico" entra no mapa. Os pares e os chamados daqui são fictícios.

CABECALHO_DA_LISTA = "grupo;tipo;subtipo;motivo"
GRUPOS = {"publico", "denuncia", "pessoal", "sem_lugar", "a_revisar"}

CLASSIFICACAO_FICTICIA = {
    ("Iluminação Pública", "Reparo de lâmpada apagada"): "publico",
    ("Estacionamento Irregular", "Carro na calçada"): "denuncia",
    ("Remoção Gratuita", "Móveis da casa"): "pessoal",
    ("Informação", "Horário de atendimento"): "sem_lugar",
    ("Tipo Em Revisão", "Subtipo em revisão"): "a_revisar",
}


def chamado(tipo, subtipo, *, rua="Rua A", latitude="-22.90668", longitude="-43.173317"):
    """Uma linha de chamado fictício no formato da lista de exemplo."""
    return (f"2025-03-01 08:00;2025-03-02 08:00;{tipo};{subtipo};Atendido;Centro;{rua};"
            f"{latitude};{longitude}\n")


def lista_de_chamados(*grupos_de_linhas):
    return LISTA_EXEMPLO.splitlines()[0] + "\n" + "".join(grupos_de_linhas)


def escrever_lista(tmp_path, texto, nome="lista.csv"):
    caminho = tmp_path / nome
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def texto_do_resumo(saida):
    return (saida / "resumo.txt").read_text(encoding="utf-8")


def test_exemplo_da_issue_26_a_rua_sai_so_com_os_chamados_de_problema_publico(tmp_path):
    # 3 de iluminação (publico), 2 de estacionamento irregular (denuncia) e 1 subtipo novo.
    texto = lista_de_chamados(
        chamado("Iluminação Pública", "Reparo de lâmpada apagada") * 3,
        chamado("Estacionamento Irregular", "Carro na calçada") * 2,
        chamado("Tipo Novo", "Subtipo novo"),
    )
    resumo, saida, _, _ = rodar(tmp_path, texto, classificacao=CLASSIFICACAO_FICTICIA)
    linhas = (saida / "ruas.csv").read_text(encoding="utf-8").splitlines()
    assert linhas[1:] == ["Centro;Rua A;3;3;3;1.0"]
    assert sum(int(q["chamados"]) for q in ler_csv(saida / "quadrados.csv")) == 3
    texto_resumo = texto_do_resumo(saida)
    assert "denuncia: 2" in texto_resumo
    assert "sem classificação: 1" in texto_resumo
    assert resumo.problema_publico == 3


def chamados_dos_cinco_grupos_e_sem_classificacao():
    return lista_de_chamados(
        chamado("Iluminação Pública", "Reparo de lâmpada apagada") * 3,
        chamado("Estacionamento Irregular", "Carro na calçada") * 2,
        chamado("Remoção Gratuita", "Móveis da casa", rua="Rua B") * 4,
        chamado("Informação", "Horário de atendimento", latitude="", longitude="") * 1,
        chamado("Tipo Em Revisão", "Subtipo em revisão") * 5,
        chamado("Tipo Novo", "Subtipo novo") * 4,
        chamado("Outro Tipo Novo", "Outro subtipo", rua="") * 2,
    )


def test_so_os_chamados_de_problema_publico_entram_nas_ruas_e_nos_quadrados(tmp_path):
    _, saida, _, _ = rodar(tmp_path, chamados_dos_cinco_grupos_e_sem_classificacao(),
                           classificacao=CLASSIFICACAO_FICTICIA)
    ruas = ler_csv(saida / "ruas.csv")
    assert [(r["rua"], r["chamados"]) for r in ruas] == [("Rua A", "3")]
    quadrados = ler_csv(saida / "quadrados.csv")
    assert sum(int(q["chamados"]) for q in quadrados) == 3
    geojson = ler_json(saida / "ruas.geojson")
    assert [f["properties"]["rua"] for f in geojson["features"]] == ["Rua A"]


def test_resumo_diz_quantos_ficaram_fora_do_mapa_em_cada_grupo(tmp_path):
    resumo, saida, _, _ = rodar(tmp_path, chamados_dos_cinco_grupos_e_sem_classificacao(),
                                classificacao=CLASSIFICACAO_FICTICIA)
    assert resumo.lidos == 21
    assert resumo.problema_publico == 3
    assert resumo.fora_do_mapa == {"denuncia": 2, "pessoal": 4, "sem_lugar": 1, "a_revisar": 5,
                                   "sem classificação": 6}
    texto = texto_do_resumo(saida)
    for trecho in ("chamados lidos: 21", "chamados de problema público (entram no mapa): 3",
                   "denuncia: 2", "pessoal: 4", "sem_lugar: 1", "a_revisar: 5",
                   "sem classificação: 6"):
        assert trecho in texto, f"o resumo não traz \"{trecho}\""


def test_resumo_lista_os_pares_sem_classificacao_para_completar_a_lista(tmp_path):
    resumo, saida, _, _ = rodar(tmp_path, chamados_dos_cinco_grupos_e_sem_classificacao(),
                                classificacao=CLASSIFICACAO_FICTICIA)
    assert resumo.sem_classificacao == [("Tipo Novo", "Subtipo novo", 4),
                                        ("Outro Tipo Novo", "Outro subtipo", 2)]
    texto = texto_do_resumo(saida)
    assert "pares tipo/subtipo sem classificação: 2" in texto
    # Do que tem mais chamados para o que tem menos.
    assert texto.index("- Tipo Novo / Subtipo novo: 4") < texto.index(
        "- Outro Tipo Novo / Outro subtipo: 2")
    # Os pares "a_revisar" já estão na lista: não entram nesta relação.
    assert "Tipo Em Revisão" not in texto


def test_resumo_sem_par_sem_classificacao_mostra_zero(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
    texto = texto_do_resumo(saida)
    assert "sem classificação: 0" in texto
    assert "pares tipo/subtipo sem classificação: 0" in texto


def test_sem_rua_e_sem_coordenada_contam_so_os_chamados_de_problema_publico(tmp_path):
    texto = lista_de_chamados(
        chamado("Iluminação Pública", "Reparo de lâmpada apagada") * 3,
        chamado("Iluminação Pública", "Reparo de lâmpada apagada", rua="", latitude="",
                longitude=""),
        chamado("Estacionamento Irregular", "Carro na calçada", rua="", latitude="",
                longitude="") * 5,
    )
    resumo, saida, _, _ = rodar(tmp_path, texto, classificacao=CLASSIFICACAO_FICTICIA)
    assert resumo.sem_rua == 1 and resumo.sem_coordenada == 1
    total = sum(int(q["chamados"]) for q in ler_csv(saida / "quadrados.csv"))
    assert total == resumo.problema_publico - resumo.sem_coordenada == 3
    assert "entre os chamados de problema público:" in texto_do_resumo(saida)


def test_a_filtragem_acontece_dentro_do_bigquery():
    consultas = montar_consultas(BIGQUERY, CLASSIFICACAO_FICTICIA)
    for nome in ("ruas", "quadrados", "resumo"):
        consulta = consultas[nome]
        assert "('Iluminação Pública', 'Reparo de lâmpada apagada')" in consulta, nome
        for outro in ("Estacionamento Irregular", "Remoção Gratuita", "Informação",
                      "Tipo Em Revisão"):
            assert outro not in consulta, f"a consulta {nome} traz o par {outro}"
        assert "UNNEST(ARRAY<STRUCT<tipo STRING, subtipo STRING>>[" in consulta
    # A consulta por subtipo só soma: tipo, subtipo e quantos chamados.
    assert "GROUP BY" in consultas["por_subtipo"]
    assert "latitude" not in consultas["por_subtipo"]


def test_compara_tipo_e_subtipo_sem_os_espacos_do_comeco_e_do_fim(tmp_path):
    # Na lista há tipos com espaço no fim ("Acessibilidade Digital "); na tabela pode haver
    # também, ou não. A comparação tira os espaços dos dois lados.
    caminho = escrever_lista(tmp_path, "\n".join([
        CABECALHO_DA_LISTA,
        "publico;Acessibilidade Digital ;Locais disponíveis;espaço ou serviço público",
        "publico;Iluminação Pública; Reparo de lâmpada apagada ;espaço ou serviço público",
        "denuncia;Estacionamento Irregular;Carro na calçada;aponta uma pessoa",
    ]) + "\n")
    classificacao = ler_classificacao(caminho)
    assert ("Acessibilidade Digital", "Locais disponíveis") in classificacao
    texto = lista_de_chamados(
        chamado("Acessibilidade Digital", "Locais disponíveis"),
        chamado("  Acessibilidade Digital  ", "Locais disponíveis "),
        chamado("Iluminação Pública ", "Reparo de lâmpada apagada"),
        chamado("Estacionamento Irregular   ", "  Carro na calçada"),
    )
    resumo, saida, _, _ = rodar(tmp_path, texto, classificacao=classificacao)
    assert resumo.problema_publico == 3
    assert resumo.fora_do_mapa["denuncia"] == 1
    assert resumo.fora_do_mapa["sem classificação"] == 0
    assert ler_csv(saida / "ruas.csv")[0]["chamados"] == "3"


def test_par_que_so_se_repete_pelos_espacos_conta_uma_vez(tmp_path):
    caminho = escrever_lista(tmp_path, "\n".join([
        CABECALHO_DA_LISTA,
        "publico;Transporte Escolar; Inclusão de Veículo;espaço ou serviço público",
        "publico;Transporte Escolar;Inclusão de Veículo;espaço ou serviço público",
    ]) + "\n")
    classificacao = ler_classificacao(caminho)
    assert classificacao == {("Transporte Escolar", "Inclusão de Veículo"): "publico"}
    texto = lista_de_chamados(chamado("Transporte Escolar", "Inclusão de Veículo"))
    _, saida, _, _ = rodar(tmp_path, texto, classificacao=classificacao)
    assert ler_csv(saida / "ruas.csv")[0]["chamados"] == "1"


APOSTROFO = chr(39)
BARRA = chr(92)


def test_subtipo_com_apostrofo_funciona(tmp_path):
    subtipo = f"Benefício {APOSTROFO}causa mortis{APOSTROFO}"
    classificacao = {("Táxi", subtipo): "publico"}
    texto = lista_de_chamados(chamado("Táxi", subtipo) * 2)
    resumo, _, _, _ = rodar(tmp_path, texto, classificacao=classificacao)
    assert resumo.problema_publico == 2
    # No BigQuery, o apóstrofo vai com barra invertida antes, e a barra invertida também.
    assert BIGQUERY.texto(f"OPM{APOSTROFO}s") == f"{APOSTROFO}OPM{BARRA}{APOSTROFO}s{APOSTROFO}"
    assert BIGQUERY.texto(f"a{BARRA}b") == f"{APOSTROFO}a{BARRA}{BARRA}b{APOSTROFO}"


def test_chamado_sem_subtipo_fica_sem_classificacao(tmp_path):
    texto = lista_de_chamados(chamado("Iluminação Pública", ""))
    resumo, _, _, _ = rodar(tmp_path, texto, classificacao=CLASSIFICACAO_FICTICIA)
    assert resumo.problema_publico == 0
    assert resumo.sem_classificacao == [("Iluminação Pública", "", 1)]


class ClienteQueNaoBate(ClienteFalso):
    """Devolve um chamado a mais na contagem por subtipo, como se a conta não batesse."""

    def query(self, sql, job_config=None):
        trabalho = super().query(sql, job_config)
        resultado = trabalho._resultado
        if resultado is not None and [c.name for c in resultado.schema] == COLUNAS_POR_SUBTIPO:
            resultado[0]["chamados"] += 1
        return trabalho


def test_coleta_para_se_a_conta_por_grupo_nao_bate_com_a_do_mapa(tmp_path):
    cliente = ClienteQueNaoBate(montar_base(LISTA_EXEMPLO))
    with pytest.raises(ValueError, match="não bate") as erro:
        rodar(tmp_path, cliente=cliente)
    assert "O que fazer:" in str(erro.value)
    assert not (tmp_path / "coleta").exists()


def test_consultas_com_a_lista_de_verdade_cabem_no_limite_do_bigquery():
    # O BigQuery aceita consultas de até 1.024 mil caracteres.
    classificacao = ler_classificacao(CLASSIFICACAO_PADRAO)
    for nome, consulta in montar_consultas(BIGQUERY, classificacao).items():
        assert len(consulta) < 1_000_000, nome


# ---- A lista de classificação: no repositório e lida pela coleta ----------------------


def test_lista_de_classificacao_esta_no_repositorio_com_os_cinco_grupos():
    assert CLASSIFICACAO_PADRAO.is_relative_to(RAIZ / "_referencias")
    assert CLASSIFICACAO_PADRAO.exists()
    assert b"\r" not in CLASSIFICACAO_PADRAO.read_bytes()
    classificacao = ler_classificacao(CLASSIFICACAO_PADRAO)
    assert set(classificacao.values()) == GRUPOS
    assert len(classificacao) > 5000


def test_coleta_le_a_lista_do_repositorio_por_padrao(tmp_path, monkeypatch):
    # Uma lista fictícia em que só tapa-buraco é de problema público.
    lista = escrever_lista(tmp_path, "\n".join([
        CABECALHO_DA_LISTA,
        "publico;Conservação;Tapa-buraco;espaço ou serviço público",
        "pessoal;Limpeza;Remoção de entulho;pedido da própria casa",
    ]) + "\n")
    monkeypatch.setattr(coleta, "CLASSIFICACAO_PADRAO", lista)
    cliente = ClienteFalso(montar_base(LISTA_EXEMPLO))
    saida = tmp_path / "s"
    codigo = main(["--projeto", "p", "--saida", str(saida)],
                  abrir=lambda projeto: cliente, dialeto=DUCKDB)
    assert codigo == 0
    assert [(r["bairro"], r["rua"]) for r in ler_csv(saida / "ruas.csv")] == [("Tijuca", "Rua A")]


def test_lista_pode_vir_de_outro_arquivo_pela_linha_de_comando(tmp_path):
    lista = escrever_lista(tmp_path, "\n".join([
        CABECALHO_DA_LISTA, "publico;Limpeza;Remoção de entulho;espaço ou serviço público",
    ]) + "\n")
    cliente = ClienteFalso(montar_base(LISTA_EXEMPLO))
    saida = tmp_path / "s"
    codigo = main(["--projeto", "p", "--saida", str(saida),
                   "--classificacao", str(lista)], abrir=lambda projeto: cliente, dialeto=DUCKDB)
    assert codigo == 0
    assert {r["rua"] for r in ler_csv(saida / "ruas.csv")} == {"Rua B"}


LISTAS_MALFORMADAS = {
    "vazia": ("", "cabeçalho"),
    "cabeçalho errado": ("grupo;tipo;subtipo\npublico;A;B\n", "cabeçalho"),
    "coluna a menos": (f"{CABECALHO_DA_LISTA}\npublico;A;B;x\npublico;C;D\n", "linha 3"),
    "grupo desconhecido": (f"{CABECALHO_DA_LISTA}\npublica;A;B;x\n", "publica"),
    "tipo vazio": (f"{CABECALHO_DA_LISTA}\npublico; ;B;x\n", "linha 2"),
    "par em dois grupos": (
        f"{CABECALHO_DA_LISTA}\npublico;A;B;x\ndenuncia;A ;B;y\n", "linhas 2 e 3"),
    "sem nenhum par publico": (f"{CABECALHO_DA_LISTA}\ndenuncia;A;B;x\n", "publico"),
}


@pytest.mark.parametrize("caso", LISTAS_MALFORMADAS)
def test_lista_malformada_para_a_coleta_e_diz_o_que_fazer(tmp_path, caso):
    texto, trecho = LISTAS_MALFORMADAS[caso]
    caminho = escrever_lista(tmp_path, texto)
    with pytest.raises(ListaInvalida) as erro:
        ler_classificacao(caminho)
    assert trecho in str(erro.value)
    assert "O que fazer:" in str(erro.value)


def test_lista_que_nao_esta_em_utf8_diz_o_que_fazer(tmp_path):
    caminho = tmp_path / "lista.csv"
    caminho.write_bytes(f"{CABECALHO_DA_LISTA}\npublico;Iluminação;Lâmpada;x\n".encode("cp1252"))
    with pytest.raises(ListaInvalida) as erro:
        ler_classificacao(caminho)
    assert "UTF-8" in str(erro.value) and "O que fazer:" in str(erro.value)


def test_sem_a_lista_a_coleta_para_antes_de_abrir_o_bigquery(tmp_path, capsys):
    codigo, mensagem = rodar_comando(capsys, "--projeto", "p",
                                     "--classificacao", str(tmp_path / "nao_existe.csv"))
    confere_mensagem(codigo, mensagem, "lista de classificação", "nao_existe.csv")


def test_pagina_de_metodo_le_o_resumo_que_a_coleta_grava(tmp_path):
    # As duas pontas juntas: o resumo da coleta, com os grupos, lido pelo montador do site.
    from montar_site import montar_site

    _, saida, _, _ = rodar(tmp_path, chamados_dos_cinco_grupos_e_sem_classificacao(),
                           classificacao=CLASSIFICACAO_FICTICIA)
    site = tmp_path / "site"
    montar_site(saida, site)
    pagina = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (site / "metodo.html").read_text(
        encoding="utf-8")))
    assert "Dos 21 chamados lidos, 3 (14,3%) são de problema público" in pagina
    assert "Denúncia, que pode apontar vizinho, carro, obra, estabelecimento ou imóvel: 2 chamados" in pagina
    assert "Subtipo que não está na lista de classificação: 6 chamados" in pagina
    assert "LGPD" in pagina


# ---- Fatias dos filtros do mapa (issue #31) -------------------------------------------

# O que cada linha de uma fatia pode ter. Nada além disso sai na pasta filtros/.
COLUNAS_DAS_FATIAS = {"q", "d", "t", "e", "p", "o", "n", "f"}


def fatias(saida):
    pasta = saida / "filtros"
    return {arquivo.name: ler_json(arquivo) for arquivo in sorted(pasta.glob("*.json"))
            if arquivo.name != "indice.json"}


def linhas_da_fatia(fatia):
    """As linhas da fatia, com o "q" já como posição do quadrado (soma das diferenças)."""
    colunas = list(fatia)
    tamanho = len(fatia["q"])
    assert all(len(fatia[c]) == tamanho for c in colunas), "colunas de tamanhos diferentes"
    linhas, quadrado = [], 0
    for i in range(tamanho):
        linha = {c: fatia[c][i] for c in colunas}
        quadrado += linha["q"]
        linha["q"] = quadrado
        linhas.append(linha)
    return linhas


def somar_fatia(fatia, indice, **filtro):
    """{quadrado: [chamados, atendidos, fechados]} da fatia, com o filtro (nome: [valores])."""
    listas = {"t": indice["temas"], "p": indice["prazos"], "o": indice["orgaos"]}
    nomes = {"tema": "t", "prazo": "p", "orgao": "o"}
    totais = {}
    for linha in linhas_da_fatia(fatia):
        if any(listas[nomes[nome]][linha[nomes[nome]]] not in valores
               for nome, valores in filtro.items()):
            continue
        quadrado = indice["quadrados"][linha["q"]]
        atendido = indice["estados"][linha["e"]][2] == "Atendido"
        soma = totais.setdefault(quadrado, [0, 0, 0])
        soma[0] += linha["n"]
        soma[1] += linha["n"] if atendido else 0
        soma[2] += linha["f"]
    return totais


def test_coleta_grava_as_fatias_por_mes_por_ano_e_tudo(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
    nomes = {arquivo.name for arquivo in (saida / "filtros").iterdir()}
    # Os chamados com coordenada do exemplo são de março a junho de 2025.
    assert nomes == {"indice.json", "tudo.json", "2025.json", "2025-03.json", "2025-04.json",
                     "2025-05.json", "2025-06.json"}
    indice = ler_json(saida / "filtros" / "indice.json")
    assert indice["meses"] == ["2025-03", "2025-04", "2025-05", "2025-06"]
    assert indice["anos"] == [2025]


def test_sem_filtro_as_fatias_somam_os_mesmos_totais_dos_quadrados(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
    indice = ler_json(saida / "filtros" / "indice.json")
    esperado = {q["quadrado"]: [int(q["chamados"]), int(q["atendidos"]), int(q["fechados"])]
                for q in ler_csv(saida / "quadrados.csv")}
    todas = fatias(saida)
    assert somar_fatia(todas["tudo.json"], indice) == esperado
    assert somar_fatia(todas["2025.json"], indice) == esperado
    por_mes = {}
    for nome, fatia in todas.items():
        if re.fullmatch(r"\d{4}-\d{2}\.json", nome):
            for quadrado, soma in somar_fatia(fatia, indice).items():
                total = por_mes.setdefault(quadrado, [0, 0, 0])
                for i, valor in enumerate(soma):
                    total[i] += valor
    assert por_mes == esperado


def test_com_tema_a_fatia_soma_so_os_chamados_do_tema(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
    indice = ler_json(saida / "filtros" / "indice.json")
    tudo = fatias(saida)["tudo.json"]
    # Q2 (687400_7465600): 2 chamados da Limpeza na Rua B e 2 sem rua, também da Limpeza.
    assert somar_fatia(tudo, indice, tema=["Limpeza"]) == {"687400_7465600": [4, 1, 1]}
    assert somar_fatia(tudo, indice, tema=["Conservação"]) == {"680000_7464000": [5, 3, 4]}


def test_a_fatia_do_mes_traz_o_dia_de_abertura(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
    linhas = linhas_da_fatia(fatias(saida)["2025-05.json"])
    # Tijuca: abertos de 1 a 5 de maio de 2025, um por dia.
    assert sorted(linha["d"] for linha in linhas) == [1, 2, 3, 4, 5]
    assert "d" not in fatias(saida)["2025.json"] and "d" not in fatias(saida)["tudo.json"]


def test_as_fatias_so_tem_as_colunas_dos_totais(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
    for nome, fatia in fatias(saida).items():
        assert set(fatia) <= COLUNAS_DAS_FATIAS, f"{nome}: {set(fatia) - COLUNAS_DAS_FATIAS}"
        for coluna, valores in fatia.items():
            assert all(isinstance(valor, int) for valor in valores), (nome, coluna)


def test_indice_so_tem_as_listas_dos_filtros(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
    indice = ler_json(saida / "filtros" / "indice.json")
    assert set(indice) == {"formato", "quadrados", "temas", "estados", "prazos", "orgaos", "meses",
                           "anos", "primeiro_dia", "ultimo_dia", "bairros"}
    assert indice["quadrados"] == [q["quadrado"] for q in ler_csv(saida / "quadrados.csv")]
    assert sorted(indice["temas"]) == ["Conservação", "Iluminação Pública", "Limpeza"]
    assert sorted(indice["prazos"]) == ["No prazo"]
    assert sorted(indice["orgaos"]) == sorted(ORGAO_DO_TIPO.values())
    assert ["Fechado", "Encerrado", "Atendido"] in indice["estados"]


def test_a_lista_de_tema_nao_tem_tipo_de_fora_do_grupo_publico(tmp_path):
    texto = lista_de_chamados(
        chamado("Iluminação Pública", "Reparo de lâmpada apagada"),
        chamado("Estacionamento Irregular", "Carro na calçada"),
        chamado("Remoção Gratuita", "Móveis da casa"),
        chamado("Tipo Em Revisão", "Subtipo em revisão"),
        chamado("Tipo Sem Lista", "Subtipo sem lista"),
    )
    _, saida, _, _ = rodar(tmp_path, texto, classificacao=CLASSIFICACAO_FICTICIA)
    indice = ler_json(saida / "filtros" / "indice.json")
    assert indice["temas"] == ["Iluminação Pública"]
    for arquivo in (saida / "filtros").iterdir():
        texto_da_fatia = arquivo.read_text(encoding="utf-8")
        for tipo in ("Estacionamento", "Remoção Gratuita", "Em Revisão", "Sem Lista"):
            assert tipo not in texto_da_fatia, (arquivo.name, tipo)


def test_indice_traz_o_primeiro_e_o_ultimo_dia_com_chamados(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
    indice = ler_json(saida / "filtros" / "indice.json")
    # Os chamados sem coordenada (até 01/07/2025) não entram no mapa nem no calendário.
    assert indice["primeiro_dia"] == "2025-03-01"
    assert indice["ultimo_dia"] == "2025-06-02"


def test_indice_traz_a_caixa_de_cada_bairro_do_cadastro(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
    bairros = ler_json(saida / "filtros" / "indice.json")["bairros"]
    oeste, sul, leste, norte = CAIXA_DO_BAIRRO["Tijuca"]
    assert bairros["Tijuca"] == [sul, oeste, norte, leste]
    assert set(bairros) == set(CAIXA_DO_BAIRRO)


def test_as_fatias_nao_tem_identificador_nem_coordenada(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
    conexao = montar_base(LISTA_EXEMPLO)
    proibidos = set()
    for id_chamado, porta, latitude, longitude in conexao.sql(
        "SELECT id_chamado, numero_logradouro, latitude, longitude FROM chamado"
    ).fetchall():
        proibidos |= {id_chamado, str(porta)}
        proibidos |= {repr(v) for v in (latitude, longitude) if v}
    for arquivo in (saida / "filtros").iterdir():
        texto = arquivo.read_text(encoding="utf-8")
        for campo in ("id_chamado", "latitude", "longitude", "numero_logradouro", "subtipo",
                      "data_fim", "Rua A", "Rua B", "Reparo de lâmpada"):
            assert campo not in texto, f"{arquivo.name} traz {campo}"
        for proibido in proibidos:
            assert not re.search(rf"(?<![\d.]){re.escape(proibido)}(?![\d])", texto), (
                f"{arquivo.name} traz {proibido}"
            )


def test_coleta_de_novo_apaga_as_fatias_antigas(tmp_path):
    _, saida, _, _ = rodar(tmp_path)
    (saida / "filtros" / "2010-01.json").write_text("{}", encoding="utf-8")
    rodar(tmp_path)
    assert not (saida / "filtros" / "2010-01.json").exists()


# ---- Prazo cruzado com a situação, no resumo (issue #31) ------------------------------


def test_resumo_cruza_o_prazo_com_a_situacao(tmp_path):
    linhas = LISTA_EXEMPLO.splitlines()
    cabecalho = linhas[0] + ";dentro_prazo;situacao"
    texto = cabecalho + "\n" + "".join(
        f"{linha};{'A Vencer' if i % 2 else 'No prazo'};{'Encerrado' if i < 10 else 'Não Encerrado'}\n"
        for i, linha in enumerate(linhas[1:])
    )
    _, saida, _, _ = rodar(tmp_path, texto)
    resumo = (saida / "resumo.txt").read_text(encoding="utf-8")
    bloco = resumo.split(
        "prazo (dentro_prazo) por situação, entre os chamados de problema público:\n"
    )[1].split("GB lidos")[0]
    assert bloco.splitlines() == [
        "  A Vencer / Encerrado: 5",
        "  A Vencer / Não Encerrado: 4",
        "  No prazo / Encerrado: 5",
        "  No prazo / Não Encerrado: 5",
    ]
