# Checklist — Mapa 1746

Fonte de verdade do andamento. Marque `[x]` ao resolver e anote decisão e responsável na linha.

**Última atualização:** 2026-11-05

## Dados-chave

| Campo | Valor |
|---|---|
| Responsável | Guilherme (`guilobocarvalho`); neste projeto, o mesmo usuário do mentor |
| Mentor | `guilobocarvalho` no GitHub |
| Organização no GitHub | `mapas-abertos` (plano Free, criada em 04/11/2026) |
| Modelo de origem | `v2026.11.05.2` do `guilobocarvalho/mentoria-p3-modelo` (ver `docs/atualizar_do_modelo.md`) |
| Início | 04/11/2026 |
| Prazo / marco | a definir |
| Critério de conclusão | ver `CLAUDE.md` › O projeto |

## Temas

### 1. Preparar o repositório

Passo a passo em `docs/como_usar_este_modelo.md`.

- [x] Organização criada pelo mentor, com o responsável como dono (**Owner**) e convite aceito, e este repositório criado a partir do modelo — público, por decisão do responsável — _resp.: mentor, 04/11/2026_
- [x] Preencher nome, responsável, critério de conclusão e escopo no `CLAUDE.md` e os títulos dos documentos — "Fora" do escopo e prazo ficam a definir — _resp.: Guilherme, 04/11/2026_
- [x] Registrar em Dados-chave a versão do modelo de onde o repositório nasceu (a mais recente em Releases do modelo, no dia da cópia) — `v2026.11.04.4` — _resp.: mentor, 04/11/2026_
- [x] Ligar **Automatically delete head branches** nas configurações do repositório — _resp.: mentor, 04/11/2026_
- [x] Criar a `.venv` e ligar a barreira local (`git config core.hooksPath .githooks`) em cada computador que clonar o repositório — feito no computador do Guilherme — _resp.: Guilherme, 04/11/2026_
- [x] Rodar o workflow **Etiquetas** (Actions › Etiquetas › Run workflow) e conferir as cinco etiquetas — _resp.: mentor, 04/11/2026_
- [x] Primeira rodada de `python verificacoes/verificar_tudo.py` no computador e CI verde no GitHub — _resp.: Guilherme, 04/11/2026_
- [ ] Definir o destino de deploy e preencher o `.github/workflows/deploy.yml` — destino escolhido: GitHub Pages (ver `decisoes.md`); preencher e ligar só depois do OK do advogado — _resp.: Guilherme_
- [ ] No fim da mentoria, decidir se o mentor sai da organização — _resp.: a definir_

### 1b. Repositório público

Ajustes porque o repositório é público (ver `decisoes.md`).

- [x] Regra da `main` (Settings › Rules › Rulesets › "Proteger a main"): só por pull request, com "Documentos de IA" e "Código" verdes, sem push forçado, sem apagar, sem exceção para admin — _resp.: Guilherme, 04/11/2026_
- [x] Actions: workflows de pull request de qualquer colaborador externo só rodam com aprovação — _resp.: Guilherme, 04/11/2026_
- [x] Segurança: secret scanning com push protection, alertas do Dependabot e private vulnerability reporting ligados — _resp.: Guilherme, 04/11/2026_
- [x] CodeQL (varredura de segurança do Python e dos workflows), Dependabot abrindo pull request de correção, regra "Proteger as versões" (tags `v*` não são apagadas nem reescritas), tópicos do repositório, Wiki e Projects desligados — _resp.: Guilherme, 04/11/2026_
- [x] `SECURITY.md`, `CONTRIBUTING.md` e revisão de dependências no pull request — issue #3 — _resp.: Guilherme, 04/11/2026_
- [x] Decidir se o check "Revisão de dependências" entra como obrigatório na regra "Proteger a main" — obrigatório (ver `decisoes.md`) — _resp.: Guilherme, 04/11/2026_
- [ ] Ao criar a atualização automática (workflow agendado): em repositório público, o GitHub pausa o agendamento depois de 60 dias sem atividade no repositório; prever como manter ativo e um aviso se parar — _resp.: Guilherme_
- [x] Regras de dado público, neutralidade e logs públicos no `CLAUDE.md` e no `_referencias/LEIA-ME.md` — _resp.: Guilherme, 04/11/2026_
- [x] `LICENSE` MIT (titular: Guilherme Lobo de Carvalho) e seção "Fonte dos dados" no `README.md` — _resp.: Guilherme, 04/11/2026_
- [ ] Conferir no Data.Rio a licença dos dados do 1746 e trocar o "a definir" do `README.md` — _resp.: Guilherme_
- [ ] Consulta jurídica antes de publicar o site (licença dos dados, risco de identificar pessoas, texto da página de método) — _resp.: Guilherme_
- [ ] Credencial do BigQuery, só leitura: criar num environment restrito à `main` (Settings › Environments), nunca num Secret solto, quando a primeira ferramenta de coleta precisar. Nenhuma credencial criada até agora — _resp.: Guilherme_

### 2. Ferramentas

A ordem da lista é a prioridade: o de cima é o próximo. O gestor mantém.

- [ ] Agregador: totais por rua e por quadrado de 100 m — issue #7; código e testes no pull request, falta a revisão do gestor e o teste manual. O valor do mínimo fica a definir até a consulta jurídica — _resp.: Guilherme_
