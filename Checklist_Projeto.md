# Checklist — a definir

Fonte de verdade do andamento. Marque `[x]` ao resolver e anote decisão e responsável na linha.

**Última atualização:** 2026-11-04

## Dados-chave

| Campo | Valor |
|---|---|
| Responsável | a definir |
| Mentor | `guilobocarvalho` no GitHub |
| Organização no GitHub | a definir |
| Modelo de origem | a definir (versão do `guilobocarvalho/mentoria-p3-modelo` de onde este repositório nasceu, ex.: v2026.11.04.2; ver `docs/atualizar_do_modelo.md`) |
| Início | a definir |
| Prazo / marco | a definir |
| Critério de conclusão | ver `CLAUDE.md` › O projeto |

## Temas

### 1. Preparar o repositório

Passo a passo em `docs/como_usar_este_modelo.md`.

- [ ] Organização criada pelo mentor, com o responsável como dono (**Owner**) e convite aceito, e este repositório criado a partir do modelo, privado — _resp.: mentor_
- [ ] Preencher nome, responsável, critério de conclusão e escopo no `CLAUDE.md` e os títulos dos documentos — _resp.: a definir_
- [ ] Registrar em Dados-chave a versão do modelo de onde o repositório nasceu (a mais recente em Releases do modelo, no dia da cópia) — _resp.: mentor_
- [ ] Ligar **Automatically delete head branches** nas configurações do repositório — _resp.: mentor_
- [ ] Criar a `.venv` e ligar a barreira local (`git config core.hooksPath .githooks`) em cada computador que clonar o repositório — _resp.: a definir_
- [ ] Rodar o workflow **Etiquetas** (Actions › Etiquetas › Run workflow) e conferir as cinco etiquetas — _resp.: mentor_
- [ ] Primeira rodada de `python verificacoes/verificar_tudo.py` no computador e CI verde no GitHub — _resp.: a definir_
- [ ] Definir o destino de deploy e preencher o `.github/workflows/deploy.yml` — _resp.: a definir_
- [ ] No fim da mentoria, decidir se o mentor sai da organização — _resp.: a definir_

### 2. Ferramentas

A ordem da lista é a prioridade: o de cima é o próximo. O gestor mantém.

- [ ] Primeira ferramenta: a definir (abrir como "Pedido de ferramenta") — _resp.: a definir_
