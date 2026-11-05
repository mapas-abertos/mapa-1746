"""Testes das próprias verificações: para cada uma, um caso que passa e casos que falham.

Cada teste monta um repositório pequeno numa pasta temporária, com git, e roda a
verificação nele. Nada do repositório de verdade é alterado.
"""

import importlib.util
import os
import subprocess
from datetime import date
from pathlib import Path

import pytest

import documentos_ia
import rodar_lint
import rodar_testes
import segredos

HOJE = date(2026, 11, 4)

MAPA = """# Mapa

| Arquivo | Para que serve |
|---|---|
| `CLAUDE.md` | regras |
| `memory.md` | memória |
| `map.md` | este mapa |
| `historico.md` | histórico |
| `decisoes.md` | decisões |
| `Checklist_Projeto.md` | andamento |
| `Backlog_Melhorias.md` | ideias |

- `src/` — código
- `src/LEIA-ME.md` e `src/*.py` — regras da pasta e ferramentas
- `_referencias/` — originais
- `_referencias/LEIA-ME.md` — regras da pasta (o `.env` nunca entra: é só descrição)
"""

BASE = {
    "CLAUDE.md": "regras do projeto",
    "memory.md": "memória",
    "map.md": MAPA,
    "historico.md": "# Histórico\n\n## 2026-11-04\n\n- feito\n\n## 2026-11-01\n\n- feito antes\n",
    "decisoes.md": "# Decisões\n",
    "Checklist_Projeto.md": "# Checklist\n\n**Última atualização:** 2026-11-04\n",
    "Backlog_Melhorias.md": "# Backlog\n",
    "src/LEIA-ME.md": "código",
    "src/ferramenta.py": "def dobro(x):\n    return 2 * x\n",
    "_referencias/LEIA-ME.md": "originais",
}


def montar_repo(pasta):
    """Monta em `pasta` o repositório mínimo que passa em todas as verificações."""
    for caminho, texto in BASE.items():
        arquivo = pasta / caminho
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(texto, encoding="utf-8")
    # Sem as variáveis GIT_* herdadas (a trava do envio as recebe do git): com elas, o
    # git init reinicializaria o repositório de verdade, e não este de teste.
    sem_git = {nome: valor for nome, valor in os.environ.items() if not nome.startswith("GIT_")}
    subprocess.run(
        ["git", "init", "-q"], cwd=pasta, check=True, stdin=subprocess.DEVNULL, capture_output=True,
        env=sem_git,
    )
    return pasta


@pytest.fixture
def repo(tmp_path):
    """Repositório mínimo que passa em todas as verificações."""
    return montar_repo(tmp_path)


def escrever(repo, caminho, texto):
    arquivo = repo / caminho
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(texto, encoding="utf-8")


def tem_erro(erros, trecho):
    return any(trecho in erro for erro in erros)


# ---- Documentos de IA ----


def test_documentos_passa_no_repositorio_certo(repo):
    assert documentos_ia.verificar(repo, HOJE) == []


def test_documentos_falha_com_claude_md_acima_do_limite(repo):
    escrever(repo, "CLAUDE.md", "palavra " * 1501)
    assert tem_erro(documentos_ia.verificar(repo, HOJE), "CLAUDE.md tem 1501 palavras")


def test_documentos_falha_com_memory_md_acima_do_limite(repo):
    escrever(repo, "memory.md", "palavra " * 601)
    assert tem_erro(documentos_ia.verificar(repo, HOJE), "memory.md tem 601 palavras")


def test_documentos_falha_com_historico_fora_de_ordem(repo):
    escrever(repo, "historico.md", "## 2026-11-01\n\n- a\n\n## 2026-11-04\n\n- b\n")
    assert tem_erro(documentos_ia.verificar(repo, HOJE), "a entrada mais recente fica no topo")


def test_documentos_falha_com_titulo_sem_data_no_historico(repo):
    escrever(repo, "historico.md", "## 2026-11-04\n\n- a\n\n## semana passada\n\n- b\n")
    assert tem_erro(documentos_ia.verificar(repo, HOJE), "não começa com uma data válida")


def test_documentos_falha_com_data_inexistente_no_historico(repo):
    escrever(repo, "historico.md", "## 2026-02-30\n\n- a\n")
    assert tem_erro(documentos_ia.verificar(repo, HOJE), "não começa com uma data válida")


