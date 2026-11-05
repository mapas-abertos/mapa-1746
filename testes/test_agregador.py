"""Testes do agregador (issue #7): totais por rua e por quadrado de 100 m.

Cada teste nasce de um item do "Quando está pronta" da issue, antes do código (TDD).
Todos os chamados daqui são fictícios: ruas, datas e coordenadas inventadas.
"""

import csv
import json
from datetime import date
from pathlib import Path

import pytest
from pyproj import Transformer

from agregador import EntradaInvalida, agregar, main

RAIZ = Path(__file__).resolve().parent.parent

# Lista de exemplo fictícia, no formato da tabela do 1746 (separada por ponto e vírgula).
# Quadrados de 100 m em que os chamados caem (canto sudoeste, em metros EPSG:31983):
#   Q1 687300_7465600 (Centro): linhas 1 a 6
#   Q2 687400_7465600 (Centro): linhas 7, 8, 14 e 15
#   Q3 680000_7464000 (Tijuca): linhas 9 a 13
# As linhas 16 a 19 não têm coordenada; as 14 e 15 não têm rua.
LISTA_EXEMPLO = """\
data_inicio;data_fim;tipo;subtipo;tipo_situacao;bairro;rua;latitude;longitude
2025-03-01 08:00;2025-03-01 20:00;Iluminação Pública;Reparo de lâmpada apagada;Atendido;Centro;Rua A;-22.90668;-43.173317
2025-03-02 08:00;2025-03-03 08:00;Iluminação Pública;Reparo de lâmpada apagada;Atendido;Centro;Rua A;-22.906652;-43.173288
2025-03-03 08:00;2025-03-05 08:00;Iluminação Pública;Reparo de lâmpada apagada;Não atendido;Centro;Rua A;-22.906483;-43.173534
2025-03-04 08:00;2025-03-07 08:00;Iluminação Pública;Reparo de lâmpada apagada;Atendido;Centro;Rua A;-22.90684;-43.173139
2025-03-05 08:00;;Iluminação Pública;Reparo de lâmpada apagada;Não consta;Centro;Rua A;-22.906573;-43.173435
2025-03-06 08:00;;Iluminação Pública;Reparo de lâmpada apagada;Não consta;Centro;Rua A;-22.90675;-43.173189
2025-04-01 10:00;2025-04-02 10:00;Limpeza;Remoção de entulho;Atendido;Centro;Rua B;-22.906606;-43.17246
2025-04-02 10:00;;Limpeza;Remoção de entulho;Não consta;Centro;Rua B;-22.906695;-43.172264
2025-05-01 09:00;2025-05-11 09:00;Conservação;Tapa-buraco;Atendido;Tijuca;Rua A;-22.921911;-43.244299
2025-05-02 09:00;2025-05-06 09:00;Conservação;Tapa-buraco;Atendido;Tijuca;Rua A;-22.921732;-43.244496
2025-05-03 09:00;2025-05-05 09:00;Conservação;Tapa-buraco;Atendido;Tijuca;Rua A;-22.922089;-43.244102
2025-05-04 09:00;;Conservação;Tapa-buraco;Não consta;Tijuca;Rua A;-22.921819;-43.244203
2025-05-05 09:00;2025-05-06 09:00;Conservação;Tapa-buraco;Não atendido;Tijuca;Rua A;-22.922002;-43.244395
2025-06-01 07:00;;Limpeza;Remoção de entulho;Não consta;Centro;0;-22.90661;-43.17247
2025-06-02 07:00;;Limpeza;Remoção de entulho;Não consta;Centro;;-22.9067;-43.17227
2025-06-03 10:00;2025-06-05 10:00;Limpeza;Remoção de entulho;Atendido;Centro;Rua B;;
2025-06-04 10:00;;Limpeza;Remoção de entulho;Não consta;Centro;Rua B;0;0
2025-06-05 10:00;;Limpeza;Remoção de entulho;Não consta;Centro;Rua B;-22.9066;0
2025-07-01 12:00;;Iluminação Pública;Reparo de lâmpada apagada;Não consta;Glória;Rua C;;
"""

