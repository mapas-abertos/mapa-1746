# Papéis dos chats

Dois papéis, com o chamado (issue) como contrato entre eles. A regra completa está no `CLAUDE.md` › Papéis dos chats; aqui ficam as frases para abrir cada chat. Os nomes seguem o `docs/glossario.md`.

| | Gestor | Operador |
|---|---|---|
| Modelo | Opus, esforço médio (alto ao revisar pedido de revisão feito no Opus ou que mexe na conferência automática) | Sonnet, esforço médio; sobe pela escada abaixo |
| Quantos | Um, o chat principal do projeto | Um sub chat novo por chamado (subagente, se não der) |
| Faz | Conversa com você, abre e refina chamados, prioriza, atende o suporte, revisa o pedido de revisão contra o chamado | Linha de trabalho, teste, código e pedido de revisão de um chamado |
| Não faz | Código de ferramenta | Mudar o escopo do chamado |
| Registra | O que ele mesmo mudou | O que ele mesmo mudou, no pedido de revisão do chamado |

## Chamados e etiquetas

| Etiqueta (label) | O que quer dizer | Quem põe | Quem tira |
|---|---|---|---|
| `pedido` | Ferramenta nova ou mudança numa que já existe | O formulário | — |
| `defeito` | Ferramenta que já existe fazendo algo errado | O formulário | — |
| `tarefa` | Configuração ou documentação, sem ser ferramenta | O formulário | — |
| `suporte` | Travou: o mentor é avisado | O formulário | — |
| `externo` | Aberto por quem é de fora (projeto público) | O formulário | O gestor, ao transformar em pedido, defeito ou tarefa, ou ao fechar |
| `em andamento` | Um sub chat (ou subagente) está trabalhando nele | O gestor, ao abrir o sub chat | A rotina automática **Chamado fechado**, quando o chamado fecha |
| `aguardando responsável` | Dúvida esperando resposta sua | Quem perguntou, gestor ou operador | O gestor, quando você responde (ou a rotina, se o chamado fechar antes) |

- **Abrir:** o gestor abre ou refina o chamado com você, num dos formulários: pedido, defeito, tarefa ou suporte.
- **Pegar:** ao abrir o sub chat, o gestor põe `em andamento` e comenta no chamado quem pegou ("sub chat aberto em 04/11"). Chamado com `em andamento` não vai para outro sub chat.
- **Dúvida:** vira comentário no chamado, com `aguardando responsável`.
- **Fechar:** pedido, defeito e tarefa fecham sozinhos ao juntar à versão aprovada (merge), pelo `Closes #N` do pedido de revisão (em inglês: `Fecha` não funciona). Ao fechar, a rotina **Chamado fechado** tira as etiquetas de situação. Suporte fecha quando você confirma que destravou.
- **Prioridade:** sem etiqueta. O gestor mantém a ordem no `Checklist_Projeto.md`, tema "Ferramentas": o de cima é o próximo.
- As etiquetas são criadas pela rotina automática (workflow) **Etiquetas** (Actions › Etiquetas › Run workflow), uma vez, logo depois de o projeto ser criado.

## Nível de esforço e falha

O gestor escolhe o nível do operador por esta tabela, ao abrir o sub chat. Não precisa anotar no chamado: o nível sai da regra.

| Nível | Quando |
|---|---|
| **Sonnet médio** (padrão) | Pedido ou defeito com o "Quando está pronta" claro, numa ferramenta só |
| **Sonnet alto** | Muitos casos de regra, leitura de arquivo ou sistema externo, defeito sem causa óbvia, ou o Sonnet médio falhou |
| **Opus** | Decisão que afeta várias ferramentas (a primeira ferramenta, que define o padrão, ou mudança de estrutura), segredos e entrega automática (deploy), mudança nas verificações da conferência automática (CI), ou o Sonnet alto falhou |

**Conta como falha:** a conferência automática fica vermelha de novo no mesmo ponto depois da correção, o teste manual é reprovado, ou o operador anda em círculo. **Não conta:** queda do sub chat, falta de internet ou limite do plano; nesses casos, reabra no mesmo nível.

**Escada de falha:**

