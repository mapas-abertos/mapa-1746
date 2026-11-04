# Histórico — Mapa 1746

> Log do que foi feito, por data, mais recente no topo. O porquê das escolhas fica no `decisoes.md`.
>
> Cada data é um título `## AAAA-MM-DD`. O CI confere a data e a ordem.

## 2026-11-04

- Issue #3: `SECURITY.md` (relato em particular pelo "Report a vulnerability"), `CONTRIBUTING.md` (como sugerir ou apontar erro no mapa e as regras públicas) e workflow "Dependências" (`.github/workflows/dependencias.yml`), que barra no pull request vulnerabilidade alta ou crítica e licença GPL, AGPL ou SSPL. O check ainda não é obrigatório na regra da `main`: decisão pendente no checklist.
- Ajustes de repositório público: regra da `main` exigindo pull request e o CI verde, aprovação para workflows de colaboradores externos, secret scanning com push protection, Dependabot e private vulnerability reporting ligados; regras de dado público agregado, neutralidade e logs públicos no `CLAUDE.md` e no `_referencias/LEIA-ME.md`; trechos de "repositório privado" corrigidos; `LICENSE` MIT e seção "Fonte dos dados" no `README.md`; deploy no GitHub Pages e credencial do BigQuery registrados como pendentes. Depois: CodeQL, pull request de correção do Dependabot, proteção das tags de versão e tópicos ligados; Wiki e Projects desligados.
- Projeto preenchido: nome Mapa 1746, descrição, responsável, início, critério de conclusão e escopo "Dentro" ("Fora" e prazo a definir).
- Preparação do repositório (`docs/como_usar_este_modelo.md`): modelo de origem `v2026.11.04.4` e organização `mapas-abertos` nos Dados-chave, etiquetas criadas pelo workflow, apagar branch depois do merge ligado, `.venv` criada, barreira local ligada, bibliotecas instaladas e `verificar_tudo` sem erro. Autor dos commits deste clone: `guilobocarvalho`.
- Repositório criado a partir do modelo P3 da mentoria de IA: documentos de IA, verificações do CI, templates de issue e de pull request, papéis dos chats (gestor e operador, com subagente como plano B), regras e etiquetas das issues, nível de esforço e escada de falha, barreira local de segredos, `.venv` e `requirements.txt`, permissões do Claude Code, fim de linha LF, caminho para desfazer uma versão, atualização a partir do modelo por pull request, versão automática e ponto de encaixe do deploy.
