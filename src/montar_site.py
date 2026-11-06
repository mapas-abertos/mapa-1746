"""Montador do site do mapa v1: quadrados de 100 m coloridos, tabelas para baixar e método.

Pedido na issue #16. Lê, de uma pasta, as quatro saídas do agregador (ou da coleta, que grava
o mesmo formato): quadrados.geojson, quadrados.csv, ruas.csv e resumo.txt. Grava, em outra
pasta, o site pronto: um mapa (index.html), a página de método e fonte (metodo.html) e as duas
tabelas para baixar. Só as quatro saídas entram: nenhum outro arquivo da pasta de entrada vai
para o site, e nada traz chamado individual, coordenada de chamado ou identificador.

Os dados vão num arquivo .js (dados.js), e não são buscados pela rede: o site não precisa
de servidor de dados. Para ver o mapa de fundo, sirva a pasta por http (o OpenStreetMap
bloqueia o pedido de uma página aberta do disco, com duplo clique, porque ela não diz de
que site vem). Só o mapa de fundo e a biblioteca Leaflet vêm da internet. Publicar no GitHub Pages fica para depois do OK do advogado (ver decisoes.md).

Uso, a partir da raiz do repositório:

    .venv/Scripts/python src/montar_site.py dados/saida --saida dados/site
    Para ver as opções: --ajuda

Depois, sirva a pasta e abra o endereço no navegador:

    .venv/Scripts/python -m http.server 8765 --bind 127.0.0.1 -d dados/site
    http://127.0.0.1:8765
"""

import argparse
import html
import json
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

# Quadrado com "menos de N" chamados: cinza, fora da escala acima.
COR_MENOS_DE = "#b8b8b8"

# O texto da cor, igual na legenda e na página de método (ver a issue #16).
FRASE_DA_COR = (
    "A cor mostra onde se pede mais, e isso acompanha onde há mais gente e mais movimento. "
    "Não mostra onde a Prefeitura atende pior."
)

# Onde está a fonte, a licença do código e a tabela de origem.
TABELA_DE_ORIGEM = "datario.adm_central_atendimento_1746.chamado"
LINK_DATA_RIO = "https://data.rio/"
LINK_DO_CODIGO = "https://github.com/mapas-abertos/mapa-1746"

# Biblioteca do mapa por CDN, com a versão fixa. O "integrity" faz o navegador recusar o
# arquivo se ele mudar. Trocar a versão: calcule o hash novo do arquivo e troque os dois.
LEAFLET = "https://unpkg.com/leaflet@1.9.4/dist"
LEAFLET_JS_HASH = "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
LEAFLET_CSS_HASH = "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="

# O que aparece no clique, na ordem. Quadrado abaixo do mínimo só mostra o primeiro.
TRACO = "—"

# ---------------------------------------------------------------------------------------

# O que o agregador (e a coleta) gravam. É só isso que o site lê e leva.
ENTRADAS = ("quadrados.geojson", "quadrados.csv", "ruas.csv", "resumo.txt")
TABELAS = ("ruas.csv", "quadrados.csv")
ARQUIVOS_DO_SITE = (
    "index.html", "metodo.html", "estilo.css", "mapa.js", "dados.js", "ruas.csv", "quadrados.csv",
)

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


def _ler_minimo(campos):
    valor = campos.get("mínimo para mostrar o número", "")
    if not valor.isdigit() or int(valor) < 1:
        raise EntradaInvalida(
            "O resumo.txt não diz o mínimo para mostrar o número. "
            "O que fazer: rode de novo o agregador (ou a coleta), que grava a linha "
            "\"mínimo para mostrar o número: N\" no resumo.txt."
        )
    return int(valor)


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
    resumo = _ler_resumo((pasta / "resumo.txt").read_text(encoding="utf-8"))
    return features, resumo


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
    if _numero(str(chamados)) is None:  # "menos de N"
        linhas = [["Chamados", str(chamados)]] + [
            [rotulo, TRACO] for rotulo in
            ("Atendidos", "Fechados", "Ainda abertos", "Mediana de dias até fechar")
        ]
        cor = COR_MENOS_DE
    else:
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


