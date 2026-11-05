---
name: abrir-pedido
description: Entrevista o responsável e abre uma issue de pedido de ferramenta, de defeito ou de tarefa (configuração ou documentação) com o "Quando está pronta" testável. Use quando o responsável quiser uma ferramenta nova, uma mudança ou relatar que algo está errado.
---

# Abrir um pedido

Quem faz é o gestor. O objetivo é sair com uma issue que o operador consiga transformar em teste sem voltar a perguntar.

1. **Entreviste com perguntas de múltipla escolha**, poucas por vez, até conseguir escrever cada campo do formulário: o que faz (entrada e saída), onde entra no trabalho, quando está pronta, exemplo fictício e se mexe com dado sensível. Para defeito: qual ferramenta, os passos, o que deveria acontecer e o que aconteceu. Para tarefa: o que, por quê e quando está pronta.
2. **"Quando está pronta" testável:** cada item é algo que um teste confere, com entrada e resultado esperados. Inclua pelo menos um caso de erro (entrada errada, arquivo faltando) e a mensagem esperada.
3. **Mostre o texto ao responsável** e ajuste até ele aprovar.
4. **Abra a issue** com `gh issue create`, com o título começando por `[Pedido]`, `[Defeito]` ou `[Tarefa]`, a etiqueta `pedido`, `defeito` ou `tarefa` e o corpo com as mesmas seções do formulário em `.github/ISSUE_TEMPLATE/`.
5. **Prioridade:** acrescente a issue no `Checklist_Projeto.md`, tema "Ferramentas", na posição que o responsável escolher.
6. Dado sensível: só dado fictício na issue. Original que pode ir para o GitHub vai para `_referencias/`; o que não pode fica em `dados/`.
