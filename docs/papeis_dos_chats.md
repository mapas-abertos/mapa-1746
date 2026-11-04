# Papéis dos chats

Dois papéis, com a issue como contrato entre eles. A regra completa está no `CLAUDE.md` › Papéis dos chats; aqui ficam as frases para abrir cada chat.

| | Gestor | Operador |
|---|---|---|
| Modelo | Opus, esforço médio (alto ao revisar pull request feito no Opus ou que mexe no CI) | Sonnet, esforço médio; sobe pela escada abaixo |
| Quantos | Um, o chat principal do repositório | Um sub chat novo por issue (subagente, se não der) |
| Faz | Conversa com você, abre e refina issues, prioriza, atende o suporte, revisa o pull request contra a issue | Branch, teste, código e pull request de uma issue |
| Não faz | Código de ferramenta | Mudar o escopo da issue |
| Registra | O que ele mesmo mudou | O que ele mesmo mudou, no pull request da issue |

## Issues e etiquetas

| Etiqueta | O que quer dizer | Quem põe | Quem tira |
|---|---|---|---|
| `pedido` | Ferramenta nova ou mudança numa que já existe | O formulário | — |
| `defeito` | Ferramenta que já existe fazendo algo errado | O formulário | — |
| `suporte` | Travou: o mentor é avisado | O formulário | — |
| `em andamento` | Um sub chat (ou subagente) está trabalhando nela | O gestor, ao abrir o sub chat | O merge fecha a issue |
| `aguardando responsável` | Dúvida esperando resposta sua | Quem perguntou, gestor ou operador | O gestor, quando você responde |

- **Abrir:** o gestor abre ou refina a issue com você, num dos três formulários: pedido, defeito ou suporte.
- **Pegar:** ao abrir o sub chat, o gestor põe `em andamento` e comenta na issue quem pegou ("sub chat aberto em 04/11"). Issue com `em andamento` não vai para outro sub chat.
- **Dúvida:** vira comentário na issue, com `aguardando responsável`.
- **Fechar:** pedido e defeito fecham sozinhos no merge, pelo `Fecha #N` do pull request. Suporte fecha quando você confirma que destravou.
- **Prioridade:** sem etiqueta. O gestor mantém a ordem no `Checklist_Projeto.md`, tema "Ferramentas": o de cima é o próximo.
- As etiquetas são criadas pelo workflow **Etiquetas** (Actions › Etiquetas › Run workflow), uma vez, logo depois de o repositório ser criado.

## Nível de esforço e falha

O gestor escolhe o nível do operador por esta tabela, ao abrir o sub chat. Não precisa anotar na issue: o nível sai da regra.

| Nível | Quando |
|---|---|
| **Sonnet médio** (padrão) | Pedido ou defeito com o "Quando está pronta" claro, numa ferramenta só |
| **Sonnet alto** | Muitos casos de regra, leitura de arquivo ou sistema externo, defeito sem causa óbvia, ou o Sonnet médio falhou |
| **Opus** | Decisão que afeta várias ferramentas (a primeira ferramenta, que define o padrão, ou mudança de estrutura), segredos e deploy, mudança nas verificações do CI, ou o Sonnet alto falhou |

**Conta como falha:** o CI fica vermelho de novo no mesmo ponto depois da correção, o teste manual é reprovado, ou o operador anda em círculo. **Não conta:** queda do sub chat, falta de internet ou limite do plano; nesses casos, reabra no mesmo nível.

**Escada de falha:**

1. Antes de subir de nível, o gestor relê a issue. Se o problema é a issue ambígua, ela volta para você com `aguardando responsável`, e o nível não muda.
2. Issue clara: 2 tentativas por nível, na ordem Sonnet médio, Sonnet alto, Opus.
3. Falhou no Opus: issue "Suporte do mentor", com o link do pull request e as tentativas.
4. A cada subida, o operador que sai comenta na issue o nível, a tentativa, o que tentou, o erro e onde parou. O sub chat novo começa por esse comentário.
5. O sub chat novo continua no mesmo branch. Se o gestor julgar que a abordagem estava errada, o pull request antigo fecha sem merge e um branch novo começa da `main`.

## Se não der para abrir o sub chat

Se o app não oferecer a sessão nova, ou ela falhar ao abrir, o gestor roda a issue num subagente no Sonnet, dentro do próprio chat, com as mesmas regras do operador. O comentário na issue diz "subagente no chat do gestor". O subagente acaba junto com o chat do gestor: se o chat cair no meio, o gestor tira `em andamento` e a issue recomeça do branch, que guarda o que já foi enviado.

## Abrir o gestor

No app do Claude, abra um chat do Claude Code na pasta do repositório, com o modelo Opus, e cole:

> Você é o gestor deste repositório. Leia o `CLAUDE.md` e o `memory.md`, veja as issues abertas e me diga em que pé estamos e qual issue sugere fazer agora.

## Pedir uma ferramenta

Converse com o gestor sobre o que você precisa. Ele abre a issue "Pedido de ferramenta" com você e confere se o "Quando está pronta" dá para testar.

## Mandar uma issue para o operador

Diga ao gestor:

> Abra um sub chat no Sonnet para a issue 12.

O gestor abre a sessão nova com o número da issue como tarefa. Você pode acompanhar ou conversar com o sub chat a qualquer momento. Quando ele terminar, avisa o gestor com o link do pull request.

## Revisar e entregar

1. O gestor confere o pull request contra a issue e diz o que falta, se faltar.
2. Você faz o teste manual e marca o checklist do pull request.
3. Com o CI verde, peça o merge ao gestor. A versão sai sozinha.

## Várias issues ao mesmo tempo

Pode. Cada issue tem o seu sub chat. Se dois pull requests mexerem no `historico.md` ou no `map.md`, o segundo a entrar pode dar conflito: peça "traga a main para este branch e resolva o conflito mantendo as duas entradas". O CI confere se o resultado ficou certo.