# O exemplo da própria issue #7.
EXEMPLO_DA_ISSUE = """\
data_inicio;data_fim;tipo;subtipo;tipo_situacao;bairro;rua;latitude;longitude
2025-03-01 10:00;2025-03-04 10:00;Iluminação Pública;Reparo de lâmpada apagada;Atendido;Centro;Rua Exemplo;-22.9035;-43.1790
2025-03-02 09:00;;Iluminação Pública;Reparo de lâmpada apagada;Não consta;Centro;Rua Exemplo;-22.9036;-43.1791
2025-03-05 08:00;2025-03-06 08:00;Limpeza;Remoção de entulho;Atendido;Centro;0;0;0
"""

CABECALHO_RUAS = ["bairro", "rua", "chamados", "atendidos", "fechados", "mediana_dias_ate_fechar"]
CABECALHO_QUADRADOS = ["quadrado", "chamados", "atendidos", "fechados", "mediana_dias_ate_fechar"]

# Caixa que contém o município do Rio de Janeiro, em graus.
RIO_LATITUDE = (-23.10, -22.70)
RIO_LONGITUDE = (-43.85, -43.05)

PARA_METROS = Transformer.from_crs("EPSG:4326", "EPSG:31983", always_xy=True)


# ---- Ajudantes ------------------------------------------------------------------------


def rodar(tmp_path, texto=LISTA_EXEMPLO, minimo=5, **opcoes):
    entrada = tmp_path / "chamados.csv"
    entrada.write_text(texto, encoding="utf-8")
    saida = tmp_path / "saida"
    resumo = agregar(entrada, saida, minimo=minimo, **opcoes)
    return resumo, saida


def ler_csv(caminho):
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo, delimiter=";"))


def cabecalho(caminho):
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        return next(csv.reader(arquivo, delimiter=";"))


def ler_geojson(saida):
    return json.loads((saida / "quadrados.geojson").read_text(encoding="utf-8"))


def por_rua(saida):
    return {(linha["bairro"], linha["rua"]): linha for linha in ler_csv(saida / "ruas.csv")}


def coordenadas_dos_chamados(texto):
    """(longitude, latitude) de cada chamado que tem coordenada."""
    pontos = []
    for linha in csv.DictReader(texto.splitlines(), delimiter=";"):
        lat, lon = linha["latitude"], linha["longitude"]
        if lat and lon and float(lat) != 0 and float(lon) != 0:
            pontos.append((float(lon), float(lat)))
    return pontos


