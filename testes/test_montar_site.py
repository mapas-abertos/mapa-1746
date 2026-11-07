"""Testes do montador do site (issues #16 e #31): o mapa a partir das saídas do agregador.

Cada teste nasce de um item do "Quando está pronta" da issue, antes do código (TDD).
Os dados são os mesmos chamados fictícios do teste do agregador (testes/test_agregador.py):
3 quadrados, 2 lado a lado no Centro e 1 na Tijuca. Os testes dos filtros (issue #31) usam
a saída da coleta, rodada no DuckDB como em testes/test_coleta.py, e o Node para as contas
do filtros.js (o mesmo código que roda no navegador).
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from test_agregador import LISTA_EXEMPLO
from test_coleta import CLASSIFICACAO_FICTICIA, chamados_dos_cinco_grupos_e_sem_classificacao
from test_coleta import montar_base
from test_coleta import rodar as rodar_coleta

from agregador import agregar
from montar_site import (
    ARQUIVOS_DO_SITE,
    CORES_DAS_CLASSES,
    LIMITES_DO_RIO,
    EntradaInvalida,
    main,
    montar_site,
)

FRASE = (
    "A cor mostra onde se pede mais, e isso acompanha onde há mais gente e mais movimento. "
    "Não mostra onde a Prefeitura atende pior."
)

Q1 = "687300_7465600"  # Centro: 6 chamados, 3 atendidos, 4 fechados, mediana 1,5 dia
Q2 = "687400_7465600"  # Centro: 4 chamados
Q3 = "680000_7464000"  # Tijuca: 5 chamados


# ---- Ajudantes ------------------------------------------------------------------------


def agregado(tmp_path, resumo_extra="", lista=LISTA_EXEMPLO):
    """Roda o agregador com a lista fictícia e devolve a pasta com as 4 saídas."""
    entrada = tmp_path / "chamados.csv"
    entrada.write_text(lista, encoding="utf-8")
    pasta = tmp_path / "agregado"
    agregar(entrada, pasta)
    if resumo_extra:
        with open(pasta / "resumo.txt", "a", encoding="utf-8") as arquivo:
            arquivo.write(resumo_extra)
    return pasta


def montar(tmp_path, resumo_extra="", lista=LISTA_EXEMPLO, **opcoes):
    pasta = agregado(tmp_path, resumo_extra, lista)
    site = tmp_path / "site"
    montar_site(pasta, site, **opcoes)
    return pasta, site


def texto(site, nome):
    return (site / nome).read_text(encoding="utf-8")


def sem_marcas(html):
    """O texto que a pessoa lê: sem as marcas HTML e com espaços simples."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def dados_do_mapa(site):
    conteudo = texto(site, "dados.js").strip()
    prefixo = "window.MAPA_DADOS = "
    assert conteudo.startswith(prefixo) and conteudo.endswith(";")
    return json.loads(conteudo[len(prefixo):-1])


def quadrado(site, identificador):
    for feature in dados_do_mapa(site)["quadrados"]["features"]:
        if feature["properties"]["id"] == identificador:
            return feature
    raise AssertionError(f"quadrado {identificador} não está no mapa")


def linhas(feature):
    return dict(feature["properties"]["linhas"])


# ---- Monta o site numa pasta, só com os arquivos agregados -----------------------------


def test_monta_as_paginas_e_as_tabelas_numa_pasta(tmp_path):
    _, site = montar(tmp_path)
    for nome in ("index.html", "metodo.html", "estilo.css", "mapa.js", "dados.js",
                 "ruas.csv", "quadrados.csv"):
        assert (site / nome).is_file(), nome


def test_o_site_so_leva_as_saidas_do_agregador_e_nada_de_dados(tmp_path):
    pasta = agregado(tmp_path)
    # Arquivos soltos na pasta de entrada, que não são saída do agregador, ficam de fora.
    (pasta / "chamados_brutos.csv").write_text(LISTA_EXEMPLO, encoding="utf-8")
    (pasta / "anotacoes.txt").write_text("não é para o site", encoding="utf-8")
    site = tmp_path / "site"
    montar_site(pasta, site)

    assert {arquivo.name for arquivo in site.rglob("*") if arquivo.is_file()} == set(ARQUIVOS_DO_SITE)
    tudo = "".join(texto(site, nome) for nome in ARQUIVOS_DO_SITE)
    # Nada do chamado individual: nem coordenada, nem tipo, nem data.
    for pedaco in ("-22.90668", "-43.173317", "Iluminação Pública", "2025-03-01 08:00", "não é para o site"):
        assert pedaco not in tudo


def test_as_tabelas_para_baixar_sao_as_do_agregador(tmp_path):
    pasta, site = montar(tmp_path)
    for nome in ("ruas.csv", "quadrados.csv"):
        original = (pasta / nome).read_text(encoding="utf-8")
        # Com a marca de UTF-8 no início, para o Excel abrir os acentos certos.
        assert (site / nome).read_bytes().startswith(b"\xef\xbb\xbf")
        assert (site / nome).read_text(encoding="utf-8-sig") == original


def test_montar_de_novo_na_mesma_pasta_atualiza_o_site(tmp_path):
    _, site = montar(tmp_path)
    assert linhas(quadrado(site, Q1))["Chamados"] == "6"
    segunda = tmp_path / "segunda"
    segunda.mkdir()
    so_dois = "\n".join(LISTA_EXEMPLO.splitlines()[:3]) + "\n"
    montar_site(agregado(segunda, lista=so_dois), site)
    assert linhas(quadrado(site, Q1))["Chamados"] == "2"


# ---- Mapa do Rio inteiro, quadrados coloridos e legenda --------------------------------


def test_abre_no_mapa_do_rio_inteiro(tmp_path):
    _, site = montar(tmp_path)
    (sul, oeste), (norte, leste) = dados_do_mapa(site)["limites"]
    assert [[sul, oeste], [norte, leste]] == LIMITES_DO_RIO
    # A caixa cobre o município inteiro (a mesma caixa usada no teste do agregador) e os 3 quadrados.
    assert sul <= -23.05 and norte >= -22.75 and oeste <= -43.75 and leste >= -43.10
    for identificador in (Q1, Q2, Q3):
        for longitude, latitude in quadrado(site, identificador)["geometry"]["coordinates"][0]:
            assert sul <= latitude <= norte and oeste <= longitude <= leste


def test_o_site_tem_um_quadrado_para_cada_quadrado_do_agregador_com_o_mesmo_contorno(tmp_path):
    pasta, site = montar(tmp_path)
    original = json.loads((pasta / "quadrados.geojson").read_text(encoding="utf-8"))
    do_site = dados_do_mapa(site)["quadrados"]
    assert [f["properties"]["id"] for f in do_site["features"]] == [
        f["properties"]["quadrado"] for f in original["features"]
    ]
    assert [f["geometry"] for f in do_site["features"]] == [f["geometry"] for f in original["features"]]


