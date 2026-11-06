# Lista de classificação dos tipos e subtipos do 1746

- **O que é:** `grupos_subtipos_1746.csv`, o catálogo de pares tipo/subtipo do 1746, cada um num grupo. Colunas `grupo;tipo;subtipo;motivo`, separadas por ponto e vírgula, em UTF-8. São 5.160 linhas, sem contagens de chamados: só o catálogo de tipos, que é público.
- **De onde veio:** preparada pelo gestor com o responsável (Guilherme) em 06/11/2026, a partir dos tipos e subtipos da tabela `datario.adm_central_atendimento_1746.chamado`. Pedido na issue #26.
- **Para que serve:** a coleta (`src/coleta.py`) lê esta lista e só soma no mapa os chamados do grupo `publico`, por privacidade (ver `decisoes.md`, 06/11/2026).
- **Os grupos:**
  - `publico` (690 linhas): problema em espaço ou serviço público. Só este entra no mapa.
  - `denuncia` (770): pode apontar vizinho, carro, obra, estabelecimento ou imóvel.
  - `pessoal` (723): pedido da própria casa ou da pessoa.
  - `sem_lugar` (1.739): informação, tributo ou documento.
  - `a_revisar` (1.238): ainda sem classificação final. Fica fora do mapa até ser classificado.
- **Diferente do resto desta pasta:** esta lista é um arquivo de configuração vivo, e não um original intacto. Ela muda quando um par `a_revisar` for classificado ou quando aparecer um subtipo novo (o resumo da coleta lista os pares que não estão aqui). Toda mudança passa por uma issue e um pedido de revisão.
- **Como é comparada com a tabela:** sem os espaços do começo e do fim, dos dois lados (há tipos e subtipos com espaço no fim, como "Acessibilidade Digital "). Um par que só se repete por causa desses espaços conta uma vez.
- **Mudança ao entrar no repositório:** só o fim de linha, de CRLF (Windows) para LF, como o resto do repositório. O conteúdo é o mesmo.