def _dados_do_mapa(features):
    return {
        "limites": LIMITES_DO_RIO,
        "quadrados": {
            "type": "FeatureCollection",
            "features": [_quadrado_para_o_mapa(feature) for feature in features],
        },
    }


# ---- Páginas --------------------------------------------------------------------------


def _legenda(minimo):
    itens = []
    for posicao, (limite, cor) in enumerate(CLASSES):
        inicio = max(limite, minimo) if posicao == 0 else limite
        if posicao + 1 < len(CLASSES):
            fim = CLASSES[posicao + 1][0] - 1
            rotulo = f"{_milhar(inicio)} a {_milhar(fim)}" if fim > inicio else _milhar(inicio)
        else:
            rotulo = f"{_milhar(inicio)} ou mais"
        itens.append((cor, rotulo))
    itens.append((COR_MENOS_DE, f"Menos de {minimo} chamados (número não mostrado)"))
    linhas = "\n".join(
        f'        <li><span class="amostra" style="background:{cor}"></span>{html.escape(rotulo)}</li>'
        for cor, rotulo in itens
    )
    return linhas


def _pagina_do_mapa(minimo):
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
    </nav>
  </header>
  <div id="mapa" role="application" aria-label="Mapa dos chamados do 1746 por quadrado de 100 m"></div>
  <section class="legenda" aria-label="Legenda">
    <h2>Chamados por quadrado</h2>
    <ul>
{_legenda(minimo)}
    </ul>
    <p>{html.escape(FRASE_DA_COR)}</p>
  </section>
  <script src="{LEAFLET}/leaflet.js" integrity="{LEAFLET_JS_HASH}" crossorigin=""></script>
  <script src="dados.js"></script>
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
    gravar, coordenada fora do município. O que o resumo não traz não aparece.
    """
    total = _numero_do_resumo(resumo, "contados", "chamados lidos")
    itens = []
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
    fora = _numero_do_resumo(resumo, "coordenada fora do município")
    if fora is not None:
        itens.append(
            f"{_milhar(fora)} chamados com coordenada fora do município do Rio foram descartados "
            f"do mapa, porque a coordenada está provavelmente errada."
        )
    return "\n".join(f"      <li>{html.escape(item)}</li>" for item in itens)


def _pagina_de_metodo(minimo, resumo):
    mais_recente = _data_do_resumo(
        resumo, "chamado mais recente na base", "chamado mais recente", "data do chamado mais recente"
    )
    coleta = _data_do_resumo(resumo, "data da coleta", "coleta")
    fora_do_mapa = _o_que_fica_de_fora(resumo)
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
    <p>O total de chamados do 1746 do Rio de Janeiro em cada quadrado de 100 m por 100 m,
    somando todos os chamados da base, sem filtro. Um toque num quadrado mostra os números dele:
    chamados, atendidos, fechados, ainda abertos (chamados menos fechados) e a mediana de dias
    até fechar.</p>

    <h2>O que a cor quer dizer</h2>
    <p>{html.escape(FRASE_DA_COR)}</p>
    <p>Os quadrados cinza têm menos de {minimo} chamados: o número não é mostrado.</p>

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
      e por rua: nenhum chamado individual nem coordenada exata.</li>
      <li><strong>Regra do mínimo.</strong> Quadrado ou rua com menos de {minimo} chamados
      aparece só como "menos de {minimo}", sem os outros números, para não identificar quem
      chamou. Nesses casos os outros campos aparecem como "{TRACO}".</li>
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
    <a href="ruas.csv" download>por rua</a> e <a href="quadrados.csv" download>por quadrado</a>.</p>
  </main>
</body>
</html>
"""


