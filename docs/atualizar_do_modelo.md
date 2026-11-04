# Atualizar a partir do modelo

O repositório nasceu de uma cópia do modelo P3 (`guilobocarvalho/mentoria-p3-modelo`). Quando o modelo melhora, a melhoria chega aqui por um pull request, sem tocar no que é do projeto.

**Quem faz:** o mentor, que tem acesso ao modelo (ele é privado) e é membro da organização. O responsável aprova o pull request como qualquer outro.

## O que vem do modelo e o que é do projeto

| Vem do modelo (a atualização traz) | É do projeto (a atualização não mexe) |
|---|---|
| `verificacoes/`, `.github/`, `.githooks/`, `.claude/` | `CLAUDE.md`, `memory.md`, `map.md`, `historico.md`, `decisoes.md`, `Checklist_Projeto.md`, `Backlog_Melhorias.md`, `README.md` |
| `docs/como_usar_este_modelo.md`, `docs/segredos_no_github.md`, `docs/papeis_dos_chats.md`, `docs/atualizar_do_modelo.md` | `src/`, `testes/`, `_referencias/`, `requirements.txt`, `.env.example` e os outros guias de `docs/` |
| `pyproject.toml`, `requirements-dev.txt`, `.gitignore`, `.gitattributes` | |

Se o projeto mudou um arquivo da coluna da esquerda, a atualização tenta juntar as duas mudanças; o que não juntar sozinho aparece como conflito, para resolver no pull request.

Se o modelo mudou uma regra no `CLAUDE.md` dele, ela não vem sozinha: o mentor lê a mudança no modelo e propõe só as linhas novas, no mesmo pull request.

## Passo a passo

A versão de origem fica no `Checklist_Projeto.md` › Dados-chave › "Modelo de origem". A versão nova é a mais recente em **Releases** do modelo.

No clone do repositório do projeto, com o Claude Code:

1. Trazer as versões do modelo, num lugar separado das versões do projeto (as duas usam nomes como `v2026.11.04`; misturar daria confusão e um `git push --tags` mandaria as do modelo para o projeto):
   - `git remote add --no-tags modelo https://github.com/guilobocarvalho/mentoria-p3-modelo.git` (só da primeira vez)
   - `git fetch --no-tags modelo "+refs/tags/*:refs/modelo/*"`
2. Criar o branch: `git switch -c modelo-<versão nova>` a partir da `main` atualizada.
3. Aplicar só o que mudou no modelo entre as duas versões, nas partes que vêm do modelo:

   ```
   git diff refs/modelo/<versão de origem> refs/modelo/<versão nova> -- verificacoes .github .githooks .claude docs/como_usar_este_modelo.md docs/segredos_no_github.md docs/papeis_dos_chats.md docs/atualizar_do_modelo.md pyproject.toml requirements-dev.txt .gitignore .gitattributes | git apply --3way
   ```

4. Arquivo novo do modelo: acrescentar no `map.md` (o `verificar_tudo` acusa o que faltar). Rodar `python verificacoes/verificar_tudo.py`.
5. Atualizar "Modelo de origem" no checklist para a versão nova e registrar no `historico.md`.
6. Pull request "Atualiza do modelo <origem> para <nova>", com o link dos Releases do modelo entre as duas versões. Com o CI verde e o OK do responsável, merge.
