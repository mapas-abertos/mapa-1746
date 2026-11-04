# verificacoes

Scripts da conferência automática (CI). Rodam no GitHub a cada pull request e no seu computador antes de cada push. Cada um diz, em português, o que está errado e o que fazer.

| Script | Confere |
|---|---|
| `verificar_tudo.py` | Roda todos abaixo, na ordem do GitHub. É o que se roda antes do push. |
| `documentos_ia.py` | Limites de palavras do `CLAUDE.md` (1.500) e do `memory.md` (600), datas e ordem do `historico.md`, "Última atualização" do checklist, `map.md` completo nos dois sentidos e `LEIA-ME.md` em toda pasta. |
| `segredos.py` | Barra `.env`, chaves, arquivos de dados fora de `_referencias/`, arquivos acima de 5 MB e senhas ou tokens escritos nos arquivos. |
| `rodar_lint.py` | Erros de escrita no Python, com o ruff (regras em `pyproject.toml`). |
| `rodar_testes.py` | Código em `src/` sem teste e testes que falham, com o pytest. |
| `comum.py` | Funções usadas por todos (lista dos arquivos que vão para o GitHub). |

Uso, a partir da raiz do repositório:

```
pip install -r requirements-dev.txt
python verificacoes/verificar_tudo.py
```

- Só se usa a biblioteca padrão do Python nestes scripts; ruff e pytest são chamados por fora.
- Alarme falso na barreira de segredos: escreva `nao-e-segredo` num comentário na mesma linha e explique no pull request.
- As regras ajustáveis (limites, extensões barradas, tamanho máximo) ficam no topo de cada script. Mudou uma regra → registre em `decisoes.md` e converse com o mentor.
- Os testes destes scripts ficam em `testes/`, aqui dentro. Mexeu num script → rode `python -m pytest verificacoes/testes`.
