# verificacoes/testes

Testes das próprias verificações do CI: para cada uma, um caso que passa e casos que falham.

- Cada teste monta um repositório pequeno numa pasta temporária e roda a verificação nele. O repositório de verdade não é alterado.
- Rodam junto com os testes das ferramentas, no CI e em `python verificacoes/rodar_testes.py`.
- Senhas e tokens de teste são montados em partes no código, para este arquivo não ser barrado pela própria barreira.
