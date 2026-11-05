# Como usar este modelo

Passo a passo da primeira vez, da organização criada até a conferência automática (CI) verde. O passo 1 é do mentor; do 2 em diante, você e o Claude Code fazem juntos: o Claude roda os comandos, você confere e aprova. Os nomes seguem o `glossario.md`, nesta pasta; os nomes em **negrito** e em inglês são os que aparecem na tela do GitHub.

## Antes de começar

- Conta pessoal no GitHub, com o seu usuário enviado ao mentor.
- No computador: Git, Python 3.12 ou mais novo e o Claude Code no app do Claude.

## 1. Organização e projeto no GitHub (o mentor faz)

1. O mentor cria uma organização no plano Free, com o nome que você escolher, e convida você como dono (**Owner**). Aceite o convite, que chega por e-mail ou em https://github.com/notifications.
2. O mentor cria o seu projeto no GitHub (repository) dentro da organização a partir do modelo (template) `guilobocarvalho/mentoria-p3-modelo` (**Use this template › Create a new repository**), privado (**Private**) ou, se o projeto for aberto, público (ver "Se o projeto for público"), com nome sem espaço e sem acento (`ferramentas-medicao`). O projeto já vem com todos os arquivos do modelo, sem o histórico dele.
3. O mentor roda a rotina automática (workflow) **Etiquetas** no projeto novo (Actions › Etiquetas › Run workflow): ela cria as etiquetas (labels) dos chamados e apaga as padrão do GitHub.
4. O mentor registra no `Checklist_Projeto.md` › Dados-chave a versão do modelo usada na cópia (a mais recente em **Releases** do modelo). É dela que partem as atualizações (ver `atualizar_do_modelo.md`).
5. O mentor liga, no projeto novo, **Settings › General › Automatically delete head branches** (apaga a linha de trabalho depois de juntar à versão aprovada). O modelo não copia as configurações.
6. O mentor fica como membro da organização durante a mentoria; é assim que o chamado de suporte chega a ele. No fim, você decide se ele sai.

## 2. Trazer para o computador