def test_documentos_falha_com_data_repetida_no_historico(repo):
    escrever(repo, "historico.md", "## 2026-11-04\n\n- a\n\n## 2026-11-04\n\n- b\n")
    assert tem_erro(documentos_ia.verificar(repo, HOJE), "aparece duas vezes")


def test_documentos_falha_com_checklist_sem_data_valida(repo):
    escrever(repo, "Checklist_Projeto.md", "**Última atualização:** a definir\n")
    assert tem_erro(documentos_ia.verificar(repo, HOJE), "não é uma data válida")


def test_documentos_falha_com_checklist_no_futuro(repo):
    escrever(repo, "Checklist_Projeto.md", "**Última atualização:** 2026-12-25\n")
    assert tem_erro(documentos_ia.verificar(repo, HOJE), "está no futuro")


def test_documentos_falha_com_checklist_mais_velho_que_o_historico(repo):
    escrever(repo, "Checklist_Projeto.md", "**Última atualização:** 2026-11-02\n")
    assert tem_erro(documentos_ia.verificar(repo, HOJE), "anterior à entrada mais recente")


def test_documentos_falha_com_arquivo_fora_do_mapa(repo):
    escrever(repo, "notas.txt", "solto")
    assert tem_erro(documentos_ia.verificar(repo, HOJE), "`notas.txt` não aparece no map.md")


def test_documentos_falha_com_item_do_mapa_que_nao_existe(repo):
    escrever(repo, "map.md", MAPA + "- `docs/guia.md` — guia\n")
    assert tem_erro(documentos_ia.verificar(repo, HOJE), "`docs/guia.md` está no mapa mas não existe")


def test_documentos_falha_com_pasta_sem_leia_me(repo):
    escrever(repo, "testes/test_a.py", "")
    escrever(repo, "map.md", MAPA + "- `testes/` — testes\n- `testes/test_a.py` — teste\n")
    assert tem_erro(documentos_ia.verificar(repo, HOJE), "`testes/` não tem LEIA-ME.md")


def test_documentos_pasta_com_ponto_nao_precisa_de_leia_me(repo):
    escrever(repo, ".github/workflows/ci.yml", "name: CI\n")
    escrever(repo, "map.md", MAPA + "- `.github/` e `.github/workflows/` — GitHub\n- `.github/workflows/*.yml` — CI\n")
    assert documentos_ia.verificar(repo, HOJE) == []


def test_documentos_arquivo_ignorado_pelo_git_nao_precisa_estar_no_mapa(repo):
    escrever(repo, ".gitignore", "dados/\n")
    escrever(repo, "dados/cliente.txt", "dado real")
    escrever(repo, "map.md", MAPA + "- `.gitignore` — o que não vai para o GitHub\n")
    assert documentos_ia.verificar(repo, HOJE) == []


def test_documentos_pasta_coberta_por_coringa(repo):
    escrever(repo, "docs/a/LEIA-ME.md", "a")
    escrever(repo, "docs/b/LEIA-ME.md", "b")
    escrever(repo, "docs/LEIA-ME.md", "docs")
    extra = "- `docs/` e `docs/*/` — guias\n- `docs/LEIA-ME.md` e `docs/*/LEIA-ME.md` — regras\n"
    escrever(repo, "map.md", MAPA + extra)
    assert documentos_ia.verificar(repo, HOJE) == []


# ---- Segredos ----


def test_segredos_passa_no_repositorio_certo(repo):
    assert segredos.verificar(repo) == []


def test_segredos_falha_com_arquivo_env(repo):
    escrever(repo, ".env", "CHAVE=123")
    assert tem_erro(segredos.verificar(repo), ".env: arquivo de segredo")


def test_segredos_env_example_pode_entrar(repo):
    escrever(repo, ".env.example", "CHAVE=\n")
    assert segredos.verificar(repo) == []


def test_segredos_falha_com_chave_privada(repo):
    escrever(repo, "acesso.pem", "conteúdo")
    assert tem_erro(segredos.verificar(repo), "acesso.pem: arquivo de segredo")


def test_segredos_falha_com_planilha_fora_de_referencias(repo):
    escrever(repo, "src/clientes.xlsx", "dados")
    assert tem_erro(segredos.verificar(repo), "src/clientes.xlsx: arquivo de dados fora de _referencias/")