def test_a_cor_e_a_quantidade_de_chamados_e_todo_quadrado_tem_cor_da_escala(tmp_path):
    _, site = montar(tmp_path)
    for identificador in (Q1, Q2, Q3):
        assert quadrado(site, identificador)["properties"]["cor"] in CORES_DAS_CLASSES
    # Q2 tem 4 chamados: a primeira classe, de 1 a 9.
    assert quadrado(site, Q2)["properties"]["cor"] == CORES_DAS_CLASSES[0]


def test_quanto_mais_chamados_mais_escura_a_cor(tmp_path):
    # Os quadrados de 6 e de 5 chamados caem na mesma classe.
    # Ordem das classes: a lista de cores vai da mais clara à mais escura.
    assert len(set(CORES_DAS_CLASSES)) == len(CORES_DAS_CLASSES) >= 4
    _, site = montar(tmp_path)
    cores = [quadrado(site, i)["properties"]["cor"] for i in (Q1, Q2, Q3)]
    assert all(cor in CORES_DAS_CLASSES for cor in cores)


def test_a_legenda_mostra_as_cores_a_partir_de_1_chamado(tmp_path):
    _, site = montar(tmp_path)
    html = texto(site, "index.html")
    legenda = sem_marcas(html)
    for cor in CORES_DAS_CLASSES:
        assert cor in html  # cada cor da legenda aparece como amostra
    assert "1 a 9" in legenda  # sem mínimo, a primeira classe começa em 1
    assert "1.000 ou mais" in legenda
    assert "menos de" not in legenda.lower()
    assert "número não mostrado" not in legenda


def test_a_frase_da_cor_esta_na_legenda_e_na_pagina_de_metodo(tmp_path):
    _, site = montar(tmp_path)
    assert FRASE in sem_marcas(texto(site, "index.html"))
    assert FRASE in sem_marcas(texto(site, "metodo.html"))


# ---- Clique no quadrado ----------------------------------------------------------------


def test_clique_mostra_chamados_atendidos_fechados_ainda_abertos_e_mediana(tmp_path):
    _, site = montar(tmp_path)
    assert quadrado(site, Q1)["properties"]["linhas"] == [
        ["Chamados", "6"],
        ["Atendidos", "3"],
        ["Fechados", "4"],
        ["Ainda abertos", "2"],
        ["Mediana de dias até fechar", "1,5"],
    ]


def test_ainda_abertos_e_chamados_menos_fechados(tmp_path):
    _, site = montar(tmp_path)
    for identificador in (Q1, Q2, Q3):
        valores = linhas(quadrado(site, identificador))
        assert int(valores["Ainda abertos"]) == int(valores["Chamados"]) - int(valores["Fechados"])


def test_quadrado_com_1_chamado_mostra_1_no_arquivo_e_no_clique(tmp_path):
    so_um = "\n".join(LISTA_EXEMPLO.splitlines()[:2]) + "\n"
    _, site = montar(tmp_path, lista=so_um)
    (feature,) = dados_do_mapa(site)["quadrados"]["features"]
    assert feature["properties"]["linhas"] == [
        ["Chamados", "1"],
        ["Atendidos", "1"],
        ["Fechados", "1"],
        ["Ainda abertos", "0"],
        ["Mediana de dias até fechar", "0,5"],
    ]
    assert feature["properties"]["cor"] == CORES_DAS_CLASSES[0]
    assert "menos de" not in texto(site, "dados.js")


def test_quadrado_sem_nenhum_fechado_mostra_traco_na_mediana(tmp_path):
    lista = (
        "data_inicio;data_fim;tipo;subtipo;tipo_situacao;bairro;rua;latitude;longitude\n"
        + "".join(
            f"2025-03-0{i} 08:00;;Limpeza;Remoção de entulho;Não consta;Centro;Rua A;-22.9067;-43.1732\n"
            for i in range(1, 4)
        )
    )
    entrada = tmp_path / "chamados.csv"
    entrada.write_text(lista, encoding="utf-8")
    pasta = tmp_path / "agregado"
    agregar(entrada, pasta)
    site = tmp_path / "site"
    montar_site(pasta, site)
    (feature,) = dados_do_mapa(site)["quadrados"]["features"]
    assert linhas(feature)["Fechados"] == "0"
    assert linhas(feature)["Ainda abertos"] == "3"
    assert linhas(feature)["Mediana de dias até fechar"] == "—"


def test_nunca_aparece_null_none_ou_nan_no_site(tmp_path):
    _, site = montar(tmp_path)
    for nome in ("dados.js", "index.html", "metodo.html"):
        conteudo = texto(site, nome)
        for palavra in ("null", "None", "NaN", "undefined"):
            assert palavra not in conteudo, f"{palavra} em {nome}"


def test_numeros_grandes_saem_com_ponto_de_milhar(tmp_path):
    linhas_chamados = "".join(
        f"2025-03-01 {hora:02d}:{minuto:02d};;Limpeza;Remoção de entulho;Não consta;Centro;Rua A;-22.9067;-43.1732\n"
        for hora in range(24) for minuto in range(0, 60, 2)
    )  # 720 chamados no mesmo quadrado
    cabecalho = "data_inicio;data_fim;tipo;subtipo;tipo_situacao;bairro;rua;latitude;longitude\n"
    entrada = tmp_path / "chamados.csv"
    entrada.write_text(cabecalho + linhas_chamados * 2, encoding="utf-8")  # 1.440
    pasta = tmp_path / "agregado"
    agregar(entrada, pasta)
    site = tmp_path / "site"
    montar_site(pasta, site)
    (feature,) = dados_do_mapa(site)["quadrados"]["features"]
    assert linhas(feature)["Chamados"] == "1.440"
    assert feature["properties"]["cor"] == CORES_DAS_CLASSES[-1]


# ---- Botões para baixar ----------------------------------------------------------------


def test_os_dois_botoes_de_baixar_vem_antes_do_mapa(tmp_path):
    _, site = montar(tmp_path)
    html = texto(site, "index.html")
    ruas = html.index('href="ruas.csv"')
    quadrados = html.index('href="quadrados.csv"')
    mapa = html.index('id="mapa"')
    assert ruas < mapa and quadrados < mapa  # visíveis sem rolar a página
    assert re.search(r'<a[^>]*href="ruas\.csv"[^>]*download', html)
    assert re.search(r'<a[^>]*href="quadrados\.csv"[^>]*download', html)
    texto_visivel = sem_marcas(html)
    assert "Baixar a tabela por rua" in texto_visivel
    assert "Baixar a tabela por quadrado" in texto_visivel


