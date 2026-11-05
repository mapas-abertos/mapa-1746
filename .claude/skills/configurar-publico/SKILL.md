---
name: configurar-publico
description: Configura a segurança e a proteção de um repositório público criado do modelo P3 (regra da main, versões, aprovação de PR de fora, varredura de segredos). Só o mentor dispara, com /configurar-publico.
disable-model-invocation: true
---

# Configurar repositório público

Rode só em repositório **público**. Antes de cada comando que muda o GitHub, mostre o comando e peça o OK do mentor. `R` é o repositório (`dono/nome`).

## Antes

1. Confira: `gh repo view R --json visibility` mostra `PUBLIC`.
2. O mentor liga o **Dependency graph** pela tela (Settings › Code security › Dependency graph). Não há API para isso, e sem ele a revisão de dependências falha com "Dependency review is not supported".
3. A preparação do repositório já entrou na `main` por pull request, com o CI verde (assim os checks exigidos já existem com estes nomes).

## Passos, nesta ordem (foi a que funcionou)

1. Regra da `main`, sem exceção para admin e com 0 aprovações (ninguém aprova o próprio pull request):
   `gh api -X POST repos/R/rulesets --input .github/rulesets/proteger_main.json`
2. Pull request de quem é de fora só roda o CI depois de aprovado:
   `gh api -X PUT repos/R/actions/permissions/fork-pr-contributor-approval -f approval_policy=all_external_contributors`
3. Varredura de segredos com bloqueio no push:
   `gh api -X PATCH repos/R --input -` com `{"security_and_analysis": {"secret_scanning": {"status": "enabled"}, "secret_scanning_push_protection": {"status": "enabled"}}}`
4. Relato privado de falha (o botão do `SECURITY.md`):
   `gh api -X PUT repos/R/private-vulnerability-reporting`
5. Alertas e correções do Dependabot:
   `gh api -X PUT repos/R/vulnerability-alerts` e `gh api -X PUT repos/R/automated-security-fixes`
6. CodeQL padrão:
   `gh api -X PATCH repos/R/code-scanning/default-setup -f state=configured`
7. Regra das versões (ninguém apaga nem reescreve uma tag `v*`; a rotina Publicar versão continua criando):
   `gh api -X POST repos/R/rulesets --input .github/rulesets/proteger_versoes.json`
8. Aprovação do responsável para publicar: ambiente `prod`, que só a `main` usa e que pede a aprovação dele (`ID` = `gh api users/<usuário do responsável> --jq .id`):
   `gh api -X PUT repos/R/environments/prod --input -` com `{"reviewers": [{"type": "User", "id": ID}], "prevent_self_review": false, "deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}`
   e `gh api -X POST repos/R/environments/prod/deployment-branch-policies -f name=main`
9. Regra da versão em uso (só a rotina Publicar versão mexe na `prod`):
   `gh api -X POST repos/R/rulesets --input .github/rulesets/proteger_prod.json`
   A conferir no primeiro projeto: se a rotina for barrada ao mover a `prod`, a liberação para o GitHub Actions no arquivo (`bypass_actors`) não valeu; tire a regra (`gh api -X DELETE repos/R/rulesets/<id>`) e fique com as travas do computador e a aprovação do passo 8.
10. Opcional, com o OK do mentor: desligar Wiki e Projects (`gh repo edit R --enable-wiki=false --enable-projects=false`) e pôr tópicos.

## Depois

- Mostre ao mentor o resultado de `gh api repos/R/rulesets` e de `gh api repos/R --jq .security_and_analysis`.
- Registre no `historico.md` e marque o item no checklist.
- Lembre: em repositório público, workflow agendado (`schedule`) pausa sozinho depois de 60 dias sem atividade no repositório.