1. Crie a pasta `C:\repos\` (no Mac, `~/repos/`). Se a TI não deixar criar pasta direto no `C:\`, use `C:\Users\<seu usuário>\repos\`.
2. Peça ao Claude Code: "faça a cópia no computador (clone) do projeto <endereço> em C:\repos".
3. Não use pasta sincronizada com OneDrive, Google Drive ou SharePoint: a sincronização pode estragar a pasta `.git`. O GitHub já é o backup.
4. Peça ao Claude: "crie a .venv e ligue as travas do computador". Ele roda, dentro da pasta do projeto:
   - `python -m venv .venv` (o ambiente do Python só deste projeto; fica no seu computador);
   - `git config core.hooksPath .githooks` (as travas do computador, ou hooks: antes de salvar etapa, barram salvar direto na versão aprovada e segredos; antes de enviar para a nuvem, rodam o `verificar_tudo`).

## 3. Preencher o projeto

1. Peça ao Claude: "leia o CLAUDE.md e me ajude a preencher o projeto". Ele preenche nome, critério de conclusão e escopo com você e troca "a definir" nos títulos dos documentos.
2. Os arquivos que começam com ponto (`.github/`, `.gitignore`, `.env.example`) fazem parte do modelo. No Windows eles podem ficar ocultos: no Explorador de Arquivos, **Exibir › Mostrar › Itens ocultos**.

## 4. Conferir as etiquetas

Em **Issues › Labels**, devem aparecer `pedido`, `defeito`, `tarefa`, `externo`, `suporte`, `em andamento` e `aguardando responsável`. Não apareceram? Peça ao mentor para rodar a rotina **Etiquetas**. O que cada uma quer dizer está em `papeis_dos_chats.md`, nesta pasta.

## 5. Primeira verificação

1. Peça ao Claude: "instale as bibliotecas e rode o verificar_tudo". Ele roda, com o Python da `.venv`:
   - `pip install -r requirements.txt -r requirements-dev.txt`
   - `python verificacoes/verificar_tudo.py`
2. Tudo OK → peça ao Claude para salvar a preparação (commit) numa linha de trabalho (branch) `preparacao` e abrir o pedido de revisão (pull request). Até a preparação passa por pedido de revisão: a trava do computador barra salvar etapa direto na versão aprovada (`main`).
3. Com a conferência automática verde no pedido de revisão, peça para juntar à versão aprovada (merge). Nada vai para uso ainda: isso é publicar (ver "Publicar uma versão").

## 6. Primeira ferramenta

1. Abra um chamado (issue) **Pedido de ferramenta**.
2. Peça ao Claude: "vamos trabalhar no chamado <número>". Ele cria a linha de trabalho, escreve o teste, mostra o que o teste confere e só então escreve o código.
3. No pedido de revisão, faça o teste manual e marque o checklist. Com a conferência automática verde, peça para juntar à versão aprovada.
4. A ferramenta de exemplo (`src/exemplo.py` e `testes/test_exemplo.py`) pode sair nesse primeiro pedido de revisão.
5. Quando quiser pôr em uso, peça para publicar (ver abaixo).

## Publicar uma versão

Juntar à versão aprovada (`main`) não põe nada em uso. Publicar (release) é um passo separado, e quem decide é você.

1. Peça ao Claude: "publique a versão". Ele pede a sua confirmação e roda a rotina **Publicar versão (release)**. Você também pode rodar pela tela: **Actions › Publicar versão (release) › Run workflow**, com o campo vazio.
2. A rotina confere a conferência automática da versão aprovada, cria a versão com a data (ex.: `v2026.11.05`) e as notas do que entrou desde a última, move a versão em uso (`prod`) e chama a entrega automática.
3. Em projeto público, o GitHub pede a sua aprovação antes de publicar (ambiente `prod`).

A versão em uso (`prod`) só se mexe por essa rotina: as travas do computador barram salvar etapa ou enviar direto para ela.

## Se o projeto for público

Tudo fica visível para qualquer pessoa: código, chamados, pedidos de revisão e registros das rotinas automáticas (logs do Actions). O modelo já traz o `SECURITY.md`, o `CONTRIBUTING.md`, o formulário "Sugestão ou erro (para quem é de fora)" e a revisão de dependências, que só roda em público. A ordem que funcionou:

1. O mentor cria o projeto pelo modelo como **Public** (passo 1).
2. Logo em seguida, o mentor liga o **Dependency graph** pela tela (Settings › Code security). Sem ele, a revisão de dependências falha em todo pedido de revisão.
3. Passos 2 a 5 como no privado, com a preparação entrando por pedido de revisão.
4. Depois de juntar a preparação, o mentor roda `/configurar-publico`: regras de proteção (rulesets) da versão aprovada, da versão em uso e das versões, aprovação do responsável para publicar, aprovação para a conferência automática de pedido de revisão de quem é de fora, varredura de segredos, relato privado de falha, Dependabot e CodeQL.
5. A partir daí, a versão aprovada só aceita pedido de revisão com a conferência automática verde, inclusive para o próprio mentor.

Também vale saber: o conteúdo do modelo (guias, regras) fica público junto; credencial que dá acesso a dados vai num ambiente (environment) restrito à versão aprovada (ver `segredos_no_github.md`); e rotina agendada pausa depois de 60 dias sem atividade no projeto.

## Se responsável e mentor forem a mesma pessoa

Acontece quando o mentor usa o modelo num projeto próprio. Nada quebra, mas três coisas mudam:

- **Suporte:** o formulário "Suporte do mentor" atribui o chamado a você mesmo. Use-o para registrar o que travou; a resposta é sua.
- **Revisão:** o GitHub não deixa aprovar o próprio pedido de revisão. A revisão continua com o subagente `revisor`, e, se houver regra de proteção da versão aprovada (projeto público), ela fica com 0 aprovações.
- **Checklist:** itens "_resp.: mentor_" e "_resp.: a definir_" são todos seus.

## Se uma versão saiu com problema

1. Abra um chamado **Defeito numa ferramenta** dizendo qual versão (página **Releases**).
2. **Voltar a versão em uso, na hora:** peça ao Claude "volte para a versão v2026.11.04" (ou rode **Publicar versão (release)** com o nome dela no campo). A versão em uso (`prod`) volta para ela e a entrega automática leva essa versão.
3. **Corrigir de vez:** no pedido de revisão que trouxe o problema, o botão **Revert** abre um pedido de revisão que desfaz a mudança. Depois de juntar à versão aprovada, publique de novo.

## Se precisar de senha ou chave

Ver `segredos_no_github.md`, nesta pasta.