# ---- Página de método e fonte ----------------------------------------------------------


def test_metodo_traz_fonte_grade_licencas_e_limites_e_nao_fala_mais_do_minimo(tmp_path):
    _, site = montar(tmp_path)
    html = texto(site, "metodo.html")
    pagina = sem_marcas(html)
    assert "datario.adm_central_atendimento_1746.chamado" in pagina
    assert re.search(r'href="https://[^"]*data\.rio[^"]*"', html)
    assert "100 m" in pagina
    assert "mínimo" not in pagina.lower() and "menos de" not in pagina.lower()
    assert "licença MIT" in pagina
    assert re.search(r"dados[^.]*a definir", pagina, re.IGNORECASE)
    assert "falta de água e de luz em casa não passa pelo 1746" in pagina.lower()
    assert "ausência de chamado não é ausência de problema" in pagina.lower()
    assert 'href="index.html"' in html  # volta para o mapa


def test_metodo_mostra_as_datas_do_resumo_em_dia_mes_ano(tmp_path):
    extra = "chamado mais recente: 2026-10-30\ndata da coleta: 2026-11-05\n"
    _, site = montar(tmp_path, resumo_extra=extra)
    pagina = sem_marcas(texto(site, "metodo.html"))
    assert "30/10/2026" in pagina
    assert "05/11/2026" in pagina


RESUMO_DA_COLETA = """Resumo da coleta (chamados do 1746)
fonte: datario.adm_central_atendimento_1746.chamado (BigQuery, só leitura)
período: todos
chamados lidos: 19
sem rua: 2
  dos quais com rua fora do cadastro de logradouros: 0
sem coordenada: 4
chamado mais recente na base: 2026-10-30
data da coleta: 2026-11-05
ruas: 5
ruas com desenho: 0
quadrados: 3
GB lidos no BigQuery (simulação): 0,1
"""


def test_metodo_le_as_datas_do_resumo_no_formato_da_coleta(tmp_path):
    pasta = agregado(tmp_path)
    (pasta / "resumo.txt").write_text(RESUMO_DA_COLETA, encoding="utf-8")
    site = tmp_path / "site"
    montar_site(pasta, site)
    pagina = sem_marcas(texto(site, "metodo.html"))
    assert "Chamado mais recente na base: 30/10/2026" in pagina
    assert "Data da coleta: 05/11/2026" in pagina


RESUMO_DA_COLETA_REAL = """Resumo da coleta (chamados do 1746)
fonte: datario.adm_central_atendimento_1746.chamado (BigQuery, só leitura)
período: todos
chamados lidos: 20425527
sem rua: 6513009
  dos quais com rua fora do cadastro de logradouros: 1000
sem coordenada: 10902581
coordenada fora do município: 1234
chamado mais recente na base: 2026-10-30
data da coleta: 2026-11-05
ruas: 30000
quadrados: 100000
"""


def montar_com_resumo(tmp_path, resumo):
    pasta = agregado(tmp_path)
    (pasta / "resumo.txt").write_text(resumo, encoding="utf-8")
    site = tmp_path / "site"
    montar_site(pasta, site)
    return sem_marcas(texto(site, "metodo.html"))


def test_metodo_diz_quantos_chamados_nao_aparecem_no_mapa_e_a_porcentagem(tmp_path):
    pagina = montar_com_resumo(tmp_path, RESUMO_DA_COLETA_REAL)
    # 10.902.581 de 20.425.527 = 53,4%; 6.513.009 de 20.425.527 = 31,9%.
    assert "10.902.581 chamados (53,4%) não têm coordenada e não aparecem no mapa" in pagina
    assert "6.513.009 chamados (31,9%) não têm rua e não entram na tabela por rua" in pagina
    assert "20.425.527 chamados" in pagina  # o total lido, para a pessoa ter a base da conta


def test_metodo_diz_quantos_chamados_com_coordenada_fora_do_municipio_foram_descartados(tmp_path):
    pagina = montar_com_resumo(tmp_path, RESUMO_DA_COLETA_REAL)
    assert "1.234 chamados com coordenada fora do município do Rio foram descartados do mapa" in pagina


def test_metodo_le_a_linha_de_fora_do_municipio_no_formato_real_da_coleta(tmp_path):
    # Issue #24: a coleta grava a linha recuada, debaixo de "sem coordenada".
    resumo = RESUMO_DA_COLETA_REAL.replace(
        "coordenada fora do município: 1234\n",
        "  dos quais com coordenada fora do município: 8291\n",
    )
    pagina = montar_com_resumo(tmp_path, resumo)
    assert "8.291 chamados com coordenada fora do município do Rio foram descartados do mapa" in pagina


def test_metodo_funciona_sem_a_linha_de_coordenada_fora_do_municipio(tmp_path):
    resumo = RESUMO_DA_COLETA_REAL.replace("coordenada fora do município: 1234\n", "")
    pagina = montar_com_resumo(tmp_path, resumo)
    assert "fora do município" not in pagina
    assert "não têm coordenada e não aparecem no mapa" in pagina


def test_metodo_sem_total_lido_mostra_so_a_contagem_sem_porcentagem(tmp_path):
    resumo = "sem coordenada: 4\nsem rua: 2\n"
    pagina = montar_com_resumo(tmp_path, resumo)
    assert "4 chamados não têm coordenada e não aparecem no mapa" in pagina
    assert "%" not in pagina


def test_metodo_sem_chamados_sem_coordenada_nao_fala_em_porcentagem_quebrada(tmp_path):
    resumo = "chamados lidos: 0\nsem coordenada: 0\nsem rua: 0\n"
    pagina = montar_com_resumo(tmp_path, resumo)
    assert "0 chamados não têm coordenada" in pagina
    assert "nan" not in pagina.lower() and "inf" not in pagina.lower()


def test_metodo_diz_a_definir_quando_a_coleta_nao_achou_chamado(tmp_path):
    pasta = agregado(tmp_path)
    resumo = RESUMO_DA_COLETA.replace("na base: 2026-10-30", "na base: nenhum")
    (pasta / "resumo.txt").write_text(resumo, encoding="utf-8")
    site = tmp_path / "site"
    montar_site(pasta, site)
    assert "Chamado mais recente na base: a definir" in sem_marcas(texto(site, "metodo.html"))


def test_metodo_diz_a_definir_quando_o_resumo_nao_traz_as_datas(tmp_path):
    _, site = montar(tmp_path)  # o resumo do agregador não tem as duas datas
    pagina = sem_marcas(texto(site, "metodo.html"))
    assert re.search(r"chamado mais recente[^.]*a definir", pagina, re.IGNORECASE)
    assert re.search(r"coleta[^.]*a definir", pagina, re.IGNORECASE)


# ---- Só problema público, por privacidade (issue #26) ---------------------------------

