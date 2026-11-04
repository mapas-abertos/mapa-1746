# Mapa do repositório — a definir

> Índice de tudo que existe aqui. Arquivo ou pasta novo entra aqui; o CI confere nos dois sentidos.
>
> Como o CI lê este mapa: cada item é um caminho entre crases, na primeira coluna da tabela ou no começo de uma linha de lista, antes do travessão. O que vem depois do travessão é descrição. Vale coringa: `src/*.py` cobre todos os `.py` de `src/`. O que o `.gitignore` ignora (como o .env e a pasta dados/) não entra no mapa.

## Arquivos-padrão

| Arquivo | Responde | Quando ler |
|---|---|---|
| `README.md` | O que é este repositório e como começar? | Primeira visita, no GitHub |
| `CLAUDE.md` | O que vale sempre? | Toda sessão |
| `AGENTS.md` | Ponteiro para o `CLAUDE.md` (lido pelo Codex) | Não editar |
| `memory.md` | Como o responsável trabalha? Onde já erramos? | Antes de qualquer tarefa |
| `map.md` | O que existe aqui? | Para achar um arquivo |
| `Checklist_Projeto.md` | Em que pé está? | Ao planejar ou fechar uma tarefa |
| `decisoes.md` | Por que está assim? | Antes de mudar algo já decidido |
| `historico.md` | O que foi feito, e quando? | Por busca |
| `Backlog_Melhorias.md` | Que ideias estão para debate? | Ao surgir uma ideia |

## Configuração

- `.gitignore` — o que nunca vai para o GitHub (`.env`, `dados/`, arquivos temporários).
- `.env.example` — nomes das chaves que a ferramenta usa, sem os valores; modelo do `.env`.
- `pyproject.toml` — regras do lint (ruff) e onde ficam os testes (pytest).
- `requirements-dev.txt` — ferramentas das verificações, com a versão fixa.
- `requirements.txt` — bibliotecas que as ferramentas de `src/` usam, com a versão fixa.
- `.gitattributes` — fim de linha igual (LF) em todo computador e no GitHub.
- `.githooks/pre-commit` — barreira local: confere segredos antes de cada commit.
- `.claude/settings.json` — permissões do Claude Code: libera os comandos de rotina e bloqueia o `.env` e a `dados/`.

## Pastas

Cada pasta tem um `LEIA-ME.md` com as regras dela (menos as que começam com ponto).

- `_referencias/` — originais e insumos que explicam de onde veio o trabalho.
- `src/` — código das ferramentas.
- `testes/` — testes automáticos das ferramentas.
- `docs/` — guias para o responsável e para o Claude.
- `verificacoes/` — scripts da conferência automática (CI).
- `verificacoes/testes/` — testes dos scripts do CI.
- `.github/` — configuração do GitHub.
- `.githooks/` — ganchos do git (ligados com `git config core.hooksPath .githooks`).
- `.claude/` — configuração do Claude Code para este repositório.
- `.github/workflows/` — workflows do GitHub Actions.
- `.github/ISSUE_TEMPLATE/` — formulários de issue.

## Arquivos

- `*/LEIA-ME.md` e `verificacoes/testes/LEIA-ME.md` — regras de cada pasta.
- `src/exemplo.py` — ferramenta de exemplo (dias úteis entre duas datas); sai com a primeira ferramenta de verdade.
- `testes/test_exemplo.py` — testes da ferramenta de exemplo.
- `docs/como_usar_este_modelo.md` — passo a passo da primeira vez, do repositório vazio ao CI verde.
- `docs/atualizar_do_modelo.md` — como o mentor traz as melhorias do modelo P3 para este repositório, por pull request.
- `docs/papeis_dos_chats.md` — gestor (Opus) e operador (Sonnet, um sub chat por issue), com as frases de abertura.
- `docs/segredos_no_github.md` — onde guardar senhas e chaves, no computador e no GitHub, e o que fazer se vazar.
- `verificacoes/verificar_tudo.py` — roda todas as verificações; rodar antes de cada push.
- `verificacoes/documentos_ia.py` — tetos de palavras, histórico, checklist, mapa e `LEIA-ME`.
- `verificacoes/segredos.py` — barreira contra segredos e arquivos que não podem ir para o GitHub.
- `verificacoes/rodar_lint.py` — lint do Python com o ruff, com os erros comuns traduzidos.
- `verificacoes/rodar_testes.py` — código sem teste e testes com o pytest.
- `verificacoes/comum.py` — funções usadas pelas verificações.
- `verificacoes/testes/test_verificacoes.py` — um caso que passa e casos que falham para cada verificação.
- `.github/workflows/ci.yml` — CI: documentos de IA e código, a cada pull request e na `main`.
- `.github/workflows/versao.yml` — depois do CI verde na `main`, cria a tag com a data e o Release e chama o deploy.
- `.github/workflows/deploy.yml` — ponto de encaixe do CD; destino a definir.
- `.github/workflows/etiquetas.yml` — cria as etiquetas das issues e apaga as padrão; rodar à mão, uma vez.
- `.github/ISSUE_TEMPLATE/pedido_ferramenta.yml` — formulário "Pedido de ferramenta": o que faz, onde entra, quando está pronta.
- `.github/ISSUE_TEMPLATE/defeito.yml` — formulário "Defeito numa ferramenta": o que fez, o que deveria acontecer, o que aconteceu.
- `.github/ISSUE_TEMPLATE/suporte.yml` — formulário "Suporte do mentor", que marca o mentor.
- `.github/ISSUE_TEMPLATE/config.yml` — toda issue começa por um dos três formulários.
- `.github/PULL_REQUEST_TEMPLATE.md` — checklist do teste manual e do merge.

## Status atual

- Primeira ferramenta: a definir.
