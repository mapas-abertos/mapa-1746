# Decisões — a definir

> O **porquê** das escolhas do projeto. O que foi feito fica no `historico.md`; o andamento, no `Checklist_Projeto.md`. Decisão nova entra no topo.
>
> Formato: **Decisão em uma frase — DD/MM/AAAA.** O que motivou, opções consideradas e por que esta. Quem decidiu. Se revoga uma anterior, diga qual.

As decisões abaixo vêm do modelo P3 da mentoria. Para mudar uma delas, converse com o mentor e registre a nova decisão no topo.

- **Melhorias do modelo chegam por pull request do mentor, e não por fork — 04/11/2026.** Um fork de repositório privado depende do acesso ao modelo (sem ele, o GitHub apaga o fork), o "Sync fork" traria também os documentos do projeto, gerando conflito em toda atualização, e o Actions vem desligado. Cada repositório registra de qual versão do modelo nasceu; o mentor aplica só a diferença entre duas versões nas partes que vêm do modelo (`docs/atualizar_do_modelo.md`). Decidiu: mentoria (modelo P3).

- **Segredo barrado também no computador, antes do commit; Python numa `.venv`; Claude Code sem acesso ao `.env` — 04/11/2026.** O CI só acusa um segredo depois que ele já está no GitHub; a barreira local (`.githooks/pre-commit`) roda o mesmo `segredos.py` antes de cada commit. `requirements.txt` lista o que as ferramentas usam (vai para o GitHub e o CI instala); a `.venv` é onde isso fica instalado no computador (não vai). O `.claude/settings.json` libera os comandos de rotina e bloqueia a leitura do `.env` e da `dados/`; push, merge e o que muda o GitHub continuam pedindo confirmação. Melhoria do modelo percebida no uso vai para o Backlog com a origem "modelo P3". Decidiu: mentoria (modelo P3).

- **Operador no Sonnet médio por padrão, com escada de falha até o mentor — 04/11/2026.** Começar barato e subir só por motivo: Sonnet alto e Opus têm critérios escritos, e o nível sai da regra, sem anotação por issue. Antes de subir, o gestor confere se a issue está clara, porque boa parte das falhas é pedido mal definido. São 2 tentativas por nível (Sonnet médio, Sonnet alto, Opus) e, depois, suporte do mentor. Queda técnica não conta como falha. O gestor fica no Opus médio, e alto ao revisar pull request feito no Opus ou que mexe no CI. Decidiu: mentoria (modelo P3).

- **Etiquetas em português, criadas por workflow, e regra de quem pega e quem fecha cada issue — 04/11/2026.** Com issues em paralelo, sem regra de andamento dois sub chats podiam pegar a mesma issue. Cinco etiquetas: tipo (`pedido`, `defeito`, `suporte`) e situação (`em andamento`, `aguardando responsável`); as padrão do GitHub saem para não confundir. Defeito ganhou formulário próprio e não marca o mentor, porque é trabalho do gestor e do operador. Prioridade sem etiqueta: a ordem do checklist. As etiquetas nascem num workflow rodado à mão, uma vez, porque o passo manual já tinha sido esquecido no próprio modelo. Se o sub chat não puder ser aberto, o gestor roda a issue num subagente, como plano B. Decidiu: mentoria (modelo P3).

- **Dois papéis de chat: gestor (Opus) e um sub chat operador (Sonnet) por issue; quem faz registra — 04/11/2026.** O gestor guarda a visão do projeto e revisa; o operador começa cada issue com o contexto limpo e gasta menos. Sub chat, e não subagente, porque tarefa longa precisa de um chat próprio que sobreviva à sessão principal. O registro (histórico, mapa, checklist) é de quem fez a mudança, no mesmo branch. Issues podem andar em paralelo; conflito no histórico ou no mapa se resolve mantendo as duas entradas, e o CI confere. Decidiu: mentoria (modelo P3).

- **Teste primeiro (TDD), escrito pelo Claude a partir do "Quando está pronta" da issue — 04/11/2026.** O responsável não precisa ler código para saber se a ferramenta faz o que pediu: aprova o teste, explicado em linguagem simples, e o CI confere toda vez. O que não dá para testar automaticamente vai para o teste manual do pull request. Decidiu: mentoria (modelo P3).

- **O CI não impede o merge; a regra do `CLAUDE.md` impede — 04/11/2026.** No GitHub Free, com repositório privado, não há branch protegido, então o GitHub aceita merge com o CI vermelho. Opções: disciplina (escolhida), org Team (pago por usuário) ou repositório público (expõe o código). Para compensar, versão e deploy só saem depois do CI verde na `main`. Decidiu: mentoria (modelo P3).

- **Versão pela data do merge (`v2026.11.04`, `.2` se houver outra no dia), criada sozinha — 04/11/2026.** Não pede ninguém para escolher número. A alternativa, versão semântica escolhida por etiqueta no pull request, era um passo a mais. Decidiu: mentoria (modelo P3).

- **Deploy num arquivo próprio (`deploy.yml`), chamado pelo `versao.yml`; destino a definir — 04/11/2026.** O destino depende do que a ferramenta faz e da TI. O arquivo já existe para o encaixe não mexer no resto. Fica separado e chamado direto porque uma tag criada pelo próprio Actions não dispara outro workflow. Decidiu: mentoria (modelo P3).

- **Originais em `_referencias/`, que vai para o GitHub; o que não pode ir fica em `dados/` — 04/11/2026.** Os originais explicam de onde veio o que foi feito. Planilhas, documentos e bancos só entram em `_referencias/`; chaves e `.env` não entram em pasta nenhuma; acima de 5 MB fica fora. Decidiu: mentoria (modelo P3).

- **Clone do repositório em `C:\repos\`, fora da pasta sincronizada com a nuvem — 04/11/2026.** OneDrive, Google Drive e SharePoint podem corromper a pasta `.git` ao sincronizar. O GitHub já é o backup do código. Decidiu: mentoria (modelo P3).
