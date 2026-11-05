## O que muda

<!-- Uma ou duas frases. Com o número da issue em "Closes #" (em inglês, que é o que o GitHub entende), ela fecha sozinha no merge. -->

Closes #

## Teste manual (feito por você, não pelo Claude)

- [ ] Conferi cada item do "Quando está pronta" da issue.
  - Ferramenta: rodei no meu computador com um exemplo (de `_referencias/` ou fictício) e testei um caso de erro (entrada errada, arquivo faltando); a mensagem diz o que fazer.
  - Configuração ou documentação: li os arquivos na aba **Files changed** e conferi o efeito (o check, a tela ou o texto que a issue pede).

## Evidência (o operador cola)

<!-- O comando que rodou e o final da saída do verificar_tudo. "Passou" sozinho não vale. -->

```
python verificacoes/verificar_tudo.py
...
```

## Antes do merge

- [ ] Conferência automática (CI) verde neste pull request.
- [ ] Revisado pelo subagente `revisor`, a pedido do gestor, contra a issue.
- [ ] Os testes automáticos cobrem o "Quando está pronta" da issue.
- [ ] `historico.md`, `map.md` e checklist atualizados.
- [ ] Nenhuma senha, chave ou dado real fora de `_referencias/`.
