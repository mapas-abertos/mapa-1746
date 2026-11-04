# src

Código das ferramentas, em Python, escrito pelo Claude.

- Um arquivo por ferramenta, com nome que diz o que ela faz (`resumo_medicao.py`). No topo, um texto curto: o que faz e qual issue pediu.
- Toda ferramenta tem teste em `testes/`, escrito antes do código. O CI barra código sem teste.
- Biblioteca de fora (ex.: para ler planilha) vai no `requirements.txt` da raiz, com a versão fixa, no mesmo pull request.
- Senha e chave são lidas do ambiente (`os.environ["NOME"]`), nunca escritas no código.
- `exemplo.py` é a ferramenta de exemplo do modelo. Apague-a com o teste dela quando a primeira ferramenta de verdade entrar, e atualize o `map.md`.