# Números inventados, no formato do resumo da coleta depois da issue #26.
RESUMO_SO_PROBLEMA_PUBLICO = """Resumo da coleta (chamados do 1746)
fonte: datario.adm_central_atendimento_1746.chamado (BigQuery, só leitura)
período: todos
chamados lidos: 9500000
chamados de problema público (entram no mapa): 3590000
fora do mapa, por grupo:
  denuncia: 2000000
  pessoal: 1500000
  sem_lugar: 1200000
  a_revisar: 1000000
  sem classificação: 210000
pares tipo/subtipo sem classificação: 2
  - Tipo Novo / Subtipo novo: 200000
  - Outro Tipo / Outro subtipo: 10000
entre os chamados de problema público:
sem rua: 718000
  dos quais com rua fora do cadastro de logradouros: 10
sem coordenada: 359000
  dos quais com coordenada fora do município: 1000
chamado mais recente na base: 2026-11-05
data da coleta: 2026-11-06
ruas: 30000
quadrados: 100000
"""

LINK_DA_LISTA = (
    "https://github.com/mapas-abertos/mapa-1746/blob/main/"
    "_referencias/20261106_classificacao_subtipos/grupos_subtipos_1746.csv"
)


def test_metodo_diz_que_o_mapa_mostra_so_problema_publico(tmp_path):
    pagina = montar_com_resumo(tmp_path, RESUMO_SO_PROBLEMA_PUBLICO)
    assert "só os chamados de problema público" in pagina
    assert "iluminação, buraco, limpeza, árvore, drenagem, semáforo e ônibus" in pagina
    assert "todos os chamados da base" not in pagina


def test_metodo_diz_por_que_privacidade(tmp_path):
    pagina = montar_com_resumo(tmp_path, RESUMO_SO_PROBLEMA_PUBLICO)
    assert "privacidade" in pagina.lower()
    assert "LGPD" in pagina
    assert "não pode apontar uma pessoa, uma casa ou um estabelecimento" in pagina


def test_metodo_diz_quantos_entram_no_mapa_e_quantos_ficaram_fora_em_cada_grupo(tmp_path):
    pagina = montar_com_resumo(tmp_path, RESUMO_SO_PROBLEMA_PUBLICO)
    # 3.590.000 de 9.500.000 = 37,8%.
    assert "Dos 9.500.000 chamados lidos, 3.590.000 (37,8%) são de problema público" in pagina
    for trecho in (
        "Denúncia, que pode apontar vizinho, carro, obra, estabelecimento ou imóvel: "
        "2.000.000 chamados (21,1%)",
        "Pedido pessoal, da própria casa ou da pessoa: 1.500.000 chamados (15,8%)",
        "Sem lugar (informação, tributo ou documento): 1.200.000 chamados (12,6%)",
        "A revisar (subtipos que ainda vão ser classificados): 1.000.000 chamados (10,5%)",
        "Subtipo que não está na lista de classificação: 210.000 chamados (2,2%)",
    ):
        assert trecho in pagina, trecho


def test_metodo_aponta_para_a_lista_de_classificacao(tmp_path):
    pasta = agregado(tmp_path)
    (pasta / "resumo.txt").write_text(RESUMO_SO_PROBLEMA_PUBLICO, encoding="utf-8")
    site = tmp_path / "site"
    montar_site(pasta, site)
    assert f'href="{LINK_DA_LISTA}"' in texto(site, "metodo.html")


def test_metodo_conta_sem_coordenada_e_sem_rua_sobre_os_chamados_de_problema_publico(tmp_path):
    pagina = montar_com_resumo(tmp_path, RESUMO_SO_PROBLEMA_PUBLICO)
    # 359.000 de 3.590.000 = 10,0%; 718.000 de 3.590.000 = 20,0%.
    assert ("Dos 3.590.000 chamados de problema público, 359.000 chamados (10,0%) não têm "
            "coordenada e não aparecem no mapa") in pagina
    assert "718.000 chamados (20,0%) não têm rua" in pagina


def test_metodo_com_um_chamado_so_num_grupo_fala_no_singular(tmp_path):
    resumo = RESUMO_SO_PROBLEMA_PUBLICO.replace("  a_revisar: 1000000", "  a_revisar: 1")
    pagina = montar_com_resumo(tmp_path, resumo)
    assert "A revisar (subtipos que ainda vão ser classificados): 1 chamado (" in pagina


def test_metodo_sem_os_grupos_no_resumo_nao_fala_em_problema_publico(tmp_path):
    # O resumo do agregador (e o da coleta antes da issue #26) não traz os grupos.
    pagina = montar_com_resumo(tmp_path, RESUMO_DA_COLETA_REAL)
    assert "LGPD" not in pagina
    assert "problema público" not in pagina


def test_texto_do_problema_publico_nao_compara_nem_classifica_lugares(tmp_path):
    pagina = montar_com_resumo(tmp_path, RESUMO_SO_PROBLEMA_PUBLICO).replace(FRASE, "").lower()
    for palavra in PALAVRAS_QUE_COMPARAM:
        assert palavra not in pagina, palavra


# ---- Celular, biblioteca de mapa e crédito ---------------------------------------------


def test_as_paginas_se_ajustam_a_tela_do_celular(tmp_path):
    _, site = montar(tmp_path)
    for nome in ("index.html", "metodo.html"):
        assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in texto(site, nome)
    css = texto(site, "estilo.css")
    assert "box-sizing: border-box" in css
    assert "overflow-x: hidden" in css or "max-width: 100%" in css


def test_biblioteca_do_mapa_vem_de_cdn_com_versao_fixa(tmp_path):
    _, site = montar(tmp_path)
    html = texto(site, "index.html")
    fontes = re.findall(r'(?:src|href)="(https://[^"]+)"', html)
    de_biblioteca = [f for f in fontes if "leaflet" in f]
    assert len(de_biblioteca) == 2  # o script e o estilo
    for endereco in de_biblioteca:
        assert re.search(r"leaflet@\d+\.\d+\.\d+/", endereco), endereco
    assert html.count("integrity=") >= 2  # confere que o arquivo da CDN é o esperado


def test_credito_do_openstreetmap_aparece_no_mapa_e_no_metodo(tmp_path):
    _, site = montar(tmp_path)
    js = texto(site, "mapa.js")
    assert "https://www.openstreetmap.org/copyright" in js
    assert "OpenStreetMap" in js
    assert "OpenStreetMap" in sem_marcas(texto(site, "metodo.html"))


# ---- Nenhum texto compara nem classifica lugares ---------------------------------------


PALAVRAS_QUE_COMPARAM = (
    "pior", "melhor", "ranking", "ranque", "perigos", "problemático", "problematico",
    "mais violento", "abandonad", "esquecid", "negligen", "descaso", "ruim", "péssim",
    "critic", "crític", "campeão", "líder",
)


