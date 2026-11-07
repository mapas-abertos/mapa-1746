"""Agregador: totais dos chamados do 1746 por rua e por quadrado de 100 m.

Pedido na issue #7. Lê uma lista de chamados (CSV, um chamado por linha, com as colunas
da tabela datario.adm_central_atendimento_1746.chamado) e grava, numa pasta:

- ruas.csv: totais por bairro e rua;
- quadrados.csv: totais por quadrado de 100 m x 100 m;
- quadrados.geojson: os mesmos quadrados, com o contorno, para o mapa;
- resumo.txt: quantos chamados foram lidos e quantos ficaram sem rua ou sem coordenada.

Em cada linha: chamados, atendidos, fechados e mediana de dias até fechar. Toda rua e
todo quadrado mostra os números, mesmo com 1 chamado (o mínimo saiu na issue #31).
Nenhum arquivo de saída traz chamado individual, coordenada de chamado,
identificador ou número de porta: só os totais e o contorno do quadrado.

Os quadrados seguem a grade em metros SIRGAS 2000 / UTM 23S (EPSG:31983), com os
cantos em múltiplos de 100 m. Cada quadrado é identificado pelo canto sudoeste, em
metros: "687300_7465600" é o quadrado de x 687300 a 687400 e y 7465600 a 7465700.

Uso, a partir da raiz do repositório:

    .venv/Scripts/python src/agregador.py dados/chamados.csv --saida dados/saida
    (opcional) --inicio 2025-01-01 --fim 2025-12-31   conta só os chamados abertos nesse período
    Para ver as opções: --ajuda

Os filtros do mapa (issue #31) saem só da coleta, que tem a lista de classificação e as
colunas de status, prazo e órgão.
"""

import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from pyproj import Transformer

# ---- Regras do agregador (mudou uma? registre em decisoes.md) -------------------------

# Colunas que a lista de chamados precisa ter. Outras colunas são ignoradas.
COLUNAS_OBRIGATORIAS = (
    "data_inicio", "data_fim", "tipo", "subtipo", "tipo_situacao",
    "bairro", "rua", "latitude", "longitude",
)

# Rua com um destes valores conta como "sem rua".
RUA_VAZIA = {"", "0"}

# Situação que conta como atendido.
SITUACAO_ATENDIDO = "Atendido"

# Grade dos quadrados: lado em metros e sistema de coordenadas em metros.
LADO_DO_QUADRADO = 100
GRADE_EM_METROS = "EPSG:31983"  # SIRGAS 2000 / UTM zona 23S
GRAUS = "EPSG:4326"  # latitude e longitude, como no GeoJSON

# Casas decimais da mediana de dias e dos cantos do quadrado no GeoJSON (6 casas = ~10 cm).
CASAS_DA_MEDIANA = 1
CASAS_DO_GEOJSON = 6

# Os arquivos de saída usam ponto e vírgula, como a entrada, e UTF-8.
SEPARADOR = ";"

# Quantos chamados com coordenada são convertidos para metros de uma vez.
LOTE = 100_000

# ---------------------------------------------------------------------------------------

CABECALHO_RUAS = ["bairro", "rua", "chamados", "atendidos", "fechados", "mediana_dias_ate_fechar"]
CABECALHO_QUADRADOS = ["quadrado", "chamados", "atendidos", "fechados", "mediana_dias_ate_fechar"]


class EntradaInvalida(ValueError):
    """A lista de chamados não está no formato esperado. A mensagem diz o que fazer."""


@dataclass
class Totais:
    """Os números de uma rua ou de um quadrado."""

    chamados: int = 0
    atendidos: int = 0
    dias_ate_fechar: list = field(default_factory=list)  # um valor por chamado fechado

    def somar(self, atendido, dias):
        self.chamados += 1
        if atendido:
            self.atendidos += 1
        if dias is not None:
            self.dias_ate_fechar.append(dias)

    @property
    def fechados(self):
        return len(self.dias_ate_fechar)

    @property
    def mediana(self):
        if not self.dias_ate_fechar:
            return None
        return round(statistics.median(self.dias_ate_fechar), CASAS_DA_MEDIANA)


@dataclass
class Resumo:
    """O que aconteceu com os chamados lidos."""

    inicio: date | None = None
    fim: date | None = None
    lidos: int = 0
    fora_do_periodo: int = 0
    sem_rua: int = 0
    sem_coordenada: int = 0
    ruas: int = 0
    quadrados: int = 0

    @property
    def contados(self):
        return self.lidos - self.fora_do_periodo

    def texto(self):
        periodo = "todos"
        if self.inicio or self.fim:
            periodo = f"{self.inicio or 'início'} a {self.fim or 'hoje'}"
        return "\n".join([
            "Resumo do agregador (chamados do 1746)",
            f"período: {periodo}",
            f"chamados lidos: {self.lidos}",
            f"fora do período: {self.fora_do_periodo}",
            f"contados: {self.contados}",
            f"sem rua: {self.sem_rua}",
            f"sem coordenada: {self.sem_coordenada}",
            f"ruas: {self.ruas}",
            f"quadrados: {self.quadrados}",
        ]) + "\n"


