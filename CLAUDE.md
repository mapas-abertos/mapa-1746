# Nome do projeto — a definir

O que este repositório resolve, em duas frases: a definir.

**Responsável:** a definir · **Mentor:** `guilobocarvalho` no GitHub · **Início:** a definir · **Prazo:** a definir

## Regra deste arquivo — leia antes de editá-lo

Este arquivo é lido em **toda sessão**. Só entra aqui o que toda sessão precisa: o que é o projeto, as regras que sempre valem e a rotina de fim de sessão. Andamento vai no `Checklist_Projeto.md`, o porquê das escolhas no `decisoes.md`, o que foi feito no `historico.md`, preferências no `memory.md`.

**Teto: 1.500 palavras**, conferido pelo CI. Para acrescentar uma linha, tire outra: não suba o teto.

## O projeto

**Critério de conclusão:** a definir.

**Escopo**
- Dentro: a definir.
- Fora: a definir.

## Regras

- Ler `memory.md` antes de qualquer tarefa. Para achar um arquivo, `map.md`.
- Não inventar dados: o que não foi confirmado fica "a definir".
- Marcar `[x]` no checklist ao resolver um item e anotar decisão e responsável na linha.
- Ideia de melhoria vai para `Backlog_Melhorias.md`. Não implementar sem aprovação. O que seria melhor no próprio modelo (CI, regras, guias), e não neste projeto, entra lá com a origem "modelo P3": o mentor leva de volta ao modelo.
- Idioma: português (Brasil). Respostas diretas e concisas, sem jargão: o responsável não precisa saber programar.

## Papéis dos chats

O trabalho se divide em dois papéis, com a issue como contrato entre eles. Frases de abertura em `docs/papeis_dos_chats.md`.

- **Gestor (Opus), o chat principal:** conversa com o responsável, abre e refina as issues (o "Quando está pronta" precisa ser testável), prioriza, atende o suporte e revisa cada pull request contra a issue. Não escreve código de ferramenta. Para cada issue, abre uma sessão nova (sub chat) no Sonnet, com o número da issue como tarefa e o nível de esforço da tabela de `docs/papeis_dos_chats.md` › Nível de esforço e falha; se não for possível abrir o sub chat, roda a issue num subagente no Sonnet, como plano B.
- **Operador (Sonnet), um sub chat por issue:** lê este arquivo e a issue e faz o ciclo abaixo, do branch ao pull request. Não muda o escopo: dúvida vira comentário na issue, e o gestor responde. Se falhar, segue a escada de falha do mesmo arquivo. Ao terminar, avisa o gestor com o link do pull request.
- **Quem faz registra:** o chat que fez a mudança atualiza `historico.md`, `map.md` e o checklist no mesmo branch, seja o gestor ou o operador. Decisão de escopo tomada pelo gestor vai para o `decisoes.md` no pull request da issue.
- Várias issues podem andar ao mesmo tempo, cada uma no seu sub chat. Etiquetas, quem pega, quem fecha e a prioridade seguem `docs/papeis_dos_chats.md` › Issues e etiquetas.

## Como trabalhar no código

O responsável descreve e aprova; o Claude escreve o código e cuida do Git. Antes de cada comando que muda o GitHub (push, pull request, merge), diga em uma frase o que vai fazer.

1. **Todo trabalho começa numa issue**: "Pedido de ferramenta" para algo novo, "Defeito numa ferramenta" para o que faz algo errado, "Suporte do mentor" quando travar. Sem issue, peça ao responsável para abrir uma ou abra com ele.
2. **Um branch por issue**, com o número e um nome curto (`issue-12-resumo-medicao`). Nunca commit direto na `main`.
3. **Teste primeiro (TDD)**: de cada item do "Quando está pronta" da issue, escreva um teste em `testes/`, explique ao responsável em linguagem simples o que ele confere e rode para ver falhar. Só então escreva o código em `src/`, até o teste passar. Se o teste está certo, quem muda é o código, não o teste.
4. O que não dá para testar automaticamente (programa externo, tela, arquivo real) vai para o teste manual do pull request, feito pelo responsável.
5. **Antes de cada push**: `python verificacoes/verificar_tudo.py`. Algum ERRO → corrija antes do push. A barreira local (`.githooks/pre-commit`) confere segredos a cada commit; nunca a pule com `--no-verify`.
6. **Pull request** com o template, ligado à issue (`Fecha #12`). Merge só com o CI verde, a revisão do gestor e o teste manual marcado pelo responsável. Conflito com a `main` (comum no `historico.md` e no `map.md` quando várias issues andam juntas): traga a `main` para o branch e mantenha as linhas dos dois lados; o CI confere a ordem do histórico e o mapa. Nunca faça merge com o CI vermelho: no GitHub Free com repositório privado, o GitHub não impede; esta regra impede.
7. Depois do merge, a versão sai sozinha (tag com a data, ver `decisoes.md`). Não crie tags à mão.

## Segredos e dados

- Python sempre pelo ambiente do repositório (`.venv`): `.venv/Scripts/python` no Windows, `.venv/bin/python` no Mac. Biblioteca nova vai para o `requirements.txt`, com a versão fixa.

- Senha, token e chave de API: só no `.env` do computador (a partir do `.env.example`) e nos Secrets do repositório no GitHub. Nunca no código, em commit, em issue ou na conversa. Ver `docs/segredos_no_github.md`.
- Se um segredo aparecer na conversa ou num arquivo, avise o responsável na hora: a chave tem de ser trocada no serviço de origem.
- Dado de cliente ou de pessoas só vai para o GitHub se o responsável disser que pode. O que pode ir fica em `_referencias/`; o que não pode fica em `dados/`, que o git ignora.

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