def test_nenhum_texto_compara_ou_classifica_lugares(tmp_path):
    _, site = montar(tmp_path)
    paginas = [sem_marcas(texto(site, "index.html")), sem_marcas(texto(site, "metodo.html")),
               texto(site, "mapa.js")]
    for pagina in paginas:
        sem_a_frase = pagina.replace(FRASE, "").lower()
        for palavra in PALAVRAS_QUE_COMPARAM:
            assert palavra not in sem_a_frase, palavra


# ---- Erros: dizem o que fazer ----------------------------------------------------------


def test_pasta_sem_as_saidas_do_agregador_avisa_quais_faltam(tmp_path):
    pasta = tmp_path / "vazia"
    pasta.mkdir()
    with pytest.raises(EntradaInvalida) as erro:
        montar_site(pasta, tmp_path / "site")
    mensagem = str(erro.value)
    for nome in ("quadrados.geojson", "quadrados.csv", "ruas.csv", "resumo.txt"):
        assert nome in mensagem
    assert "O que fazer" in mensagem
    assert not (tmp_path / "site").exists()  # não deixa um site pela metade


def test_falta_so_um_arquivo_e_a_mensagem_diz_qual(tmp_path):
    pasta = agregado(tmp_path)
    (pasta / "ruas.csv").unlink()
    with pytest.raises(EntradaInvalida) as erro:
        montar_site(pasta, tmp_path / "site")
    assert "ruas.csv" in str(erro.value)
    assert "quadrados.csv" not in str(erro.value)


def test_resumo_sem_o_minimo_monta_o_site(tmp_path):
    pasta = agregado(tmp_path)
    (pasta / "resumo.txt").write_text("chamados lidos: 19\n", encoding="utf-8")
    montar_site(pasta, tmp_path / "site")
    assert (tmp_path / "site" / "index.html").is_file()


def test_dados_antigos_com_menos_de_n_avisam_para_rodar_a_coleta_de_novo(tmp_path):
    # Um coleta.zip de antes da issue #31 ainda traz "menos de 5" no lugar do número.
    pasta = agregado(tmp_path)
    geojson = json.loads((pasta / "quadrados.geojson").read_text(encoding="utf-8"))
    geojson["features"][0]["properties"].update(
        chamados="menos de 5", atendidos=None, fechados=None, mediana_dias_ate_fechar=None)
    (pasta / "quadrados.geojson").write_text(json.dumps(geojson), encoding="utf-8")
    with pytest.raises(EntradaInvalida) as erro:
        montar_site(pasta, tmp_path / "site")
    assert "menos de" in str(erro.value)
    assert "rode a coleta de novo" in str(erro.value)
    assert not (tmp_path / "site").exists()


def test_geojson_quebrado_avisa_o_que_fazer(tmp_path):
    pasta = agregado(tmp_path)
    (pasta / "quadrados.geojson").write_text("{isto não é json", encoding="utf-8")
    with pytest.raises(EntradaInvalida) as erro:
        montar_site(pasta, tmp_path / "site")
    assert "quadrados.geojson" in str(erro.value)
    assert "O que fazer" in str(erro.value)


# ---- Linha de comando ------------------------------------------------------------------


def test_linha_de_comando_monta_o_site(tmp_path, capsys):
    pasta = agregado(tmp_path)
    site = tmp_path / "site"
    assert main([str(pasta), "--saida", str(site)]) == 0
    assert (site / "index.html").is_file()
    assert "Site gravado em" in capsys.readouterr().out


def test_linha_de_comando_sem_saida_diz_o_que_fazer_em_portugues(tmp_path, capsys):
    assert main([str(tmp_path)]) == 2
    erro = capsys.readouterr().err
    assert erro.startswith("ERRO: Falta a --saida")
    assert "O que fazer" in erro


def test_linha_de_comando_com_pasta_que_nao_existe_diz_o_que_fazer(tmp_path, capsys):
    assert main([str(tmp_path / "nao_existe"), "--saida", str(tmp_path / "site")]) == 1
    erro = capsys.readouterr().err
    assert "ERRO: não achei a pasta" in erro
    assert "O que fazer" in erro


def test_ajuda_em_portugues(capsys):
    with pytest.raises(SystemExit):
        main(["--ajuda"])
    assert "uso:" in capsys.readouterr().out


def test_o_codigo_do_site_nao_depende_de_arquivo_fora_da_pasta(tmp_path):
    # Os totais sem filtro vêm por <script src="dados.js">. A única busca pela rede é a das
    # fatias dos filtros (issue #31), na pasta filtros/ do próprio site.
    _, site = montar(tmp_path)
    for nome in ("mapa.js", "filtros.js"):
        codigo = texto(site, nome)
        todas = len(re.findall(r"fetch\(", codigo))
        assert todas == len(re.findall(r'fetch\("filtros/" \+', codigo)), nome
    assert '<script src="dados.js">' in texto(site, "index.html")
    assert Path(site / "dados.js").stat().st_size > 0


# ---- Número da versão na tela (issue #31) ---------------------------------------------


def test_o_mapa_e_o_metodo_mostram_a_versao_publicada(tmp_path):
    _, site = montar(tmp_path, versao="v2026.11.06")
    for nome in ("index.html", "metodo.html"):
        html = texto(site, nome)
        assert re.search(r'<p class="versao"[^>]*>Versão v2026\.11\.06</p>', html), nome
    css = texto(site, "estilo.css")
    regra = re.search(r"\.versao \{([^}]*)\}", css).group(1)
    assert "position: fixed" in regra  # num canto fixo da tela


def test_sem_versao_aparece_versao_local_e_o_montador_nao_para(tmp_path):
    _, site = montar(tmp_path)
    for nome in ("index.html", "metodo.html"):
        assert "Versão: local (não publicada)" in sem_marcas(texto(site, nome)), nome


def test_versao_na_linha_de_comando(tmp_path):
    pasta = agregado(tmp_path)
    site = tmp_path / "site"
    assert main([str(pasta), "--saida", str(site), "--versao", "v2026.11.06"]) == 0
    assert "Versão v2026.11.06" in texto(site, "index.html")


def test_versao_com_marca_html_nao_vira_html(tmp_path):
    _, site = montar(tmp_path, versao="<b>v1</b>")
    assert "<b>v1</b>" not in texto(site, "index.html")
    assert "&lt;b&gt;v1&lt;/b&gt;" in texto(site, "index.html")


