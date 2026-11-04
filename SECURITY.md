# Segurança — Mapa 1746

Achou uma falha de segurança? Obrigado por avisar. Relate em particular, como explicado abaixo.

## Como relatar

1. Abra a aba **Security** deste repositório no GitHub.
2. Clique em **Report a vulnerability**.
3. Descreva o que encontrou, onde está e como repetir o problema.

Só você e os responsáveis pelo projeto veem o relato. A resposta vem pelo próprio relato no GitHub.

**Nunca relate uma falha numa issue pública.** Uma issue fica visível para qualquer pessoa, antes de a falha ser corrigida. Não há e-mail para relatos: use só o botão acima.

## O que conta como falha de segurança

- Falha no código das ferramentas (`src/`) ou das verificações (`verificacoes/`).
- Falha nos workflows do GitHub Actions (`.github/workflows/`), como um jeito de rodar código ou ler uma credencial sem permissão.
- Segredo exposto: senha, token ou chave de API em arquivo, commit, issue, pull request ou log.
- Dado que identifique uma pessoa: chamado individual, coordenada exata, nome, telefone ou endereço de quem fez o chamado.

Se você viu um segredo ou um dado pessoal exposto, não copie o valor no relato. Diga só onde ele está.

## O que não conta

Erro no mapa, número que não bate ou sugestão de melhoria não são falhas de segurança. Para isso, abra uma issue, como explica o [`CONTRIBUTING.md`](CONTRIBUTING.md).
