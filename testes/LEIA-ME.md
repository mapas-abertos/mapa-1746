# testes

Testes automáticos das ferramentas de `src/`, rodados pelo pytest no CI e no seu computador.

- Um arquivo por ferramenta: `test_<nome da ferramenta>.py`.
- Teste primeiro (TDD): cada item do "Quando está pronta" da issue vira um teste antes do código existir. O teste falha, o código é escrito, o teste passa.
- O nome de cada teste diz o que ele confere, em português (`test_planilha_sem_coluna_de_valor_avisa_qual_falta`).
- Teste usa dado fictício, escrito no próprio teste ou em `_referencias/`. Nunca dado de `dados/`.
- Rodar só os testes: `python verificacoes/rodar_testes.py`.
