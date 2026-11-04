# Backlog de Melhorias — Mapa 1746

Ideias de melhoria para debater. Não implementar sem aprovação; só registrar.
Status: `proposta` → `aprovada` → `feita` (ou `descartada`). Decisão tomada → registrar também em `decisoes.md`.

Ideia de ferramenta nova não entra aqui: vira issue "Pedido de ferramenta".

Melhoria do próprio modelo (CI, regras, guias, templates), percebida no uso: registre aqui com a origem "modelo P3" e a data. O mentor revisa essas linhas e leva o que valer para o modelo, de onde todos os repositórios se beneficiam.

| # | Ideia | Origem | Status | Decisão / Notas |
|---|---|---|---|---|
| 1 | Falta uma variante "repositório público" do modelo. Hoje supõem privado: `CLAUDE.md` (regra 6), comentários do `ci.yml` e do `versao.yml`, a decisão "O CI não impede o merge", `docs/segredos_no_github.md` (diz que não há environments), `_referencias/LEIA-ME.md`, o passo 1.2 do guia e o 1º item do checklist. | modelo P3, 04/11/2026 | proposta | Aqui foi corrigido à mão, arquivo por arquivo (ver `decisoes.md`). |
| 2 | O guia `docs/como_usar_este_modelo.md` não tem os passos de repositório público: ruleset na `main` (pull request e checks "Documentos de IA" e "Código"), aprovação para workflows de colaboradores externos, secret scanning com push protection, private vulnerability reporting. Nem diz que a proteção só pode ser ligada depois do commit de preparação, que vai direto na `main`. | modelo P3, 04/11/2026 | proposta | Aqui feito por `gh api`, na ordem: push de preparação, depois o ruleset. |
| 3 | Os formulários de issue supõem só responsável e mentor. Em repositório público qualquer pessoa abre issue: "Suporte do mentor" atribui o mentor à issue de um estranho, a etiqueta diz "o mentor é avisado", os avisos falam de "dado real de cliente" e não de dado pessoal, e falta um caminho para quem é de fora (sugestão, erro no mapa) e um `SECURITY.md`. | modelo P3, 04/11/2026 | proposta | Não mexido aqui. |
| 4 | Não há formulário de issue para tarefa de configuração ou documentação (como estes ajustes de repositório público), embora o `CLAUDE.md` diga que todo trabalho começa numa issue. | modelo P3, 04/11/2026 | proposta | Aqui a issue foi aberta sem formulário, pelo `gh`. |
| 5 | O `README.md` do modelo cita a mentoria e a empresa e oferece "Suporte do mentor ... em até 24 horas": num repositório público, o visitante lê isso como canal de atendimento do projeto. | modelo P3, 04/11/2026 | proposta | O responsável decidiu manter a linha da mentoria por ora. |
| 6 | O modelo supõe responsável e mentor como pessoas diferentes (assignee do suporte, itens "resp.: mentor", revisão). Aqui são o mesmo usuário, e o ruleset não pode exigir aprovação: o GitHub não deixa aprovar o próprio pull request. | modelo P3, 04/11/2026 | proposta | Registrado em Dados-chave e em `decisoes.md`. |
| 7 | Criar o repositório pelo template já dispara CI e Versão no commit inicial: nasce a tag `v2026.11.04` "Initial commit" antes da preparação, e o guia (passo 5.3) diz que a primeira tag sai depois do push de preparação. Aqui a preparação virou `v2026.11.04.2`. | modelo P3, 04/11/2026 | proposta | Sem efeito prático; só confunde a leitura dos Releases. |
| 8 | O modelo é privado, mas um repositório público criado dele publica todo o conteúdo do modelo (guias, verificações, decisões). Vale decidir se o modelo aceita isso ou se a variante pública deve ser outra. | modelo P3, 04/11/2026 | proposta | — |
| 9 | Em repositório público o Dependabot é grátis, mas o modelo não traz `.github/dependabot.yml` para manter atualizadas as actions (`checkout`, `setup-python`) e as bibliotecas fixadas. | modelo P3, 04/11/2026 | proposta | Aqui só os alertas foram ligados. |
