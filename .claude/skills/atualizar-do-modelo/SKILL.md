---
name: atualizar-do-modelo
description: Traz para este repositório as melhorias de uma versão nova do modelo P3, por pull request. Só o mentor dispara, com /atualizar-do-modelo.
disable-model-invocation: true
---

# Atualizar a partir do modelo

Siga `docs/atualizar_do_modelo.md` passo a passo. Antes de aplicar, mostre ao mentor:

1. a versão de origem (`Checklist_Projeto.md` › Dados-chave › "Modelo de origem") e a versão nova (Releases de `guilobocarvalho/mentoria-p3-modelo`);
2. a lista de arquivos que vão mudar, separando o que vem do modelo do que é do projeto;
3. as regras novas do `CLAUDE.md` do modelo que valeria trazer, linha a linha, para o mentor escolher.

Depois de aplicar, rode `python verificacoes/verificar_tudo.py` e abra o pull request "Atualiza do modelo <origem> para <nova>".
