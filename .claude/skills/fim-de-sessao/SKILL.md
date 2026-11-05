---
name: fim-de-sessao
description: Rotina de fechar uma sessão de trabalho neste repositório, atualizando histórico, decisões, memória, mapa e checklist. Use ao terminar uma sessão ou quando o responsável disser que vai parar.
---

# Fim de sessão

Registre só o que você mudou nesta sessão, no branch em que trabalhou.

1. `historico.md`: entrada nova no topo, com a data (`## AAAA-MM-DD`). No mesmo dia, acrescente na entrada que já existe.
2. Decisão nova → `decisoes.md`. Preferência ou correção do responsável → `memory.md`. Arquivo ou pasta novo → `map.md`.
3. Checklist: marque o que foi resolvido e atualize "Última atualização".
4. Melhoria do próprio modelo percebida na sessão → `Backlog_Melhorias.md`, com a origem "modelo P3" e a data. Mostre as linhas novas ao responsável.
5. Rode `python verificacoes/documentos_ia.py`: confere os tetos (`CLAUDE.md` ≤ 1.500 palavras, `memory.md` ≤ 600), o histórico, o checklist, o mapa e os `LEIA-ME`. Passou do teto → mova o detalhe para o arquivo certo e avise o responsável.
6. Pergunta de controle: **o `CLAUDE.md` cresceu? o que saiu em troca?**
