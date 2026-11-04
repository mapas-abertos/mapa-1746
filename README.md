# Mapa 1746

Mapa público dos chamados do 1746 do Rio de Janeiro, com totais por rua ou por quadrado de ~100 m, feito a partir dos dados abertos da Prefeitura. Método e fonte abertos, com atualização automática pelo GitHub Actions.

Feito a partir do modelo P3 da mentoria de IA da LOBO DE CARVALHO SOLUCOES LTDA. O código é escrito pelo Claude Code; o responsável descreve o que quer, aprova o teste e confere o resultado.

## Fonte dos dados

- Chamados do 1746 da Prefeitura do Rio de Janeiro, publicados no Data.Rio e lidos na tabela `datario.administracao_servicos_publicos.chamado_1746` do BigQuery.
- Licença dos dados de origem: a definir (será conferida na fonte).
- O mapa mostra só totais agregados por rua ou por quadrado de ~100 m. Chamado individual, coordenada exata e dado de pessoas não entram neste repositório.

## Licença

O código está sob a licença MIT (ver `LICENSE`). Os dados seguem a licença da fonte.

## Como começar

1. Clone o repositório em `C:\repos\` (no Mac, `~/repos/`), fora da pasta sincronizada com OneDrive, Google Drive ou SharePoint. O GitHub já é o backup.
2. Abra a pasta no Claude Code e peça: "leia o CLAUDE.md e prepare o repositório".
3. Siga `docs/como_usar_este_modelo.md` na primeira vez.

## O ciclo de cada ferramenta

1. **Pedido:** abra uma issue "Pedido de ferramenta": o que faz, onde entra e quando está pronta.
2. **Teste:** o Claude escreve o teste a partir do "Quando está pronta" e explica o que ele confere.
3. **Código:** o Claude escreve a ferramenta até o teste passar.
4. **Pull request:** você faz o teste manual; o CI confere código e documentos.
5. **Merge:** com o CI verde, a versão sai sozinha (tag com a data) e segue para o deploy.

## Travou?

Ferramenta fazendo algo errado? Abra uma issue "Defeito numa ferramenta". Travou em outra coisa? Abra uma issue "Suporte do mentor". O mentor responde em até 24 horas, contadas em dias úteis.

## Onde está cada coisa

Ver `map.md`.