# ---- Leitura --------------------------------------------------------------------------


def _ler_data(texto, coluna, linha):
    """Lê '2025-03-01 10:00', '2025-03-01T10:00:00', com ou sem fuso. Com fuso, passa para UTC."""
    valor = texto.strip()
    if valor.endswith(" UTC"):
        valor = valor[:-4]
    try:
        momento = datetime.fromisoformat(valor)
    except ValueError:
        raise EntradaInvalida(
            f"Linha {linha}: a coluna {coluna} tem \"{texto}\", que não é uma data. "
            f"O que fazer: use o formato AAAA-MM-DD HH:MM, por exemplo 2025-03-01 10:00."
        ) from None
    if momento.tzinfo is not None:
        momento = momento.astimezone(timezone.utc).replace(tzinfo=None)
    return momento


def _ler_coordenada(texto, coluna, linha):
    """Número da coordenada, ou None se vazia ou 0 (sem coordenada).

    A mensagem de erro não repete o valor: coordenada de chamado não vai para log nenhum.
    """
    valor = texto.strip().replace(",", ".")
    if not valor:
        return None
    try:
        numero = float(valor)
    except ValueError:
        numero = math.nan
    if not math.isfinite(numero):
        raise EntradaInvalida(
            f"Linha {linha}: a coluna {coluna} não é um número. "
            f"O que fazer: confira a linha no arquivo de entrada; sem coordenada, deixe vazio."
        )
    return None if numero == 0 else numero


def _abrir_lista(arquivo):
    """Abre o CSV (ponto e vírgula ou vírgula) e confere as colunas."""
    primeira = arquivo.readline()
    if not primeira.strip():
        raise EntradaInvalida(
            "O arquivo de entrada está vazio. O que fazer: confira se a coleta gravou os chamados."
        )
    separador = ";" if primeira.count(";") >= primeira.count(",") else ","
    arquivo.seek(0)
    leitor = csv.DictReader(arquivo, delimiter=separador)
    leitor.fieldnames = [nome.strip() for nome in leitor.fieldnames]
    faltam = [coluna for coluna in COLUNAS_OBRIGATORIAS if coluna not in leitor.fieldnames]
    if faltam:
        plural = "a coluna" if len(faltam) == 1 else "as colunas"
        raise EntradaInvalida(
            f"Falta {plural} {', '.join(faltam)} no arquivo de entrada. "
            f"O que fazer: a lista precisa das colunas {', '.join(COLUNAS_OBRIGATORIAS)}, "
            f"com estes nomes, na primeira linha."
        )
    return leitor


# ---- Agregação ------------------------------------------------------------------------


def agregar(entrada, saida, *, inicio=None, fim=None):
    """Lê a lista de chamados em `entrada` e grava os totais na pasta `saida`.

    `inicio` e `fim` (datas, opcionais): conta só os chamados abertos nesses dias,
    contando os dois. Devolve o Resumo.
    """
    if inicio and fim and fim < inicio:
        raise ValueError(
            "A data final do período (--fim) vem antes da inicial (--inicio). "
            "O que fazer: confira as duas datas; o --fim tem de ser igual ou depois do --inicio."
        )

    resumo = Resumo(inicio=inicio, fim=fim)
    ruas = defaultdict(Totais)
    quadrados = defaultdict(Totais)
    para_metros = Transformer.from_crs(GRAUS, GRADE_EM_METROS, always_xy=True)
    lote = []  # (longitude, latitude, atendido, dias) dos chamados com coordenada

    def esvaziar_lote():
        if not lote:
            return
        longitudes, latitudes, _, _ = zip(*lote)
        xs, ys = para_metros.transform(longitudes, latitudes)
        for x, y, (_, _, atendido, dias) in zip(xs, ys, lote):
            canto = (
                math.floor(x / LADO_DO_QUADRADO) * LADO_DO_QUADRADO,
                math.floor(y / LADO_DO_QUADRADO) * LADO_DO_QUADRADO,
            )
            quadrados[canto].somar(atendido, dias)
        lote.clear()

    with open(entrada, encoding="utf-8-sig", newline="") as arquivo:
        leitor = _abrir_lista(arquivo)
        for chamado in leitor:
            linha = leitor.line_num
            resumo.lidos += 1
            aberto = _ler_data(chamado["data_inicio"] or "", "data_inicio", linha)
            if (inicio and aberto.date() < inicio) or (fim and aberto.date() > fim):
                resumo.fora_do_periodo += 1
                continue

            dias = None
            if (chamado["data_fim"] or "").strip():
                fechado = _ler_data(chamado["data_fim"], "data_fim", linha)
                dias = (fechado - aberto).total_seconds() / 86400
            atendido = (chamado["tipo_situacao"] or "").strip() == SITUACAO_ATENDIDO

            rua = (chamado["rua"] or "").strip()
            if rua in RUA_VAZIA:
                resumo.sem_rua += 1
            else:
                ruas[((chamado["bairro"] or "").strip(), rua)].somar(atendido, dias)

            latitude = _ler_coordenada(chamado["latitude"] or "", "latitude", linha)
            longitude = _ler_coordenada(chamado["longitude"] or "", "longitude", linha)
            if latitude is None or longitude is None:
                resumo.sem_coordenada += 1
            else:
                lote.append((longitude, latitude, atendido, dias))
                if len(lote) >= LOTE:
                    esvaziar_lote()
        esvaziar_lote()

    resumo.ruas = len(ruas)
    resumo.quadrados = len(quadrados)
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    gravar_ruas(saida / "ruas.csv", ruas)
    gravar_quadrados(saida, quadrados)
    (saida / "resumo.txt").write_text(resumo.texto(), encoding="utf-8")
    return resumo


