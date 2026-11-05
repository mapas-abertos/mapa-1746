# Como usar este modelo

Passo a passo da primeira vez, da organização criada ao CI verde. O passo 1 é do mentor; do 2 em diante, você e o Claude Code fazem juntos: o Claude roda os comandos, você confere e aprova. Os nomes em inglês são os que aparecem na tela do GitHub.

## Antes de começar

- Conta pessoal no GitHub, com o seu usuário enviado ao mentor.
- No computador: Git, Python 3.12 ou mais novo e o Claude Code no app do Claude.

## 1. Organização e repositório (o mentor faz)

1. O mentor cria uma organização no plano Free, com o nome que você escolher, e convida você como dono (**Owner**). Aceite o convite, que chega por e-mail ou em https://github.com/notifications.
2. O mentor cria o seu repositório dentro da organização a partir do modelo `guilobocarvalho/mentoria-p3-modelo` (**Use this template › Create a new repository**), privado (**Private**) ou, se o projeto for aberto, público (ver "Se o repositório for público"), com nome sem espaço e sem acento (`ferramentas-medicao`). O repositório já vem com todos os arquivos do modelo, sem o histórico dele.
3. O mentor roda o workflow **Etiquetas** no repositório novo (Actions › Etiquetas › Run workflow): ele cria as etiquetas das issues e apaga as padrão do GitHub.
4. O mentor registra no `Checklist_Projeto.md` › Dados-chave a versão do modelo usada na cópia (a mais recente em **Releases** do modelo). É dela que partem as atualizações (ver `atualizar_do_modelo.md`).
5. O mentor liga, no repositório novo, **Settings › General › Automatically delete head branches** (apaga o branch depois do merge). O template não copia as configurações.
6. O mentor fica como membro da organização durante a mentoria; é assim que a issue de suporte chega a ele. No fim, você decide se ele sai.

## 2. Trazer para o computador

1. Crie a pasta `C:\repos\` (no Mac, `~/repos/`). Se a TI não deixar criar pasta direto no `C:\`, use `C:\Users\<seu usuário>\repos\`.
2. Peça ao Claude Code: "clone o repositório <endereço> em C:\repos".
3. Não use pasta sincronizada com OneDrive, Google Drive ou SharePoint: a sincronização pode estragar a pasta `.git`. O GitHub já é o backup.
4. Peça ao Claude: "crie a .venv e ligue a barreira local". Ele roda, dentro da pasta do repositório:
   - `python -m venv .venv` (o ambiente do Python só deste repositório; fica no seu computador);
   - `git config core.hooksPath .githooks` (as barreiras locais: antes de cada commit, barra commit na `main` e segredos; antes de cada push, roda o `verificar_tudo`).

## 3. Preencher o projeto

1. Peça ao Claude: "leia o CLAUDE.md e me ajude a preencher o projeto". Ele preenche nome, critério de conclusão e escopo com você e troca "a definir" nos títulos dos documentos.
2. Os arquivos que começam com ponto (`.github/`, `.gitignore`, `.env.example`) fazem parte do modelo. No Windows eles podem ficar ocultos: no Explorador de Arquivos, **Exibir › Mostrar › Itens ocultos**.

## 4. Conferir as etiquetas

Em **Issues › Labels**, devem aparecer `pedido`, `defeito`, `suporte`, `em andamento` e `aguardando responsável`. Não apareceram? Peça ao mentor para rodar o workflow **Etiquetas**. O que cada uma quer dizer está em `papeis_dos_chats.md`, nesta pasta.

## 5. Primeira verificação

1. Peça ao Claude: "instale as bibliotecas e rode o verificar_tudo". Ele roda, com o Python da `.venv`:
   - `pip install -r requirements.txt -r requirements-dev.txt`
   - `python verificacoes/verificar_tudo.py`
2. Tudo OK → peça o commit da preparação num branch (`preparacao`) e o pull request. Até a preparação passa por pull request: a barreira local barra commit direto na `main`.
3. Com o CI verde no pull request, faça o merge. Na aba **Actions**, o workflow **Versão** cria a primeira tag (`v` + a data) e chama o **Deploy**, que hoje só avisa "destino a definir".

## 6. Primeira ferramenta

1. Abra uma issue **Pedido de ferramenta**.
2. Peça ao Claude: "vamos trabalhar na issue <número>". Ele cria o branch, escreve o teste, mostra o que o teste confere e só então escreve o código.
3. No pull request, faça o teste manual e marque o checklist. Com o CI verde, peça o merge.
4. A ferramenta de exemplo (`src/exemplo.py` e `testes/test_exemplo.py`) pode sair nesse primeiro pull request.

## Se o repositório for público

Tudo fica visível para qualquer pessoa: código, issues, pull requests e logs do Actions. O modelo já traz o `SECURITY.md`, o `CONTRIBUTING.md`, o formulário "Sugestão ou erro (para quem é de fora)" e a revisão de dependências, que só roda em público. A ordem que funcionou:

1. O mentor cria o repositório pelo modelo como **Public** (passo 1).
2. Logo em seguida, o mentor liga o **Dependency graph** pela tela (Settings › Code security). Sem ele, a revisão de dependências falha em todo pull request.
3. Passos 2 a 5 como no privado, com a preparação entrando por pull request.
4. Depois do merge da preparação, o mentor roda `/configurar-publico`: regras da `main` e das versões, aprovação para o CI de pull request de quem é de fora, varredura de segredos, relato privado de falha, Dependabot e CodeQL.
5. A partir daí, a `main` só aceita pull request com o CI verde, inclusive para o próprio mentor.

Também vale saber: o conteúdo do modelo (guias, regras) fica público junto; credencial que dá acesso a dados vai num environment restrito à `main` (ver `segredos_no_github.md`); e workflow agendado pausa depois de 60 dias sem atividade no repositório.

## Se responsável e mentor forem a mesma pessoa

Acontece quando o mentor usa o modelo num projeto próprio. Nada quebra, mas três coisas mudam:

- **Suporte:** o formulário "Suporte do mentor" atribui a issue a você mesmo. Use-o para registrar o que travou; a resposta é sua.
- **Revisão:** o GitHub não deixa aprovar o próprio pull request. A revisão continua com o subagente `revisor`, e, se houver regra de proteção da `main` (repositório público), ela fica com 0 aprovações.
- **Checklist:** itens "_resp.: mentor_" e "_resp.: a definir_" são todos seus.

## Se uma versão saiu com problema

1. Abra uma issue **Defeito numa ferramenta** dizendo qual versão (página **Releases**).
2. Para desfazer: no pull request que trouxe o problema, o botão **Revert** abre um pull request que desfaz a mudança. Com o CI verde e o merge, sai uma versão nova, sem o problema.
3. Com pressa: em **Actions › Deploy › Run workflow**, informe a versão anterior que funcionava (ex.: `v2026.11.04`). O deploy entrega essa versão enquanto o revert não entra.

## Se precisar de senha ou chave

Ver `segredos_no_github.md`, nesta pasta.
