# Segredos no GitHub

Segredo é tudo que dá acesso a algo: senha, token, chave de API, certificado. Quem tem o segredo entra no lugar de quem é dono dele.

## A regra

**Segredo nunca entra no código, num commit, numa issue ou na conversa com o Claude.** Ele fica em dois lugares só:

| Onde a ferramenta roda | Onde fica o segredo |
|---|---|
| No seu computador | No arquivo `.env`, na pasta do repositório. O `.gitignore` impede que ele vá para o GitHub. |
| No GitHub (Actions) | Nos Secrets do repositório: **Settings › Secrets and variables › Actions**. |

O código só lê o segredo pelo nome, nunca pelo valor.

## No seu computador: o `.env`

1. Copie o `.env.example` com o nome `.env`, na mesma pasta.
2. Preencha o valor no `.env`, à mão. Não cole o valor na conversa com o Claude: diga só o nome ("a chave se chama MINHA_CHAVE_DE_API e já está no .env").
3. Chave nova: o nome vai no `.env.example` (sem o valor), e o valor no `.env`.

## No GitHub: os Secrets do repositório

1. No repositório: **Settings › Secrets and variables › Actions › New repository secret**.
2. **Name**: o mesmo nome do `.env` (`MINHA_CHAVE_DE_API`). **Secret**: o valor. **Add secret**.
3. Depois de salvo, nem você vê o valor de novo; para mudar, use **Update**.
4. O workflow usa o segredo assim:

```yaml
      - name: Rodar a ferramenta
        env:
          MINHA_CHAVE_DE_API: ${{ secrets.MINHA_CHAVE_DE_API }}
        run: python src/minha_ferramenta.py
```

5. O código Python lê do mesmo jeito nos dois lugares:

```python
import os

chave = os.environ["MINHA_CHAVE_DE_API"]
```

No GitHub Free com repositório privado, os segredos ficam no nível do repositório: não há segredo por ambiente (environments). Para uma ferramenta simples, basta.

## A barreira do CI

`verificacoes/segredos.py` roda a cada pull request e barra `.env`, chaves e certificados, além de textos que parecem senha ou token dentro dos arquivos. Alarme falso: escreva `nao-e-segredo` num comentário na mesma linha e explique no pull request.

## Se um segredo vazou

Vazou = foi para um commit, uma issue, a conversa com o Claude ou qualquer lugar fora do `.env` e dos Secrets.

1. **Troque o segredo no serviço de origem** (gere uma chave nova e apague a antiga). Apagar o arquivo não basta: o histórico do Git guarda a versão antiga.
2. Atualize o `.env` e o Secret do GitHub com o valor novo.
3. Avise o mentor por uma issue de suporte, sem colar o segredo.
