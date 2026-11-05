"""Testes do montador do site (issue #16): o mapa v1 a partir das saídas do agregador.

Cada teste nasce de um item do "Quando está pronta" da issue, antes do código (TDD).
Os dados são os mesmos chamados fictícios do teste do agregador (testes/test_agregador.py):
3 quadrados, 2 lado a lado no Centro e 1 na Tijuca.
"""

import json
import re
from pathlib import Path

import pytest
from test_agregador import LISTA_EXEMPLO

from agregador import agregar
from montar_site import (
    ARQUIVOS_DO_SITE,
    COR_MENOS_DE,
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


def agregado(tmp_path, minimo=5, resumo_extra=""):
    """Roda o agregador com a lista fictícia e devolve a pasta com as 4 saídas."""
    entrada = tmp_path / "chamados.csv"
    entrada.write_text(LISTA_EXEMPLO, encoding="utf-8")
    pasta = tmp_path / "agregado"
    agregar(entrada, pasta, minimo=minimo)
    if resumo_extra:
        with open(pasta / "resumo.txt", "a", encoding="utf-8") as arquivo:
            arquivo.write(resumo_extra)
    return pasta


def montar(tmp_path, minimo=5, resumo_extra=""):
    pasta = agregado(tmp_path, minimo, resumo_extra)
    site = tmp_path / "site"
    montar_site(pasta, site)
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
    _, site = montar(tmp_path, minimo=5)
    assert linhas(quadrado(site, Q1))["Chamados"] == "6"
    segunda = tmp_path / "segunda"
    segunda.mkdir()
    montar_site(agregado(segunda, minimo=7), site)
    assert linhas(quadrado(site, Q1))["Chamados"] == "menos de 7"


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


def test_a_cor_e_a_quantidade_de_chamados_e_menos_de_n_tem_cor_propria(tmp_path):
    _, site = montar(tmp_path, minimo=5)
    cor_q1 = quadrado(site, Q1)["properties"]["cor"]
    cor_q2 = quadrado(site, Q2)["properties"]["cor"]
    assert cor_q1 in CORES_DAS_CLASSES
    assert cor_q2 == COR_MENOS_DE
    assert COR_MENOS_DE not in CORES_DAS_CLASSES


def test_quanto_mais_chamados_mais_escura_a_cor(tmp_path):
    # Com mínimo 1 todos têm número. Os quadrados de 6 e de 5 chamados caem na mesma classe.
    # Ordem das classes: a lista de cores vai da mais clara à mais escura.
    assert len(set(CORES_DAS_CLASSES)) == len(CORES_DAS_CLASSES) >= 4
    _, site = montar(tmp_path, minimo=1)
    cores = [quadrado(site, i)["properties"]["cor"] for i in (Q1, Q2, Q3)]
    assert all(cor in CORES_DAS_CLASSES for cor in cores)


def test_a_legenda_mostra_as_cores_e_o_quadrado_menos_de_n(tmp_path):
    _, site = montar(tmp_path, minimo=5)
    html = texto(site, "index.html")
    legenda = sem_marcas(html)
    assert "Menos de 5 chamados" in legenda
    assert "número não mostrado" in legenda
    for cor in (*CORES_DAS_CLASSES, COR_MENOS_DE):
        assert cor in html  # cada cor da legenda aparece como amostra
    assert "5 a 9" in legenda  # a primeira classe começa no mínimo
    assert "1.000 ou mais" in legenda


def test_a_frase_da_cor_esta_na_legenda_e_na_pagina_de_metodo(tmp_path):
    _, site = montar(tmp_path)
    assert FRASE in sem_marcas(texto(site, "index.html"))
    assert FRASE in sem_marcas(texto(site, "metodo.html"))


# ---- Clique no quadrado ----------------------------------------------------------------


def test_clique_mostra_chamados_atendidos_fechados_ainda_abertos_e_mediana(tmp_path):
    _, site = montar(tmp_path, minimo=1)
    assert quadrado(site, Q1)["properties"]["linhas"] == [
        ["Chamados", "6"],
        ["Atendidos", "3"],
        ["Fechados", "4"],
        ["Ainda abertos", "2"],
        ["Mediana de dias até fechar", "1,5"],
    ]


def test_ainda_abertos_e_chamados_menos_fechados(tmp_path):
    _, site = montar(tmp_path, minimo=1)
    for identificador in (Q1, Q2, Q3):
        valores = linhas(quadrado(site, identificador))
        assert int(valores["Ainda abertos"]) == int(valores["Chamados"]) - int(valores["Fechados"])


def test_abaixo_do_minimo_mostra_so_menos_de_n_e_o_resto_em_traco(tmp_path):
    _, site = montar(tmp_path, minimo=5)
    assert quadrado(site, Q2)["properties"]["linhas"] == [
        ["Chamados", "menos de 5"],
        ["Atendidos", "—"],
        ["Fechados", "—"],
        ["Ainda abertos", "—"],
        ["Mediana de dias até fechar", "—"],
    ]


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
    agregar(entrada, pasta, minimo=1)
    site = tmp_path / "site"
    montar_site(pasta, site)
    (feature,) = dados_do_mapa(site)["quadrados"]["features"]
    assert linhas(feature)["Fechados"] == "0"
    assert linhas(feature)["Ainda abertos"] == "3"
    assert linhas(feature)["Mediana de dias até fechar"] == "—"


def test_nunca_aparece_null_none_ou_nan_no_site(tmp_path):
    _, site = montar(tmp_path, minimo=5)
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
    agregar(entrada, pasta, minimo=1)
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


def test_metodo_traz_fonte_grade_minimo_licencas_e_limites(tmp_path):
    _, site = montar(tmp_path, minimo=5)
    html = texto(site, "metodo.html")
    pagina = sem_marcas(html)
    assert "datario.adm_central_atendimento_1746.chamado" in pagina
    assert re.search(r'href="https://[^"]*data\.rio[^"]*"', html)
    assert "100 m" in pagina
    assert "menos de 5" in pagina.lower()
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


def test_metodo_diz_a_definir_quando_o_resumo_nao_traz_as_datas(tmp_path):
    _, site = montar(tmp_path)  # o resumo do agregador não tem as duas datas
    pagina = sem_marcas(texto(site, "metodo.html"))
    assert re.search(r"chamado mais recente[^.]*a definir", pagina, re.IGNORECASE)
    assert re.search(r"coleta[^.]*a definir", pagina, re.IGNORECASE)


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


def test_resumo_sem_o_minimo_avisa_o_que_fazer(tmp_path):
    pasta = agregado(tmp_path)
    (pasta / "resumo.txt").write_text("chamados lidos: 19\n", encoding="utf-8")
    with pytest.raises(EntradaInvalida) as erro:
        montar_site(pasta, tmp_path / "site")
    assert "mínimo" in str(erro.value)
    assert "O que fazer" in str(erro.value)


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
    # Abre com duplo clique (file://): nada de fetch, tudo por <script src="dados.js">.
    _, site = montar(tmp_path)
    assert "fetch(" not in texto(site, "mapa.js")
    assert '<script src="dados.js">' in texto(site, "index.html")
    assert Path(site / "dados.js").stat().st_size > 0