# ---- Gravação -------------------------------------------------------------------------


def numeros(totais):
    """[chamados, atendidos, fechados, mediana]."""
    return [totais.chamados, totais.atendidos, totais.fechados, totais.mediana]


def _celula(valor):
    return "" if valor is None else str(valor)


def _gravar_csv(caminho, cabecalho, linhas):
    with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter=SEPARADOR, lineterminator="\n")
        escritor.writerow(cabecalho)
        for linha in linhas:
            escritor.writerow([_celula(valor) for valor in linha])


def gravar_ruas(caminho, ruas):
    linhas = (
        [bairro, rua, *numeros(ruas[(bairro, rua)])] for bairro, rua in sorted(ruas)
    )
    _gravar_csv(caminho, CABECALHO_RUAS, linhas)


def gravar_quadrados(saida, quadrados):
    para_graus = Transformer.from_crs(GRADE_EM_METROS, GRAUS, always_xy=True)
    linhas = []
    features = []
    for x, y in sorted(quadrados):
        linha = [f"{x}_{y}", *numeros(quadrados[(x, y)])]
        linhas.append(linha)
        lado = LADO_DO_QUADRADO
        # Sudoeste, sudeste, nordeste, noroeste e de volta ao sudoeste (sentido anti-horário).
        cantos_x = [x, x + lado, x + lado, x, x]
        cantos_y = [y, y, y + lado, y + lado, y]
        longitudes, latitudes = para_graus.transform(cantos_x, cantos_y)
        contorno = [
            [round(lon, CASAS_DO_GEOJSON), round(lat, CASAS_DO_GEOJSON)]
            for lon, lat in zip(longitudes, latitudes)
        ]
        features.append({
            "type": "Feature",
            "properties": dict(zip(CABECALHO_QUADRADOS, linha)),
            "geometry": {"type": "Polygon", "coordinates": [contorno]},
        })
    _gravar_csv(saida / "quadrados.csv", CABECALHO_QUADRADOS, linhas)
    geojson = {"type": "FeatureCollection", "features": features}
    (saida / "quadrados.geojson").write_text(
        json.dumps(geojson, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


# ---- Linha de comando -----------------------------------------------------------------


# Todas as mensagens saem em português, com "O que fazer". O argparse (a parte do Python
# que lê a linha de comando) só fala inglês: por isso as opções obrigatórias são
# conferidas aqui, os valores são lidos pelas funções abaixo, e o error() é trocado.

VEJA_A_AJUDA = "veja as opções com python src/agregador.py --ajuda."

# O que dizer quando falta cada parte obrigatória.
FALTA = {
    "entrada": (
        "o arquivo de entrada",
        "escreva o caminho da lista de chamados logo depois de agregador.py, "
        "por exemplo dados/chamados.csv.",
    ),
    "saida": ("a --saida", "informe a pasta onde gravar os arquivos, por exemplo --saida dados/saida."),
}

# A opção --minimo saiu na issue #31. Quem ainda a usa recebe esta mensagem, e nada roda.
MENSAGEM_DO_MINIMO = "A opção --minimo saiu (ver decisoes.md). Rode sem ela."

# Exemplo de valor de cada opção, para as mensagens.
EXEMPLO = {
    "--saida": "--saida dados/saida",
    "--inicio": "--inicio 2025-01-01",
    "--fim": "--fim 2025-12-31",
}


class ErroNaLinhaDeComando(Exception):
    """Algo errado nas opções da linha de comando. A mensagem diz o que fazer."""


class Formatador(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, "uso: " if prefix is None else prefix)


class LeitorDeOpcoes(argparse.ArgumentParser):
    """O leitor da linha de comando, com os erros em português.

    `exemplos` e `veja_a_ajuda` mudam de uma ferramenta para outra (a coleta também usa).
    """

    def __init__(self, *args, exemplos=None, veja_a_ajuda=VEJA_A_AJUDA, **kwargs):
        super().__init__(*args, **kwargs)
        self.exemplos = EXEMPLO if exemplos is None else exemplos
        self.veja_a_ajuda = veja_a_ajuda

    def error(self, message):
        raise ErroNaLinhaDeComando(traduzir(message, self.exemplos, self.veja_a_ajuda))


def traduzir(mensagem, exemplos=EXEMPLO, veja_a_ajuda=VEJA_A_AJUDA):
    """Põe em português os erros que o próprio argparse ainda pode dar."""
    opcao, _, detalhe = mensagem.partition(": ")
    if opcao.startswith("argument "):
        opcao = opcao.removeprefix("argument ").split("/")[-1]
        if "O que fazer:" in detalhe:  # veio de uma das funções de leitura abaixo
            return detalhe
        if "expected one argument" in detalhe:
            exemplo = exemplos.get(opcao, opcao)
            return f"Falta o valor do {opcao}. O que fazer: escreva o valor logo depois, por exemplo {exemplo}."
    if opcao == "unrecognized arguments":
        return f"Não conheço {detalhe}. O que fazer: {veja_a_ajuda}"
    return f"Não entendi a linha de comando. O que fazer: {veja_a_ajuda}"


class OpcaoDoMinimoSaiu(argparse.Action):
    """Para a ferramenta, com a MENSAGEM_DO_MINIMO, se alguém ainda passar o --minimo."""

    def __call__(self, parser, namespace, values, option_string=None):
        raise ErroNaLinhaDeComando(MENSAGEM_DO_MINIMO)


def opcao_do_minimo_que_saiu(grupo):
    """O --minimo continua conhecido só para dar a mensagem certa; não aparece na ajuda."""
    grupo.add_argument("--minimo", nargs="?", action=OpcaoDoMinimoSaiu, help=argparse.SUPPRESS)


def _leitor_de_data(opcao):
    def ler(texto):
        try:
            return date.fromisoformat(texto)
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"O {opcao} tem \"{texto}\", que não é uma data. "
                f"O que fazer: use o formato AAAA-MM-DD, por exemplo {EXEMPLO[opcao]}."
            ) from None
    return ler


def _leitor_de_opcoes():
    leitor = LeitorDeOpcoes(
        prog="agregador.py",
        usage="%(prog)s ENTRADA --saida PASTA [--inicio AAAA-MM-DD] [--fim AAAA-MM-DD]",
        description="Totais dos chamados do 1746 por rua e por quadrado de 100 m.",
        formatter_class=Formatador,
        add_help=False,
    )
    arquivos = leitor.add_argument_group("arquivos")
    arquivos.add_argument("entrada", nargs="?", metavar="ENTRADA", help="lista de chamados (CSV)")
    arquivos.add_argument("--saida", metavar="PASTA", help="pasta onde gravar os arquivos")
    opcoes = leitor.add_argument_group("opções")
    opcao_do_minimo_que_saiu(opcoes)
    opcoes.add_argument("--inicio", type=_leitor_de_data("--inicio"), metavar="AAAA-MM-DD",
                        help="primeiro dia do período (opcional)")
    opcoes.add_argument("--fim", type=_leitor_de_data("--fim"), metavar="AAAA-MM-DD",
                        help="último dia do período (opcional)")
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


def main(argv=None):
    try:
        opcoes = _ler_opcoes(argv)
    except ErroNaLinhaDeComando as erro:
        for linha in str(erro).splitlines():
            print(f"ERRO: {linha}", file=sys.stderr)
        return 2
    try:
        resumo = agregar(opcoes.entrada, opcoes.saida, inicio=opcoes.inicio, fim=opcoes.fim)
    except FileNotFoundError:
        print(
            f"ERRO: não achei o arquivo {opcoes.entrada}. "
            f"O que fazer: confira o caminho e o nome do arquivo de entrada.",
            file=sys.stderr,
        )
        return 1
    except UnicodeDecodeError:
        print(
            "ERRO: o arquivo de entrada não está em UTF-8. "
            "O que fazer: salve a lista de novo como \"CSV UTF-8\".",
            file=sys.stderr,
        )
        return 1
    except ValueError as erro:  # inclui EntradaInvalida
        print(f"ERRO: {erro}", file=sys.stderr)
        return 1
    print(resumo.texto(), end="")
    print(f"Arquivos gravados em {opcoes.saida}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