ESTILO = """\
/* Estilo do site do Mapa 1746. Funciona a partir de 375 px de largura, sem rolar para o lado. */
* { box-sizing: border-box; }
html, body { margin: 0; max-width: 100%; overflow-x: hidden; }
body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: #1f2933; line-height: 1.4; }
a { color: #0b5cad; }

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
.legenda { padding: 8px 12px; background: #fff; border-top: 1px solid #d9dee3; font-size: 0.8rem; max-height: 42vh; overflow-y: auto; }
.legenda h2 { margin: 0 0 4px; font-size: 0.9rem; }
.legenda ul { list-style: none; margin: 0 0 6px; padding: 0; display: flex; flex-wrap: wrap; gap: 2px 14px; }
.legenda li { display: flex; align-items: center; gap: 6px; }
.legenda p { margin: 0; }
.amostra { display: inline-block; width: 16px; height: 16px; border: 1px solid rgba(0, 0, 0, 0.35); border-radius: 3px; flex: none; }

/* Texto do clique no quadrado. */
.numeros { margin: 0; padding: 0; border-collapse: collapse; font-size: 0.9rem; }
.numeros th { text-align: left; font-weight: normal; padding: 1px 12px 1px 0; }
.numeros td { text-align: right; font-weight: 600; padding: 1px 0; }

/* Página de método. */
.texto { max-width: 42rem; margin: 0 auto; padding: 12px 16px 32px; }
.texto h1 { font-size: 1.5rem; }
.texto h2 { font-size: 1.1rem; margin-top: 1.5rem; }
.texto code { overflow-wrap: anywhere; }
.texto a { overflow-wrap: anywhere; }
"""


MAPA_JS = """\
// Mapa 1746 (v1). Lê window.MAPA_DADOS (dados.js) e desenha os quadrados com a biblioteca Leaflet.
(function () {
  var dados = window.MAPA_DADOS;
  var mapa = L.map("mapa", { preferCanvas: true });
  mapa.fitBounds(dados.limites);

  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(mapa);

  // O texto do clique é montado com textContent: nada do dado vira HTML.
  function textoDoClique(linhas) {
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
    return tabela;
  }

  L.geoJSON(dados.quadrados, {
    style: function (feature) {
      return { color: feature.properties.cor, weight: 0.5, fillColor: feature.properties.cor, fillOpacity: 0.8 };
    },
    onEachFeature: function (feature, camada) {
      camada.bindPopup(function () { return textoDoClique(feature.properties.linhas); });
    }
  }).addTo(mapa);
})();
"""


# ---- Montagem -------------------------------------------------------------------------


def _gravar_tabela(origem, destino):
    """Copia a tabela com a marca de UTF-8 no início, para o Excel abrir os acentos certos."""
    conteudo = Path(origem).read_text(encoding="utf-8-sig")
    Path(destino).write_text(conteudo, encoding="utf-8-sig", newline="")


def montar_site(entrada, saida):
    """Lê as saídas do agregador em `entrada` e grava o site na pasta `saida`."""
    entrada = Path(entrada)
    features, resumo = _ler_entradas(entrada)
    minimo = _ler_minimo(resumo)
    dados = _dados_do_mapa(features)  # confere o formato antes de gravar qualquer coisa

    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "index.html").write_text(_pagina_do_mapa(minimo), encoding="utf-8")
    (saida / "metodo.html").write_text(_pagina_de_metodo(minimo, resumo), encoding="utf-8")
    (saida / "estilo.css").write_text(ESTILO, encoding="utf-8")
    (saida / "mapa.js").write_text(MAPA_JS, encoding="utf-8")
    corpo = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    (saida / "dados.js").write_text(f"window.MAPA_DADOS = {corpo};\n", encoding="utf-8")
    for nome in TABELAS:
        _gravar_tabela(entrada / nome, saida / nome)


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
        usage="%(prog)s ENTRADA --saida PASTA",
        description="Monta o site do mapa a partir das saídas do agregador.",
        formatter_class=_Formatador,
        add_help=False,
    )
    leitor.add_argument("entrada", nargs="?", metavar="ENTRADA",
                        help="pasta com quadrados.geojson, quadrados.csv, ruas.csv e resumo.txt")
    leitor.add_argument("--saida", metavar="PASTA", help="pasta onde gravar o site")
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
        montar_site(opcoes.entrada, opcoes.saida)
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
