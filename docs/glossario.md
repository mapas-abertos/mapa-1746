# Glossário

Os nomes em português que usamos para o que o Git e o GitHub fazem. O termo em inglês vem entre parênteses na primeira vez, porque é ele que aparece nas telas do GitHub e nas mensagens de erro: vale conhecer os dois.

O Claude fala com o responsável usando esta coluna da esquerda.

## O trabalho no dia a dia

| Nome em português | Termo em inglês | O que é |
|---|---|---|
| **projeto no GitHub** | repository | A pasta do projeto guardada no GitHub, com todo o histórico de mudanças. |
| **cópia no computador** | clone | A pasta do projeto trazida do GitHub para o seu computador. |
| **chamado** | issue | Um pedido, defeito, tarefa ou suporte registrado no GitHub. Todo trabalho começa num chamado. |
| **etiqueta** | label | A marca do chamado: `pedido`, `defeito`, `em andamento` etc. |
| **linha de trabalho** | branch | Uma linha separada de mudanças, para mexer sem afetar a versão aprovada. Uma por chamado. |
| **salvar etapa** | commit | Guardar uma etapa do trabalho, com uma descrição, **no seu computador**. Dá para voltar a ela depois. |
| **enviar para a nuvem** | push | Mandar as etapas salvas do computador para o GitHub. Só depois disso elas ficam guardadas na nuvem. |
| **trazer da nuvem** | pull | Atualizar a cópia do computador com o que mudou no GitHub. |
| **pedido de revisão** | pull request (PR) | A proposta de levar uma linha de trabalho para a versão aprovada, para conferir antes. |
| **juntar à versão aprovada** | merge | Aprovar o pedido de revisão e incorporar a mudança. |
| **conflito** | conflict | Duas mudanças no mesmo trecho: alguém escolhe como fica. |
| **desfazer** | revert | Um pedido de revisão que volta uma mudança atrás. |

## As versões

| Nome em português | Termo em inglês | O que é |
|---|---|---|
| **versão aprovada** | `main` | A linha de trabalho principal: tudo que já foi revisado e juntado. Ainda não é o que está em uso. |
| **versão em uso** | `prod` | A linha de trabalho do que está em uso de verdade. Só a rotina de publicar mexe nela. |
| **publicar versão** | release | O passo, separado do juntar, que leva a versão aprovada para uso: cria a versão, move a `prod` e chama a entrega automática. Quem decide é o responsável. |
| **versão** | tag / release | Um retrato com nome e data do que foi publicado, como `v2026.11.05`. |

## O que roda sozinho

| Nome em português | Termo em inglês | O que é |
|---|---|---|
| **conferência automática** | CI | As verificações que o GitHub roda sozinho em cada mudança: documentos, segredos, código e testes. |
| **entrega automática** | CD / deploy | Levar a versão publicada até onde ela vai ser usada. |
| **rotina automática** | workflow / GitHub Actions | Um roteiro que o GitHub roda sozinho, como a conferência, a publicação e as etiquetas. |
| **trava do computador** | hook | Uma conferência que roda no seu computador antes de salvar etapa ou enviar para a nuvem. |
| **regra de proteção** | ruleset | O que o GitHub exige antes de juntar à versão aprovada (só em projeto público). |
| **revisão de escrita do código** | lint | Procura erros de digitação e de estilo no código. |

## Senhas e configuração

| Nome em português | Termo em inglês | O que é |
|---|---|---|
| **cofre de senhas do GitHub** | secrets | Onde ficam as senhas que as rotinas automáticas usam. |
| **arquivo de senhas do computador** | `.env` | O mesmo, no seu computador, fora do GitHub. |
| **modelo** | template | O projeto-base de onde este foi copiado. |
| **pasta do sub chat** | worktree | Uma cópia separada da pasta, para dois chats não se atrapalharem. |
