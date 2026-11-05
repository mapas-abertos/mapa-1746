# src

Código das ferramentas, em Python, escrito pelo Claude.

- Um arquivo por ferramenta, com nome que diz o que ela faz (`resumo_medicao.py`). No topo, um texto curto: o que faz e qual issue pediu.
- Toda ferramenta tem teste em `testes/`, escrito antes do código. O CI barra código sem teste.
- Biblioteca de fora (ex.: para ler planilha) vai no `requirements.txt` da raiz, com a versão fixa, no mesmo pull request.
- Senha e chave são lidas do ambiente (`os.environ["NOME"]`), nunca escritas no código.
- A ferramenta de exemplo do modelo (`exemplo.py`) saiu com a primeira ferramenta de verdade, o `agregador.py` (issue #7). Ele é o padrão para as próximas: texto no topo com o que faz e como rodar, regras ajustáveis logo abaixo, mensagens de erro que dizem o que fazer e nunca repetem dado de chamado.
