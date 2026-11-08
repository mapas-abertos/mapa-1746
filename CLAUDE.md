# Mapa 1746

Mapa público dos chamados do 1746 do Rio de Janeiro, com totais por rua ou por quadrado de ~100 m, feito a partir dos dados abertos da Prefeitura. Método e fonte abertos, com atualização automática pelo GitHub Actions.

**Responsável:** Guilherme (`guilobocarvalho`) · **Mentor:** `guilobocarvalho` no GitHub · **Início:** 04/11/2026 · **Prazo:** a definir

## Regra deste arquivo — leia antes de editá-lo

Este arquivo é lido em **toda sessão**. Só entra aqui o que toda sessão precisa: o que é o projeto, as regras que sempre valem e a rotina de fim de sessão. Andamento vai no `Checklist_Projeto.md`, o porquê das escolhas no `decisoes.md`, o que foi feito no `historico.md`, preferências no `memory.md`.

**Teto: 1.500 palavras**, conferido pelo CI. Para acrescentar uma linha, tire outra: não suba o teto.

## O projeto

**Critério de conclusão:** mapa no GitHub Pages, publicado depois do OK do advogado, com os totais por rua e por quadrado de ~100 m, uma página de método e fonte, e a atualização automática pelo Actions rodando sem intervenção.

**Escopo**
- Dentro: coletar os chamados do 1746 nos dados abertos da Prefeitura (Data.Rio, BigQuery, só leitura), agregar por rua e por quadrado de ~100 m, publicar o mapa e a página de método e fonte, e atualizar tudo pelo Actions.
- Fora: a definir.

## Regras

- Ler `memory.md` antes de qualquer tarefa. Para achar um arquivo, `map.md`.
- Não inventar dados: o que não foi confirmado fica "a definir".
- Responder só o que foi pedido, partindo dos dados e das colunas que já existem. Sugestão fora do escopo vai numa pergunta separada, marcada "fora do pedido", e nunca misturada nas opções.
- Marcar `[x]` no checklist ao resolver um item e anotar decisão e responsável na linha.
- Ideia de melhoria vai para `Backlog_Melhorias.md`. Não implementar sem aprovação. O que seria melhor no próprio modelo (CI, regras, guias), e não neste projeto, entra lá com a origem "modelo P3": o mentor leva de volta ao modelo.
- Idioma: português (Brasil). Respostas diretas e concisas, sem jargão: o responsável não precisa saber programar.
- Ao falar com o responsável, use os nomes de `docs/glossario.md` (salvar etapa, enviar para a nuvem, pedido de revisão, versão aprovada…), com o termo em inglês entre parênteses na primeira vez em cada conversa: é o que aparece nas telas do GitHub.

## Papéis dos chats

O trabalho se divide em dois papéis, com a issue como contrato entre eles. Frases de abertura em `docs/papeis_dos_chats.md`.

- **Gestor (Opus), o chat principal:** conversa com o responsável, abre e refina as issues (o "Quando está pronta" precisa ser testável), prioriza, atende o suporte e revisa cada pull request contra a issue. Não escreve código de ferramenta. Para cada issue, abre uma sessão nova (sub chat) no Sonnet, com o número da issue como tarefa e o nível de esforço da tabela de `docs/papeis_dos_chats.md` › Nível de esforço e falha; se não for possível abrir o sub chat, roda a issue num subagente no Sonnet, como plano B. O sub chat abre **com worktree** (pasta própria) e segue a skill `operar-issue`; antes do merge, o gestor pede ao subagente `revisor` que compare o pull request com a issue; depois do merge, arquiva o sub chat do operador (`docs/papeis_dos_chats.md` › Revisar e entregar). Pedido novo: skill `abrir-pedido`.
- **Operador (Sonnet), um sub chat por issue:** lê este arquivo e a issue e faz o ciclo abaixo, do branch ao pull request. Não muda o escopo: dúvida vira comentário na issue, e o gestor responde. Se falhar, segue a escada de falha do mesmo arquivo. Ao terminar, avisa o gestor com o link do pull request.
- **Quem faz registra:** o chat que fez a mudança atualiza `historico.md`, `map.md` e o checklist no mesmo branch, seja o gestor ou o operador. Decisão de escopo tomada pelo gestor vai para o `decisoes.md` no pull request da issue.
- Várias issues podem andar ao mesmo tempo, cada uma no seu sub chat. Etiquetas, quem pega, quem fecha e a prioridade seguem `docs/papeis_dos_chats.md` › Issues e etiquetas.

## Como trabalhar no código

O responsável descreve e aprova; o Claude escreve o código e cuida do Git. Antes de cada comando que muda o GitHub (push, pull request, merge), diga em uma frase o que vai fazer.

