---
name: operar-issue
description: Ciclo do operador para uma issue deste repositório, do branch ao pull request, com teste primeiro. Use quando o pedido for trabalhar numa issue (ex.: "vamos trabalhar na issue 12", "você é o operador da issue 12").
---

# Operar uma issue

Você é o operador desta issue. Não mude o escopo: dúvida vira comentário na issue, com a etiqueta `aguardando responsável`, e o gestor responde.

## Antes de começar

1. Leia a issue inteira, com os comentários. Se houver um comentário de quem tentou antes (nível, tentativa, erro, onde parou), comece por ele.
2. Num worktree novo (pasta própria do sub chat), crie o ambiente: `python -m venv .venv` e `.venv/Scripts/python -m pip install -r requirements.txt -r requirements-dev.txt` (no Mac, `.venv/bin/python`). A barreira local do git já vale aqui.
3. Branch com o número e um nome curto: `git switch -c issue-12-nome-curto`. Se a issue já tem branch, continue nele.

## Ciclo

1. **Teste primeiro.** De cada item do "Quando está pronta", escreva um teste em `testes/test_<ferramenta>.py`. Rode e veja falhar. Explique ao responsável, em linguagem simples, o que cada teste confere.
2. **Código.** Escreva em `src/` até os testes passarem. Se o teste está certo, quem muda é o código, não o teste. Biblioteca nova vai para o `requirements.txt`, com a versão fixa.
3. **O que não dá para testar automaticamente** (programa externo, tela, arquivo real) vira item do teste manual no pull request.
4. **Registros no mesmo branch:** `historico.md`, `map.md` (arquivo novo) e o checklist.
5. **Conferir:** `python verificacoes/verificar_tudo.py`. O push também roda isso e não sai com ERRO.
6. **Pull request** com o template, `Closes #12` (em inglês: o GitHub só fecha a issue no merge com `Closes`, `Fixes` ou `Resolves`). Na seção "Evidência", cole o comando que rodou e o final da saída. Conflito com a `main` no `historico.md` ou no `map.md`: traga a `main` para o branch e mantenha as linhas dos dois lados.
7. Avise o gestor com o link do pull request. O merge é do gestor, depois da revisão e do teste manual do responsável.

## Se falhar

Siga a escada de `docs/papeis_dos_chats.md` › Nível de esforço e falha. Ao sair, comente na issue: nível, tentativa, o que tentou, o erro e onde parou.