def dentro_do_poligono(ponto, anel):
    """Se o ponto (x, y) está dentro do polígono (lista de vértices fechada)."""
    x, y = ponto
    dentro = False
    for (x1, y1), (x2, y2) in zip(anel, anel[1:]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dentro = not dentro
    return dentro


# ---- ruas.csv: total, atendidos, fechados e mediana por rua e bairro ------------------


def test_exemplo_da_issue_da_a_linha_esperada_em_ruas_csv(tmp_path):
    resumo, saida = rodar(tmp_path, EXEMPLO_DA_ISSUE, minimo=1)
    linhas = (saida / "ruas.csv").read_text(encoding="utf-8").splitlines()
    assert linhas == [";".join(CABECALHO_RUAS), "Centro;Rua Exemplo;2;1;1;3.0"]
    assert resumo.sem_rua == 1
    assert resumo.sem_coordenada == 1


def test_ruas_csv_traz_total_atendidos_fechados_e_mediana_de_cada_rua_e_bairro(tmp_path):
    _, saida = rodar(tmp_path)
    assert cabecalho(saida / "ruas.csv") == CABECALHO_RUAS
    ruas = por_rua(saida)
    # Rua A no Centro: 6 chamados, 3 atendidos, 4 fechados em 0,5, 1, 2 e 3 dias.
    assert ruas[("Centro", "Rua A")] == {
        "bairro": "Centro", "rua": "Rua A", "chamados": "6", "atendidos": "3",
        "fechados": "4", "mediana_dias_ate_fechar": "1.5",
    }
    # Rua B no Centro: 5 chamados (3 deles sem coordenada contam na rua), fechados em 1 e 2 dias.
    assert ruas[("Centro", "Rua B")]["chamados"] == "5"
    assert ruas[("Centro", "Rua B")]["atendidos"] == "2"
    assert ruas[("Centro", "Rua B")]["fechados"] == "2"
    assert ruas[("Centro", "Rua B")]["mediana_dias_ate_fechar"] == "1.5"


def test_mesma_rua_em_bairros_diferentes_conta_separado(tmp_path):
    _, saida = rodar(tmp_path)
    ruas = por_rua(saida)
    assert ruas[("Tijuca", "Rua A")]["chamados"] == "5"
    # Fechados em 10, 4, 2 e 1 dias: a mediana é a média dos dois do meio, (2 + 4) / 2.
    assert ruas[("Tijuca", "Rua A")]["mediana_dias_ate_fechar"] == "3.0"
    assert ruas[("Centro", "Rua A")]["chamados"] == "6"


def test_rua_sem_chamado_fechado_fica_sem_mediana(tmp_path):
    texto = LISTA_EXEMPLO.splitlines()[0] + "\n" + (
        "2025-03-05 08:00;;Limpeza;Remoção de entulho;Não consta;Centro;Rua D;;\n"
    )
    _, saida = rodar(tmp_path, texto, minimo=1)
    linha = por_rua(saida)[("Centro", "Rua D")]
    assert linha["fechados"] == "0"
    assert linha["mediana_dias_ate_fechar"] == ""


# ---- Quadrados de 100 m na grade EPSG:31983 ------------------------------------------


def test_cada_chamado_com_coordenada_cai_em_exatamente_um_quadrado(tmp_path):
    _, saida = rodar(tmp_path, minimo=1)
    aneis = [f["geometry"]["coordinates"][0] for f in ler_geojson(saida)["features"]]
    for ponto in coordenadas_dos_chamados(LISTA_EXEMPLO):
        quantos = sum(dentro_do_poligono(ponto, anel) for anel in aneis)
        assert quantos == 1, f"o chamado em {ponto} caiu em {quantos} quadrados"


def test_quadrados_tem_100_m_de_lado_e_cantos_em_multiplos_de_100_m(tmp_path):
    _, saida = rodar(tmp_path, minimo=1)
    for feature in ler_geojson(saida)["features"]:
        anel = feature["geometry"]["coordinates"][0]
        assert len(anel) == 5 and anel[0] == anel[-1], "o contorno do quadrado tem de fechar"
        em_metros = [PARA_METROS.transform(lon, lat) for lon, lat in anel[:4]]
        for x, y in em_metros:
            assert abs(x - round(x / 100) * 100) < 1, f"canto fora da grade: x = {x}"
            assert abs(y - round(y / 100) * 100) < 1, f"canto fora da grade: y = {y}"
        xs = sorted(round(x) for x, _ in em_metros)
        ys = sorted(round(y) for _, y in em_metros)
        assert xs[-1] - xs[0] == 100 and ys[-1] - ys[0] == 100


def test_quadrado_e_identificado_pelo_canto_sudoeste_em_metros(tmp_path):
    _, saida = rodar(tmp_path, minimo=1)
    quadrados = {linha["quadrado"] for linha in ler_csv(saida / "quadrados.csv")}
    assert quadrados == {"687300_7465600", "687400_7465600", "680000_7464000"}


def test_dois_chamados_a_poucos_metros_no_mesmo_quadrado_somam_juntos(tmp_path):
    # As duas primeiras linhas do exemplo estão a uns 4 m uma da outra.
    linhas = LISTA_EXEMPLO.splitlines()
    _, saida = rodar(tmp_path, "\n".join(linhas[:3]) + "\n", minimo=1)
    quadrados = ler_csv(saida / "quadrados.csv")
    assert len(quadrados) == 1
    assert quadrados[0]["chamados"] == "2"


def test_total_dos_quadrados_e_o_numero_de_chamados_com_coordenada(tmp_path):
    resumo, saida = rodar(tmp_path, minimo=1)
    total = sum(int(linha["chamados"]) for linha in ler_csv(saida / "quadrados.csv"))
    assert total == len(coordenadas_dos_chamados(LISTA_EXEMPLO)) == 15
    assert total == resumo.contados - resumo.sem_coordenada


# ---- quadrados.geojson e quadrados.csv ------------------------------------------------


def test_quadrados_geojson_traz_poligonos_dentro_do_rio(tmp_path):
    _, saida = rodar(tmp_path)
    geojson = ler_geojson(saida)
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 3
    for feature in geojson["features"]:
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Polygon"
        for lon, lat in feature["geometry"]["coordinates"][0]:
            assert RIO_LATITUDE[0] < lat < RIO_LATITUDE[1], "latitude fora do Rio"
            assert RIO_LONGITUDE[0] < lon < RIO_LONGITUDE[1], "longitude fora do Rio"


def test_quadrados_csv_traz_os_mesmos_totais_do_geojson(tmp_path):
    _, saida = rodar(tmp_path)
    assert cabecalho(saida / "quadrados.csv") == CABECALHO_QUADRADOS
    do_csv = {linha["quadrado"]: linha for linha in ler_csv(saida / "quadrados.csv")}
    do_geojson = {f["properties"]["quadrado"]: f["properties"] for f in ler_geojson(saida)["features"]}
    assert set(do_csv) == set(do_geojson)
    for quadrado, linha in do_csv.items():
        propriedades = do_geojson[quadrado]
        for coluna in CABECALHO_QUADRADOS[1:]:
            valor = propriedades[coluna]
            assert linha[coluna] == ("" if valor is None else str(valor)), (quadrado, coluna)


def test_quadrado_com_numeros_certos(tmp_path):
    _, saida = rodar(tmp_path)
    do_csv = {linha["quadrado"]: linha for linha in ler_csv(saida / "quadrados.csv")}
    assert do_csv["687300_7465600"] == {
        "quadrado": "687300_7465600", "chamados": "6", "atendidos": "3",
        "fechados": "4", "mediana_dias_ate_fechar": "1.5",
    }
    assert do_csv["680000_7464000"]["chamados"] == "5"
    assert do_csv["680000_7464000"]["mediana_dias_ate_fechar"] == "3.0"


# ---- Sem rua e sem coordenada ---------------------------------------------------------


def test_chamado_sem_rua_nao_entra_em_nenhuma_rua(tmp_path):
    resumo, saida = rodar(tmp_path, minimo=1)
    ruas = {linha["rua"] for linha in ler_csv(saida / "ruas.csv")}
    assert ruas == {"Rua A", "Rua B", "Rua C"}
    assert resumo.sem_rua == 2  # uma com rua "0", outra com rua vazia


def test_chamado_sem_rua_mas_com_coordenada_conta_no_quadrado(tmp_path):
    _, saida = rodar(tmp_path, minimo=1)
    do_csv = {linha["quadrado"]: linha for linha in ler_csv(saida / "quadrados.csv")}
    # Q2: 2 chamados da Rua B e 2 sem rua.
    assert do_csv["687400_7465600"]["chamados"] == "4"


def test_chamado_sem_coordenada_nao_entra_em_nenhum_quadrado(tmp_path):
    resumo, _ = rodar(tmp_path, minimo=1)
    # Latitude e longitude vazias (2), as duas 0 (1) e só a longitude 0 (1).
    assert resumo.sem_coordenada == 4


def test_resumo_mostra_sem_rua_e_sem_coordenada(tmp_path):
    _, saida = rodar(tmp_path)
    texto = (saida / "resumo.txt").read_text(encoding="utf-8")
    assert "sem rua: 2" in texto
    assert "sem coordenada: 4" in texto


# ---- Mínimo configurável --------------------------------------------------------------


def test_rua_abaixo_do_minimo_sai_como_menos_de_n_sem_numero(tmp_path):
    _, saida = rodar(tmp_path, minimo=5)
    linha = por_rua(saida)[("Glória", "Rua C")]
    assert linha["chamados"] == "menos de 5"
    assert linha["atendidos"] == linha["fechados"] == linha["mediana_dias_ate_fechar"] == ""


def test_rua_com_exatamente_o_minimo_mostra_o_numero(tmp_path):
    _, saida = rodar(tmp_path, minimo=5)
    assert por_rua(saida)[("Tijuca", "Rua A")]["chamados"] == "5"


def test_quadrado_abaixo_do_minimo_sai_como_menos_de_n_sem_numero(tmp_path):
    _, saida = rodar(tmp_path, minimo=5)
    linha = {q["quadrado"]: q for q in ler_csv(saida / "quadrados.csv")}["687400_7465600"]
    assert linha["chamados"] == "menos de 5"
    assert linha["atendidos"] == linha["fechados"] == linha["mediana_dias_ate_fechar"] == ""
    propriedades = {
        f["properties"]["quadrado"]: f["properties"] for f in ler_geojson(saida)["features"]
    }["687400_7465600"]
    assert propriedades["chamados"] == "menos de 5"
    assert propriedades["atendidos"] is None and propriedades["fechados"] is None


def test_minimo_muda_o_corte(tmp_path):
    _, saida = rodar(tmp_path, minimo=7)
    assert por_rua(saida)[("Centro", "Rua A")]["chamados"] == "menos de 7"


def test_minimo_tem_de_ser_pelo_menos_1(tmp_path):
    with pytest.raises(ValueError, match="mínimo"):
        rodar(tmp_path, minimo=0)


# ---- Nenhuma saída tem coordenada, identificador ou número de porta -------------------


def test_nenhuma_saida_tem_coordenada_identificador_ou_numero_de_porta(tmp_path):
    # A tabela de verdade tem mais colunas; aqui entram um identificador e o número da porta.
    linhas = LISTA_EXEMPLO.splitlines()
    identificadores = [f"CH-{90000 + i}" for i in range(1, len(linhas))]
    portas = [f"{700 + i}A" for i in range(1, len(linhas))]
    texto = linhas[0] + ";id_chamado;numero_logradouro\n" + "".join(
        f"{linha};{identificador};{porta}\n"
        for linha, identificador, porta in zip(linhas[1:], identificadores, portas)
    )
    _, saida = rodar(tmp_path, texto, minimo=1)

    pontos = coordenadas_dos_chamados(LISTA_EXEMPLO)
    textos_proibidos = set(identificadores) | set(portas)
    for linha in csv.DictReader(LISTA_EXEMPLO.splitlines(), delimiter=";"):
        textos_proibidos |= {linha["latitude"], linha["longitude"]} - {"", "0"}

    arquivos = sorted(saida.iterdir())
    assert {a.name for a in arquivos} == {"ruas.csv", "quadrados.csv", "quadrados.geojson", "resumo.txt"}
    for arquivo in arquivos:
        texto_saida = arquivo.read_text(encoding="utf-8")
        for identificador in identificadores:
            assert identificador not in texto_saida, f"{arquivo.name} traz o identificador"
        if arquivo.suffix == ".csv":
            for linha in ler_csv(arquivo):
                assert not set(linha.values()) & textos_proibidos, f"{arquivo.name}: {linha}"
        if arquivo.name == "resumo.txt":
            for proibido in textos_proibidos:
                assert proibido not in texto_saida, f"resumo.txt traz {proibido}"

    assert cabecalho(saida / "ruas.csv") == CABECALHO_RUAS
    assert cabecalho(saida / "quadrados.csv") == CABECALHO_QUADRADOS
    for feature in ler_geojson(saida)["features"]:
        assert set(feature["properties"]) == set(CABECALHO_QUADRADOS)
        assert not {str(v) for v in feature["properties"].values()} & textos_proibidos
        # Os vértices são os cantos da grade, nunca o lugar de um chamado.
        for vertice in feature["geometry"]["coordinates"][0]:
            for lon, lat in pontos:
                assert abs(vertice[0] - lon) > 1e-7 or abs(vertice[1] - lat) > 1e-7, (
                    f"vértice igual a um chamado: {vertice}"
                )


# ---- Coluna faltando ------------------------------------------------------------------


def _sem_coluna(texto, *colunas):
    linhas = list(csv.reader(texto.splitlines(), delimiter=";"))
    manter = [i for i, nome in enumerate(linhas[0]) if nome not in colunas]
    return "".join(";".join(linha[i] for i in manter) + "\n" for linha in linhas)


def test_entrada_sem_uma_coluna_diz_qual_falta(tmp_path):
    with pytest.raises(EntradaInvalida, match="tipo_situacao"):
        rodar(tmp_path, _sem_coluna(LISTA_EXEMPLO, "tipo_situacao"))


def test_entrada_sem_duas_colunas_diz_as_duas(tmp_path):
    with pytest.raises(EntradaInvalida) as erro:
        rodar(tmp_path, _sem_coluna(LISTA_EXEMPLO, "latitude", "data_fim"))
    assert "latitude" in str(erro.value) and "data_fim" in str(erro.value)


def test_linha_de_comando_avisa_a_coluna_que_falta(tmp_path, capsys):
    entrada = tmp_path / "chamados.csv"
    entrada.write_text(_sem_coluna(LISTA_EXEMPLO, "bairro"), encoding="utf-8")
    codigo = main([str(entrada), "--saida", str(tmp_path / "saida"), "--minimo", "5"])
    assert codigo != 0
    assert "bairro" in capsys.readouterr().err


def test_entrada_separada_por_virgula_tambem_funciona(tmp_path):
    texto = EXEMPLO_DA_ISSUE.replace(";", ",")
    _, saida = rodar(tmp_path, texto, minimo=1)
    assert por_rua(saida)[("Centro", "Rua Exemplo")]["chamados"] == "2"


# ---- Período opcional -----------------------------------------------------------------


def test_periodo_deixa_de_fora_o_chamado_fora_das_datas(tmp_path):
    # Só os chamados da Tijuca abertos de 02/05 a 05/05/2025, contando os dois dias.
    resumo, saida = rodar(tmp_path, minimo=1, inicio=date(2025, 5, 2), fim=date(2025, 5, 5))
    ruas = ler_csv(saida / "ruas.csv")
    assert [(r["bairro"], r["rua"], r["chamados"]) for r in ruas] == [("Tijuca", "Rua A", "4")]
    assert resumo.fora_do_periodo == 15
    assert resumo.contados == 4


def test_periodo_pela_linha_de_comando(tmp_path, capsys):
    entrada = tmp_path / "chamados.csv"
    entrada.write_text(LISTA_EXEMPLO, encoding="utf-8")
    saida = tmp_path / "saida"
    codigo = main([
        str(entrada), "--saida", str(saida), "--minimo", "1",
        "--inicio", "2025-05-01", "--fim", "2025-05-31",
    ])
    assert codigo == 0
    assert por_rua(saida).keys() == {("Tijuca", "Rua A")}
    mensagens = capsys.readouterr().out
    assert "sem rua: 0" in mensagens and "sem coordenada: 0" in mensagens


def test_linha_de_comando_sem_periodo_conta_tudo(tmp_path):
    entrada = tmp_path / "chamados.csv"
    entrada.write_text(LISTA_EXEMPLO, encoding="utf-8")
    saida = tmp_path / "saida"
    assert main([str(entrada), "--saida", str(saida), "--minimo", "5"]) == 0
    assert len(por_rua(saida)) == 4


# ---- README ---------------------------------------------------------------------------


def test_readme_cita_a_tabela_certa_do_1746():
    fonte = (RAIZ / "README.md").read_text(encoding="utf-8").split("## Fonte dos dados")[1]
    fonte = fonte.split("\n## ")[0]
    assert "datario.adm_central_atendimento_1746.chamado" in fonte
    assert "datario.administracao_servicos_publicos.chamado_1746" not in fonte