def test_a_entrega_automatica_passa_a_versao_ao_montador():
    raiz = Path(__file__).resolve().parents[1]
    deploy = (raiz / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    passo = deploy.split("- name: Montar o site", 1)[1].split("- uses:", 1)[0]
    assert "VERSAO: ${{ inputs.versao }}" in passo
    assert '--versao "$VERSAO"' in passo


# ---- Filtros no mapa (issue #31) ------------------------------------------------------

NODE = shutil.which("node")

# Chamados fictícios para os filtros: Limpeza e Iluminação no Centro (Q2 e Q1), em volta de
# 03/01/2024 a 05/01/2024, com órgãos trocados para testar dois filtros juntos.
CABECALHO_DOS_FILTROS = (
    "data_inicio;data_fim;tipo;subtipo;tipo_situacao;bairro;rua;latitude;longitude;orgao\n"
)
NO_Q1 = "Centro;Rua A;-22.90668;-43.173317"
NO_Q2 = "Centro;Rua B;-22.906606;-43.17246"
NO_Q3 = "Tijuca;Rua A;-22.921911;-43.244299"
LIMPEZA = "Limpeza;Remoção de entulho"
LUZ = "Iluminação Pública;Reparo de lâmpada apagada"
LISTA_DOS_FILTROS = CABECALHO_DOS_FILTROS + "".join(f"{linha}\n" for linha in (
    f"2023-12-31 10:00;2024-01-02 10:00;{LIMPEZA};Atendido;{NO_Q2};Órgão da Limpeza",
    f"2024-01-02 10:00;;{LIMPEZA};Não consta;{NO_Q2};Órgão da Limpeza",
    f"2024-01-03 00:00;2024-01-04 10:00;{LIMPEZA};Atendido;{NO_Q2};Órgão da Limpeza",
    f"2024-01-04 12:00;2024-01-10 10:00;{LIMPEZA};Não atendido;{NO_Q2};Órgão das Ruas",
    f"2024-01-05 23:59;;{LIMPEZA};Não consta;{NO_Q2};Órgão da Limpeza",
    f"2024-01-06 00:00;;{LIMPEZA};Não consta;{NO_Q2};Órgão da Limpeza",
    f"2024-01-04 08:00;2024-01-04 18:00;{LUZ};Atendido;{NO_Q1};Órgão da Luz",
    f"2024-02-01 08:00;;{LUZ};Não consta;{NO_Q1};Órgão da Limpeza",
    f"2025-05-01 09:00;2025-05-11 09:00;Conservação;Tapa-buraco;Atendido;{NO_Q3};Órgão das Ruas",
))

# Antes do JS de cada teste: carrega o filtros.js e o dados.js do site, como no navegador.
PRELUDIO_JS = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const site = process.argv[1];
const F = require(path.join(site, "filtros.js"));
const contexto = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(site, "dados.js"), "utf8"), contexto);
const dados = contexto.window.MAPA_DADOS;
const info = dados.filtros;
function carregar(nome) {
  return JSON.parse(fs.readFileSync(path.join(site, "filtros", nome), "utf8"));
}
function posicoes(lista, nomes) {
  return nomes.map(function (nome) {
    const i = lista.indexOf(nome);
    if (i < 0) throw new Error("não achei " + nome);
    return i;
  });
}
function calcular(de, ate, filtro) {
  const partes = F.fatiasDoPeriodo(de, ate, info);
  const fatias = partes.map(function (p) { return { dados: carregar(p.nome), dias: p.dias }; });
  const soma = F.somar(fatias, filtro || {}, info, dados.quadrados.features.length);
  const totais = {};
  dados.quadrados.features.forEach(function (feature, i) {
    if (soma.n[i] > 0) totais[feature.properties.id] = [soma.n[i], soma.a[i], soma.f[i]];
  });
  return totais;
}
"""


def rodar_js(site, codigo):
    """Roda `codigo` (o corpo de uma função que devolve algo) no Node e devolve o resultado."""
    assert NODE, "Os testes dos filtros precisam do Node (node) instalado."
    script = PRELUDIO_JS + "\nconsole.log(JSON.stringify((function () {\n" + codigo + "\n})()));\n"
    resultado = subprocess.run([NODE, "-e", script, str(site)], capture_output=True,
                               encoding="utf-8", check=False)
    assert resultado.returncode == 0, resultado.stderr
    return json.loads(resultado.stdout)


def coletado(tmp_path, lista=LISTA_DOS_FILTROS, **opcoes):
    """Roda a coleta (no DuckDB, como nos testes dela) e monta o site com a saída."""
    _, saida, _, _ = rodar_coleta(tmp_path, lista, **opcoes)
    site = tmp_path / "site"
    montar_site(saida, site)
    return saida, site


def ler_csv(caminho):
    linhas = caminho.read_text(encoding="utf-8-sig").splitlines()
    cabecalho = linhas[0].split(";")
    return [dict(zip(cabecalho, linha.split(";"))) for linha in linhas[1:]]


def test_site_da_coleta_leva_as_fatias_e_o_do_agregador_nao_tem_filtros(tmp_path):
    _, site = coletado(tmp_path)
    nomes = {str(a.relative_to(site)).replace("\\", "/") for a in site.rglob("*") if a.is_file()}
    fatias = {"filtros/tudo.json", "filtros/2023.json", "filtros/2024.json", "filtros/2025.json",
              "filtros/2023-12.json", "filtros/2024-01.json", "filtros/2024-02.json",
              "filtros/2025-05.json"}
    assert nomes == set(ARQUIVOS_DO_SITE) | fatias
    assert 'id="form-filtros"' in texto(site, "index.html")

    (tmp_path / "agregador").mkdir()
    _, so_agregador = montar(tmp_path / "agregador")
    assert 'id="form-filtros"' not in texto(so_agregador, "index.html")
    assert "filtros" not in dados_do_mapa(so_agregador)
    assert not (so_agregador / "filtros").exists()


def test_sem_filtro_os_totais_sao_os_de_hoje(tmp_path):
    saida, site = coletado(tmp_path, LISTA_EXEMPLO)
    esperado = {q["quadrado"]: [int(q["chamados"]), int(q["atendidos"]), int(q["fechados"])]
                for q in ler_csv(saida / "quadrados.csv")}
    assert rodar_js(site, 'return F.fatiasDoPeriodo("", "", info);') == [
        {"nome": "tudo.json", "dias": None}]
    assert rodar_js(site, 'return calcular("", "", {});') == esperado
    # E o clique sem filtro é o de antes, com a mediana exata.
    assert linhas(quadrado(site, Q1))["Mediana de dias até fechar"] == "1,5"


def test_com_tema_o_quadrado_soma_so_os_chamados_do_tema(tmp_path):
    _, site = coletado(tmp_path)
    resultado = rodar_js(site, 'return calcular("", "", {temas: posicoes(info.temas, ["Limpeza"])});')
    # Q2: os 6 chamados da Limpeza, 2 atendidos e 3 fechados. Q1 e Q3 não têm Limpeza.
    assert resultado == {Q2: [6, 2, 3]}


def test_periodo_por_dia_inclui_as_duas_pontas_fechados_ou_nao(tmp_path):
    _, site = coletado(tmp_path)
    resultado = rodar_js(site, 'return calcular("2024-01-03", "2024-01-05", {});')
    # Abertos em 03, 04 e 05/01/2024: em Q2, um fechado e atendido, um fechado sem atender e
    # um aberto (às 23:59 do dia 5); em Q1, um fechado e atendido. Ficam de fora os de 31/12,
    # 02/01 e 06/01.
    assert resultado == {Q2: [3, 1, 2], Q1: [1, 1, 1]}


def test_periodo_usa_a_fatia_do_ano_inteiro_e_a_dos_meses_das_pontas(tmp_path):
    _, site = coletado(tmp_path)
    partes = rodar_js(site, 'return F.fatiasDoPeriodo("2024-01-03", "2025-05-01", info);')
    assert partes == [
        {"nome": "2024-01.json", "dias": [3, 31]},
        {"nome": "2024-02.json", "dias": None},
        {"nome": "2025.json", "dias": None},
    ]


def test_data_final_antes_da_inicial_da_a_mensagem_e_nao_soma(tmp_path):
    _, site = coletado(tmp_path)
    assert rodar_js(site, 'return F.validarPeriodo("2024-01-05", "2024-01-03", info);') == (
        "A data final é antes da data inicial")
    assert rodar_js(site, 'return F.validarPeriodo("2024-01-03", "2024-01-05", info);') is None
    # O mapa.js só soma depois de validar: com a mensagem, ele para antes de mudar o mapa.
    mapa = texto(site, "mapa.js")
    aplicar = mapa.split("function aplicar()", 1)[1]
    assert aplicar.index("validarPeriodo") < aplicar.index("somar")
    assert re.search(r"if \(erro\) \{[^}]*return;", aplicar)


def test_o_calendario_so_deixa_escolher_dias_com_chamados(tmp_path):
    _, site = coletado(tmp_path)
    html = texto(site, "index.html")
    for campo in ("filtro-de", "filtro-ate"):
        entrada = re.search(rf'<input[^>]*id="{campo}"[^>]*>', html).group(0)
        assert 'type="date"' in entrada
        assert 'min="2023-12-31"' in entrada and 'max="2025-05-01"' in entrada
    # Data digitada fora do intervalo também não passa.
    mensagem = rodar_js(site, 'return F.validarPeriodo("2020-01-01", "", info);')
    assert mensagem == "Escolha datas entre 31/12/2023 e 01/05/2025"


def test_dois_filtros_juntos_somam_so_o_que_atende_aos_dois(tmp_path):
    _, site = coletado(tmp_path)
    resultado = rodar_js(site, """return calcular("", "", {
        temas: posicoes(info.temas, ["Limpeza"]),
        orgaos: posicoes(info.orgaos, ["Órgão da Limpeza"])});""")
    # Q2: 5 da Limpeza com o Órgão da Limpeza (um é do Órgão das Ruas). Q1 tem um chamado do
    # Órgão da Limpeza, mas é de Iluminação: fica de fora.
    assert resultado == {Q2: [5, 2, 2]}


def test_status_situacao_tipo_de_situacao_e_prazo_filtram(tmp_path):
    _, site = coletado(tmp_path)
    resultado = rodar_js(site, """return [
        calcular("", "", {tipos_de_situacao: ["Atendido"]}),
        calcular("", "", {situacoes: ["Não Encerrado"]}),
        calcular("", "", {status: ["Fechado"], prazos: posicoes(info.prazos, ["No prazo"])}),
        calcular("", "", {prazos: []})];""")
    assert resultado == [
        {Q1: [1, 1, 1], Q2: [2, 2, 2], Q3: [1, 1, 1]},
        {Q1: [1, 0, 0], Q2: [3, 0, 0]},
        {Q1: [1, 1, 1], Q2: [3, 2, 3], Q3: [1, 1, 1]},
        {},
    ]


def test_quadrado_que_fica_com_0_some_do_mapa(tmp_path):
    _, site = coletado(tmp_path)
    resultado = rodar_js(site, 'return calcular("2024-01-06", "2024-01-06", {});')
    assert resultado == {Q2: [1, 0, 0]}  # Q1 e Q3 ficam com 0
    # O mapa.js tira do mapa a camada do quadrado com 0 e põe de volta quando ele tem chamados.
    mapa = texto(site, "mapa.js")
    assert "removeLayer(camada)" in mapa and "addLayer(camada)" in mapa


def test_clique_com_filtro_mostra_os_numeros_e_a_mediana_so_sem_filtro(tmp_path):
    _, site = coletado(tmp_path)
    assert rodar_js(site, "return [F.linhasDoClique(1440, 3, 4), F.NOTA_DA_MEDIANA];") == [
        [["Chamados", "1.440"], ["Atendidos", "3"], ["Fechados", "4"],
         ["Ainda abertos", "1.436"], ["Mediana de dias até fechar", "—"]],
        "A mediana só aparece sem filtro.",
    ]
    cores = rodar_js(site, "return [1, 9, 10, 1000, 5000].map(function (n) { return F.cor(n, info.classes); });")
    assert cores == [CORES_DAS_CLASSES[0], CORES_DAS_CLASSES[0], CORES_DAS_CLASSES[1],
                     CORES_DAS_CLASSES[-1], CORES_DAS_CLASSES[-1]]


def test_a_lista_de_tema_nao_mostra_tipo_de_fora_do_grupo_publico(tmp_path):
    _, saida, _, _ = rodar_coleta(tmp_path, chamados_dos_cinco_grupos_e_sem_classificacao(),
                                  classificacao=CLASSIFICACAO_FICTICIA)
    site = tmp_path / "site"
    montar_site(saida, site)
    html = texto(site, "index.html")
    tema = html.split('<legend>Tema</legend>', 1)[1].split("</fieldset>", 1)[0]
    assert re.findall(r'name="tema" value="(\d+)"', tema) == ["0"]
    assert "Iluminação Pública" in tema
    tudo = "".join(a.read_text(encoding="utf-8") for a in site.rglob("*") if a.is_file()
                   and a.suffix in (".html", ".js", ".json"))
    for tipo in ("Estacionamento Irregular", "Remoção Gratuita", "Tipo Em Revisão",
                 "Tipo Sem Lista"):
        assert tipo not in tudo, tipo


def test_na_busca_de_orgao_parte_do_nome_encolhe_a_lista(tmp_path):
    _, site = coletado(tmp_path)
    resultado = rodar_js(site, """return [
        F.filtrarLista("", info.orgaos).length,
        F.filtrarLista("orgao da", info.orgaos).length,
        F.filtrarLista("LIMP", info.orgaos).map(function (i) { return info.orgaos[i]; })];""")
    assert resultado == [3, 3, ["Órgão da Limpeza"]]
    html = texto(site, "index.html")
    assert re.search(r'<input[^>]*type="search"[^>]*id="busca-orgao"', html)
    assert len(re.findall(r'name="orgao"', html)) == 3


def test_na_busca_de_bairro_tijuca_leva_ao_bairro_e_o_que_nao_existe_avisa(tmp_path):
    _, site = coletado(tmp_path)
    resultado = rodar_js(site, """return [F.acharBairro("Tijuca", info.bairros),
        F.acharBairro("  tijuca ", info.bairros), F.acharBairro("Bairro Inventado", info.bairros),
        F.BAIRRO_NAO_ENCONTRADO];""")
    # A caixa fictícia da Tijuca nos testes da coleta, em [sul, oeste, norte, leste].
    assert resultado == [[-22.94, -43.26, -22.91, -43.22], [-22.94, -43.26, -22.91, -43.22],
                         None, "Bairro não encontrado"]
    mapa = texto(site, "mapa.js")
    assert "fitBounds" in mapa.split("acharBairro", 1)[1]
    assert re.search(r'<input[^>]*id="busca-bairro"', texto(site, "index.html"))


def test_o_site_nao_tem_numero_de_chamado_nem_coordenada_exata(tmp_path):
    _, site = coletado(tmp_path)
    conexao = montar_base(LISTA_DOS_FILTROS)
    proibidos = set()
    for id_chamado, porta, latitude, longitude in conexao.sql(
        "SELECT id_chamado, numero_logradouro, latitude, longitude FROM chamado"
    ).fetchall():
        proibidos |= {id_chamado, f"{latitude}", f"{longitude}", f":{porta},", f"[{porta},"}
    for arquivo in site.rglob("*"):
        if arquivo.is_file():
            conteudo = arquivo.read_text(encoding="utf-8-sig")
            for campo in ("id_chamado", "numero_logradouro", "latitude", "longitude",
                          "Remoção de entulho", "Reparo de lâmpada", "data_fim", *proibidos):
                assert campo not in conteudo, f"{arquivo.name} traz {campo}"


def test_fatia_com_coluna_a_mais_nao_entra_no_site(tmp_path):
    _, saida, _, _ = rodar_coleta(tmp_path, LISTA_DOS_FILTROS)
    caminho = saida / "filtros" / "tudo.json"
    fatia = json.loads(caminho.read_text(encoding="utf-8"))
    fatia["id"] = list(range(len(fatia["q"])))
    caminho.write_text(json.dumps(fatia), encoding="utf-8")
    with pytest.raises(EntradaInvalida) as erro:
        montar_site(saida, tmp_path / "site")
    assert "tudo.json" in str(erro.value) and "O que fazer" in str(erro.value)
    assert not (tmp_path / "site").exists()


def test_fatia_que_falta_avisa_o_que_fazer(tmp_path):
    _, saida, _, _ = rodar_coleta(tmp_path, LISTA_DOS_FILTROS)
    (saida / "filtros" / "2024-01.json").unlink()
    with pytest.raises(EntradaInvalida) as erro:
        montar_site(saida, tmp_path / "site")
    assert "2024-01.json" in str(erro.value) and "O que fazer" in str(erro.value)


def test_montar_de_novo_apaga_as_fatias_antigas_do_site(tmp_path):
    _, site = coletado(tmp_path)
    (site / "filtros" / "2010-01.json").write_text("{}", encoding="utf-8")
    (tmp_path / "outra").mkdir()
    montar_site(agregado(tmp_path / "outra"), site)
    assert not (site / "filtros").exists()


# ---- O filtro é só do mapa; página de método (issue #31) ------------------------------

FRASE_DO_FILTRO = (
    "Os filtros mudam só o mapa. As tabelas para baixar trazem sempre os totais sem filtro."
)


def test_o_site_e_o_metodo_dizem_que_o_filtro_e_so_do_mapa(tmp_path):
    _, site = coletado(tmp_path)
    assert FRASE_DO_FILTRO in sem_marcas(texto(site, "index.html"))
    assert FRASE_DO_FILTRO in sem_marcas(texto(site, "metodo.html"))


def test_metodo_explica_os_filtros(tmp_path):
    _, site = coletado(tmp_path)
    pagina = sem_marcas(texto(site, "metodo.html"))
    for trecho in (
        "Como funcionam os filtros",
        "data de abertura",
        "as duas datas entram",
        "fechados ou não",
        "Com mais de um filtro, entram só os chamados que atendem a todos",
        "Um quadrado que fica sem chamados some do mapa enquanto o filtro está ligado",
        "A busca de bairro só leva o mapa até o bairro e não muda a soma",
        "A mediana de dias até fechar só aparece sem filtro",
    ):
        assert trecho in pagina, trecho
    for palavra in PALAVRAS_QUE_COMPARAM:
        assert palavra not in pagina.replace(FRASE, "").lower(), palavra


BLOCO_DO_PRAZO = """prazo (dentro_prazo) por situação, entre os chamados de problema público:
  A Vencer / Encerrado: 1915000
  A Vencer / Não Encerrado: 85000
  Fora do prazo / Encerrado: 400000
  (vazio) / Encerrado: 12
