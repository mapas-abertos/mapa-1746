"""Agregador: totais dos chamados do 1746 por rua e por quadrado de 100 m.

Pedido na issue #7. Lê uma lista de chamados (CSV, um chamado por linha, com as colunas
da tabela datario.adm_central_atendimento_1746.chamado) e grava, numa pasta:

- ruas.csv: totais por bairro e rua;
- quadrados.csv: totais por quadrado de 100 m x 100 m;
- quadrados.geojson: os mesmos quadrados, com o contorno, para o mapa;
- resumo.txt: quantos chamados foram lidos e quantos ficaram sem rua ou sem coordenada.

Em cada linha: chamados, atendidos, fechados e mediana de dias até fechar. Rua ou
quadrado com menos chamados que o mínimo sai como "menos de N", sem os números.
Nenhum arquivo de saída traz chamado individual, coordenada de chamado,
identificador ou número de porta: só os totais e o contorno do quadrado.

Os quadrados seguem a grade em metros SIRGAS 2000 / UTM 23S (EPSG:31983), com os
cantos em múltiplos de 100 m. Cada quadrado é identificado pelo canto sudoeste, em
metros: "687300_7465600" é o quadrado de x 687300 a 687400 e y 7465600 a 7465700.

Uso, a partir da raiz do repositório:

    .venv/Scripts/python src/agregador.py dados/chamados.csv --saida dados/saida --minimo N
    (opcional) --inicio 2025-01-01 --fim 2025-12-31   conta só os chamados abertos nesse período

O valor do mínimo fica a definir até a consulta jurídica; por isso não há padrão.
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

    minimo: int
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
            f"mínimo para mostrar o número: {self.minimo}",
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


def agregar(entrada, saida, *, minimo, inicio=None, fim=None):
    """Lê a lista de chamados em `entrada` e grava os totais na pasta `saida`.

    `minimo`: rua ou quadrado com menos chamados que isso sai como "menos de N".
    `inicio` e `fim` (datas, opcionais): conta só os chamados abertos nesses dias,
    contando os dois. Devolve o Resumo.
    """
    if minimo < 1:
        raise ValueError("O mínimo precisa ser 1 ou mais.")
    if inicio and fim and fim < inicio:
        raise ValueError("A data final do período vem antes da inicial.")

    resumo = Resumo(minimo=minimo, inicio=inicio, fim=fim)
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
    _gravar_ruas(saida / "ruas.csv", ruas, minimo)
    _gravar_quadrados(saida, quadrados, minimo)
    (saida / "resumo.txt").write_text(resumo.texto(), encoding="utf-8")
    return resumo


# ---- Gravação -------------------------------------------------------------------------


def _numeros(totais, minimo):
    """[chamados, atendidos, fechados, mediana]; abaixo do mínimo, só "menos de N"."""
    if totais.chamados < minimo:
        return [f"menos de {minimo}", None, None, None]
    return [totais.chamados, totais.atendidos, totais.fechados, totais.mediana]


def _celula(valor):
    return "" if valor is None else str(valor)


def _gravar_csv(caminho, cabecalho, linhas):
    with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter=SEPARADOR, lineterminator="\n")
        escritor.writerow(cabecalho)
        for linha in linhas:
            escritor.writerow([_celula(valor) for valor in linha])


def _gravar_ruas(caminho, ruas, minimo):
    linhas = (
        [bairro, rua, *_numeros(ruas[(bairro, rua)], minimo)] for bairro, rua in sorted(ruas)
    )
    _gravar_csv(caminho, CABECALHO_RUAS, linhas)


def _gravar_quadrados(saida, quadrados, minimo):
    para_graus = Transformer.from_crs(GRADE_EM_METROS, GRAUS, always_xy=True)
    linhas = []
    features = []
    for x, y in sorted(quadrados):
        numeros = [f"{x}_{y}", *_numeros(quadrados[(x, y)], minimo)]
        linhas.append(numeros)
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
            "properties": dict(zip(CABECALHO_QUADRADOS, numeros)),
            "geometry": {"type": "Polygon", "coordinates": [contorno]},
        })
    _gravar_csv(saida / "quadrados.csv", CABECALHO_QUADRADOS, linhas)
    geojson = {"type": "FeatureCollection", "features": features}
    (saida / "quadrados.geojson").write_text(
        json.dumps(geojson, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


# ---- Linha de comando -----------------------------------------------------------------


def _data(texto):
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise argparse.ArgumentTypeError(f"\"{texto}\" não é uma data no formato AAAA-MM-DD") from None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Totais dos chamados do 1746 por rua e por quadrado de 100 m."
    )
    parser.add_argument("entrada", help="lista de chamados (CSV)")
    parser.add_argument("--saida", required=True, help="pasta onde gravar os arquivos")
    parser.add_argument(
        "--minimo", required=True, type=int,
        help="rua ou quadrado com menos chamados que isso sai como \"menos de N\"",
    )
    parser.add_argument("--inicio", type=_data, help="primeiro dia do período (AAAA-MM-DD)")
    parser.add_argument("--fim", type=_data, help="último dia do período (AAAA-MM-DD)")
    opcoes = parser.parse_args(argv)
    try:
        resumo = agregar(
            opcoes.entrada, opcoes.saida,
            minimo=opcoes.minimo, inicio=opcoes.inicio, fim=opcoes.fim,
        )
    except FileNotFoundError:
        print(f"ERRO: não achei o arquivo {opcoes.entrada}.", file=sys.stderr)
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
