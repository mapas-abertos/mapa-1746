# Mapa do repositório — Mapa 1746

> Índice de tudo que existe aqui. Arquivo ou pasta novo entra aqui; o CI confere nos dois sentidos.
>
> Como o CI lê este mapa: cada item é um caminho entre crases, na primeira coluna da tabela ou no começo de uma linha de lista, antes do travessão. O que vem depois do travessão é descrição. Vale coringa: `src/*.py` cobre todos os `.py` de `src/`. O que o `.gitignore` ignora (como o .env e a pasta dados/) não entra no mapa.

## Arquivos-padrão

| Arquivo | Responde | Quando ler |
|---|---|---|
| `README.md` | O que é este repositório, de onde vêm os dados e como começar? | Primeira visita, no GitHub |
| `LICENSE` | Licença MIT do código | Antes de reaproveitar o código |
| `SECURITY.md` | Como relatar uma falha de segurança em particular? | Ao achar uma falha |
| `CONTRIBUTING.md` | Como sugerir algo ou apontar erro no mapa, e que regras valem para quem é de fora? | Antes de abrir issue ou pull request |
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
- `.githooks/pre-commit` — barreira local: barra commit direto na `main` e segredos, antes de cada commit.
- `.githooks/pre-push` — roda o `verificar_tudo` antes de cada push.
- `.worktreeinclude` — o que o Claude Code copia para o worktree de cada sub chat (o `.env`).
- `.claude/settings.json` — permissões do Claude Code: libera os comandos de rotina, pede confirmação para push, merge e release, e bloqueia o `.env`, a `dados/` e o `--force`.
- `.claude/agents/revisor.md` — subagente revisor, só de leitura: compara o pull request com a issue.
- `.claude/skills/*/SKILL.md` — skills: `operar-issue`, `abrir-pedido`, `fim-de-sessao`, `atualizar-do-modelo` e `configurar-publico` (as duas últimas só o mentor dispara).

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
- `.claude/agents/` — subagentes.
- `.claude/skills/` e `.claude/skills/*/` — skills, uma pasta por procedimento.
- `.github/workflows/` — workflows do GitHub Actions.
- `.github/ISSUE_TEMPLATE/` — formulários de issue.
- `.github/rulesets/` — regras da `main` e das versões, como estão aplicadas aqui (skill `configurar-publico`).

## Arquivos

- `*/LEIA-ME.md` e `verificacoes/testes/LEIA-ME.md` — regras de cada pasta.
- `src/agregador.py` — agregador (issue #7): lê a lista de chamados e grava os totais por rua (`ruas.csv`) e por quadrado de 100 m (`quadrados.csv`, `quadrados.geojson`), com o resumo.
- `testes/test_agregador.py` — testes do agregador, com uma lista de chamados fictícia.
- `src/montar_site.py` — montador do site (issue #16): lê as saídas do agregador e grava o mapa, a página de método e as tabelas para baixar numa pasta que abre no computador.
- `testes/test_montar_site.py` — testes do montador do site, com os chamados fictícios do agregador.
- `src/coleta.py` — coleta (issue #15): soma no BigQuery os chamados por rua e por quadrado de 100 m e grava os arquivos do agregador, mais o desenho das ruas (`ruas.geojson`).
- `testes/test_coleta.py` — testes da coleta: as consultas rodam no DuckDB, com dados fictícios, e a conta de metros é conferida contra o pyproj.
- `docs/glossario.md` — os nomes em português para o Git e o GitHub, com o termo em inglês.
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
- `.github/workflows/publicar.yml` — Publicar versão (release): a pedido do responsável, confere a conferência automática, cria a versão, move a versão em uso (`prod`) e chama a entrega automática; também volta para uma versão anterior.
- `.github/workflows/deploy.yml` — ponto de encaixe do CD; destino a definir.
- `.github/workflows/dependencias.yml` — revisão de dependências a cada pull request: barra vulnerabilidade alta ou crítica e licença incompatível com a MIT.
- `.github/workflows/issue_fechada.yml` — quando uma issue fecha, tira `em andamento` e `aguardando responsável`.
- `.github/dependabot.yml` — pull request mensal com versão nova das actions e das bibliotecas fixadas.
- `.github/rulesets/*.json` — `proteger_main.json` (pull request e CI verde obrigatórios) e `proteger_versoes.json` (versões `v*` não se apagam) e `proteger_prod.json` (só a rotina de publicar mexe na `prod`).
- `.github/workflows/etiquetas.yml` — cria as etiquetas das issues e apaga as padrão; rodar à mão, uma vez.
- `.github/ISSUE_TEMPLATE/pedido_ferramenta.yml` — formulário "Pedido de ferramenta": o que faz, onde entra, quando está pronta.
- `.github/ISSUE_TEMPLATE/defeito.yml` — formulário "Defeito numa ferramenta": o que fez, o que deveria acontecer, o que aconteceu.
- `.github/ISSUE_TEMPLATE/tarefa.yml` — formulário "Tarefa de configuração ou documentação".
- `.github/ISSUE_TEMPLATE/externo.yml` — formulário "Sugestão ou erro (para quem é de fora)", sem marcar o mentor.
- `.github/ISSUE_TEMPLATE/suporte.yml` — formulário "Suporte do mentor", que marca o mentor.
- `.github/ISSUE_TEMPLATE/config.yml` — toda issue começa por um dos formulários.
- `.github/PULL_REQUEST_TEMPLATE.md` — checklist do teste manual e do merge.

## Status atual

- Ferramentas: agregador (issue #7), coleta no BigQuery (issue #15, na versão aprovada) e montador do site (issue #16, em revisão). Próximos: publicar o mapa (depois do OK do advogado) e o desenho das ruas.