"""


def test_metodo_mostra_a_nota_do_prazo_com_os_numeros_da_coleta(tmp_path):
    pagina = montar_com_resumo(tmp_path, RESUMO_SO_PROBLEMA_PUBLICO + BLOCO_DO_PRAZO)
    for trecho in (
        "A Vencer / Encerrado: 1.915.000 chamados",
        "A Vencer / Não Encerrado: 85.000 chamados",
        "Fora do prazo / Encerrado: 400.000 chamados",
        "(vazio) / Encerrado: 12 chamados",
        "2.000.000 chamados estão com o prazo \"A Vencer\", mas só 85.000 não estão encerrados",
        "parece não ser atualizada depois que o chamado fecha",
    ):
        assert trecho in pagina, trecho


def test_metodo_sem_o_bloco_do_prazo_nao_fala_do_prazo(tmp_path):
    pagina = montar_com_resumo(tmp_path, RESUMO_SO_PROBLEMA_PUBLICO)
    assert "A Vencer" not in pagina


def test_metodo_da_coleta_mostra_o_prazo_cruzado_com_a_situacao(tmp_path):
    # As duas pontas juntas: o bloco que a coleta grava, lido pelo montador.
    _, site = coletado(tmp_path)
    pagina = sem_marcas(texto(site, "metodo.html"))
    assert "No prazo / Encerrado: 5 chamados" in pagina
    assert "No prazo / Não Encerrado: 4 chamados" in pagina