1. **Todo trabalho começa numa issue**: "Pedido de ferramenta" para algo novo, "Defeito numa ferramenta" para o que faz algo errado, "Suporte do mentor" quando travar. Sem issue, peça ao responsável para abrir uma ou abra com ele.
2. **Um branch por issue**, com o número e um nome curto (`issue-12-resumo-medicao`). Nunca commit direto na `main`.
3. **Teste primeiro (TDD)**: de cada item do "Quando está pronta" da issue, escreva um teste em `testes/`, explique ao responsável em linguagem simples o que ele confere e rode para ver falhar. Só então escreva o código em `src/`, até o teste passar. Se o teste está certo, quem muda é o código, não o teste.
4. O que não dá para testar automaticamente (programa externo, tela, arquivo real) vai para o teste manual do pull request, feito pelo responsável.
5. **Antes de cada push**: `python verificacoes/verificar_tudo.py`. Algum ERRO → corrija antes do push. As barreiras locais barram commit direto na `main` e segredos (`.githooks/pre-commit`) e rodam o `verificar_tudo` antes do push (`.githooks/pre-push`); nunca as pule com `--no-verify`.
6. **Pull request** com o template, ligado à issue (`Closes #12`, em inglês: o GitHub não entende `Fecha`). Merge só com o CI verde, a revisão do gestor e o teste manual marcado pelo responsável. Conflito com a `main` (comum no `historico.md` e no `map.md` quando várias issues andam juntas): traga a `main` para o branch e mantenha as linhas dos dois lados; o CI confere a ordem do histórico e o mapa. Aqui o GitHub impede o merge com o CI vermelho (regra da `main`, ver `decisoes.md`): nunca peça para desligá-la nem para abrir exceção.
7. **Publicar é separado de juntar:** o merge só leva à versão aprovada (`main`). A versão em uso (`prod`) só muda pela rotina **Publicar versão** (`gh workflow run publicar.yml`), e só quando o responsável pedir; aqui o GitHub ainda pede a aprovação dele (ambiente `prod`). Nunca crie tags nem mexa na `prod` à mão.

## Segredos e dados

- Python sempre pelo ambiente do repositório (`.venv`): `.venv/Scripts/python` no Windows, `.venv/bin/python` no Mac. Biblioteca nova vai para o `requirements.txt`, com a versão fixa.

- Senha, token e chave de API: só no `.env` do computador (a partir do `.env.example`) e nos Secrets do repositório no GitHub. Nunca no código, em commit, em issue ou na conversa. Ver `docs/segredos_no_github.md`.
- Se um segredo aparecer na conversa ou num arquivo, avise o responsável na hora: a chave tem de ser trocada no serviço de origem.
- **Este repositório é público:** qualquer pessoa vê todos os arquivos (inclusive este, `memory.md`, `decisoes.md`, `historico.md` e o Backlog), as issues, os pull requests e os logs do Actions. Nada de dado sensível em nenhum deles, nem impresso num log.
- É uma ferramenta cívica e neutra: nenhum conteúdo político-partidário em arquivo, issue, pull request ou commit.
- Só entra dado público agregado por rua ou por quadrado de ~100 m. Chamado individual, coordenada exata, dado de pessoas e credenciais nunca entram: o dado bruto fica em `dados/`, só no computador. O que pode ir fica em `_referencias/`.

## Onde guardar cada coisa

- **Originais e insumos** (planilhas, normas, exemplos, links, transcrições) → `_referencias/`, intactos. É o que explica de onde veio o que estamos fazendo.
- **Código das ferramentas** → `src/`. **Testes** → `testes/`, um `test_<nome>.py` por ferramenta.
- **Guias e explicações** → `docs/`.
- **Verificações do CI** → `verificacoes/`. Mexer só com a concordância do mentor.
- **Dados que não podem ir para o GitHub** → `dados/` (só no computador).
- Toda pasta tem um `LEIA-ME.md` com as regras dela, e todo arquivo aparece no `map.md`. O CI confere as duas coisas.

## Ao final de cada sessão

- `historico.md`: entrada nova no topo, com a data (`## AAAA-MM-DD`). No mesmo dia, acrescente na entrada que já existe.
- Decisão nova → `decisoes.md`. Preferência ou correção → `memory.md`. Arquivo ou pasta novo → `map.md`.
- Checklist: marcar o que foi resolvido e atualizar "Última atualização".
- Rodar `python verificacoes/documentos_ia.py`: confere os tetos (este arquivo ≤ 1.500 palavras, `memory.md` ≤ 600), o histórico, o checklist, o mapa e os `LEIA-ME`. Passou do teto → mover o detalhe para o arquivo certo e avisar o responsável.
- Pergunta de controle: **este arquivo cresceu? o que saiu em troca?**