def test_segredos_planilha_em_referencias_pode_entrar(repo):
    escrever(repo, "_referencias/norma.pdf", "original")
    assert segredos.verificar(repo) == []


def test_segredos_falha_com_arquivo_grande(repo):
    (repo / "src" / "grande.bin").write_bytes(b"x" * (segredos.TAMANHO_MAXIMO_MB * 1024 * 1024 + 1))
    assert tem_erro(segredos.verificar(repo), "o limite é 5 MB")


def test_segredos_falha_com_token_do_github_no_codigo(repo):
    token = "ghp_" + "a1B2" * 9  # montado em partes para este arquivo não ser barrado
    escrever(repo, "src/ferramenta.py", f'TOKEN_GH = "{token}"\n')
    assert tem_erro(segredos.verificar(repo), "token do GitHub")


def test_segredos_falha_com_chave_da_anthropic_no_codigo(repo):
    chave = "sk-" + "ant-" + "x" * 30
    escrever(repo, "src/ferramenta.py", f'CHAVE_CLAUDE = "{chave}"\n')
    assert tem_erro(segredos.verificar(repo), "chave da Anthropic")


def test_segredos_falha_com_senha_escrita_no_codigo(repo):
    escrever(repo, "src/ferramenta.py", 'senha = "' + "minhasenha123" + '"\n')
    assert tem_erro(segredos.verificar(repo), "senha ou chave escrita no código")


def test_segredos_linha_liberada_passa(repo):
    linha = 'senha = "' + "nao_e_real_123" + '"  # nao-e-segredo: valor de teste\n'
    escrever(repo, "src/ferramenta.py", linha)
    assert segredos.verificar(repo) == []


def test_segredos_ler_do_ambiente_passa(repo):
    escrever(repo, "src/ferramenta.py", 'import os\nchave = os.environ["MINHA_CHAVE"]\n')
    assert segredos.verificar(repo) == []


# ---- Lint ----

precisa_do_ruff = pytest.mark.skipif(
    importlib.util.find_spec("ruff") is None,
    reason="ruff não instalado (pip install -r requirements-dev.txt)",
)


@precisa_do_ruff
def test_lint_passa_com_codigo_limpo(repo):
    assert rodar_lint.verificar(repo) == []


@precisa_do_ruff
def test_lint_falha_com_import_sem_uso_e_traduz(repo):
    escrever(repo, "src/ferramenta.py", "import os\n\n\ndef dobro(x):\n    return 2 * x\n")
    erros = rodar_lint.verificar(repo)
    assert tem_erro(erros, "src/ferramenta.py, linha 1: import que não é usado")


# ---- Testes automáticos ----


def test_testes_falha_com_codigo_sem_teste(repo):
    arquivos = ["src/ferramenta.py", "src/LEIA-ME.md"]
    assert tem_erro(rodar_testes.falta_teste(arquivos), "nenhum teste em testes/")


def test_testes_passa_com_codigo_e_teste(repo):
    arquivos = ["src/ferramenta.py", "testes/test_ferramenta.py"]
    assert rodar_testes.falta_teste(arquivos) == []


# ---- Trava do envio (issue #20) ----
# Dentro da trava, o git passa o endereço do repositório de verdade (GIT_DIR). Um git init
# de teste que herde esse endereço reinicializa o repositório de verdade (core.bare = true).

RAIZ = Path(__file__).resolve().parents[2]


def test_repositorio_de_teste_nao_toca_outro_repositorio(tmp_path, monkeypatch):
    outro = tmp_path / "outro"
    outro.mkdir()
    subprocess.run(["git", "init", "-q", str(outro)], check=True, stdin=subprocess.DEVNULL,
                   capture_output=True, env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")})
    config_antes = (outro / ".git" / "config").read_text(encoding="utf-8")
    monkeypatch.setenv("GIT_DIR", str(outro / ".git"))
    novo = tmp_path / "novo"
    novo.mkdir()
    montar_repo(novo)
    assert (novo / ".git").is_dir()
    assert (outro / ".git" / "config").read_text(encoding="utf-8") == config_antes


def test_trava_do_envio_limpa_o_endereco_do_git_antes_das_verificacoes():
    trava = (RAIZ / ".githooks" / "pre-push").read_text(encoding="utf-8")
    assert "unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE" in trava
    assert trava.index("unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE") < trava.index("verificar_tudo.py")