1. Antes de subir de nível, o gestor relê o chamado. Se o problema é o chamado ambíguo, ele volta para você com `aguardando responsável`, e o nível não muda.
2. Chamado claro: 2 tentativas por nível, na ordem Sonnet médio, Sonnet alto, Opus.
3. Falhou no Opus: chamado "Suporte do mentor", com o link do pedido de revisão e as tentativas.
4. A cada subida, o operador que sai comenta no chamado o nível, a tentativa, o que tentou, o erro e onde parou. O sub chat novo começa por esse comentário.
5. O sub chat novo continua na mesma linha de trabalho (branch). Se o gestor julgar que a abordagem estava errada, o pedido de revisão antigo fecha sem juntar e uma linha de trabalho nova começa da versão aprovada (`main`).

## Se não der para abrir o sub chat

1. **Antes do plano B, confira o pedido de confiança.** Na primeira vez num projeto, o sub chat novo pode parar pedindo para "confiar" na pasta. Esse pedido aparece só dentro do sub chat, e não no chat do gestor. O gestor avisa você, e você abre o sub chat e aceita.
2. **Plano B:** se o app não oferecer a sessão nova, ou ela falhar ao abrir mesmo assim, o gestor roda o chamado num subagente no Sonnet, dentro do próprio chat, com as mesmas regras do operador. O comentário no chamado diz "subagente no chat do gestor".
3. **Sub chat que abre depois:** se o sub chat do chamado abrir quando o subagente já estiver trabalhando (ou tiver terminado), o gestor arquiva o sub chat sem deixar ele começar e comenta no chamado ("sub chat arquivado; o chamado seguiu no subagente"). Nunca dois chats no mesmo chamado.
4. O subagente acaba junto com o chat do gestor: se o chat cair no meio, o gestor tira `em andamento` e o chamado recomeça da linha de trabalho, que guarda o que já foi enviado para a nuvem.

## Abrir o gestor

No app do Claude, abra um chat do Claude Code na pasta do projeto, com o modelo Opus, e cole:

> Você é o gestor deste projeto. Leia o `CLAUDE.md` e o `memory.md`, veja os chamados abertos e me diga em que pé estamos e qual chamado sugere fazer agora.

## Pedir uma ferramenta

Converse com o gestor sobre o que você precisa. Ele usa a skill `abrir-pedido`: faz perguntas de múltipla escolha até conseguir escrever cada campo, mostra o texto para você aprovar e abre o chamado. O "Quando está pronta" sai testável, com pelo menos um caso de erro.

## Mandar um chamado para o operador

Diga ao gestor:

> Abra um sub chat no Sonnet para o chamado 12.

O gestor abre a sessão nova **com pasta própria** (worktree), para dois sub chats não se atrapalharem, e o número do chamado como tarefa. O sub chat segue a skill `operar-issue`: cria a `.venv` na pasta dele, a linha de trabalho, o teste, o código e o pedido de revisão. Você pode acompanhar ou conversar com o sub chat a qualquer momento. Quando ele terminar, avisa o gestor com o link do pedido de revisão.

## Revisar e entregar

1. O gestor pede ao subagente `revisor`, que só lê e não viu o código ser escrito, que compare o pedido de revisão com o chamado. Ele responde "atende / falta", sem comentar estilo.
2. Você faz o teste manual e marca o checklist do pedido de revisão.
3. Com a conferência automática verde, peça ao gestor para juntar à versão aprovada (merge). Ainda não vai para uso.
4. **Depois do merge, o gestor arquiva o sub chat do operador** e comenta no chamado: "sub chat arquivado após o merge". Antes, confere se não há trabalho vivo no sub chat (tarefa em segundo plano, pergunta esperando você). Se o arquivamento falhar por causa do Remote Control, o gestor não o desliga sozinho, porque essa decisão é sua: ele avisa você. Se você preferir, o app pode arquivar sozinho a sessão quando o pedido de revisão fecha; essa configuração é sua.
5. Quando quiser pôr em uso, peça ao gestor "publique a versão" (release). Quem decide publicar é sempre você.

## Vários chamados ao mesmo tempo

Pode. Cada chamado tem o seu sub chat. Se dois pedidos de revisão mexerem no `historico.md` ou no `map.md`, o segundo a entrar pode dar conflito: peça "traga a versão aprovada para esta linha de trabalho e resolva o conflito mantendo as duas entradas". A conferência automática confere se o resultado ficou certo.
