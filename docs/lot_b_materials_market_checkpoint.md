# Lote B — checkpoint de implementação

- Base fixada: `c1dc871db4d09f6f0212d059cc17b82a7e2c7b9e`.
- Branch local: `fix/lot-b-materials-market-economy`.
- Escopo: BUG-008, ML-024 e ML-027.
- DA: lido `docs/art_direction/LOT_B_MARKET_GATHERING_VISUAL_HANDOFF.md`; sprites existentes bastam.
- Guia do Jogo: atualizado no template canônico para alvo de coleta fixo, prazo por raridade/quantidade e cancelamento. Não há exportação Markdown no estado atual; ML-026 segue fora do escopo.
- Dados reais via código/testes: nenhum save ou campanha real foi acessado; os testes usam SQLite/loopback temporários. Nota fora do lote: uma janela InPrivate da aplicação ficou aberta durante um contexto anterior; a tela mostrou uma venda de 54 ouros como coletada e tesouro 8.785 → 8.839. Não foi possível determinar se a mudança foi causada pela interação nem verificar persistência do save; nenhum Setup foi aberto.
- Estado prévio preservado: `AGENTS.md`, `ML-BUGS.md` e untracked preexistentes.
- Baseline oficial: indisponível; `runtime/pipeline.ps1 command --name baseline` informa que `.pipeline/project.adapter.yaml` não existe. Baseline substituto direcionado: `tests.test_gathering_service`, `tests.test_market_max_quantity`, `tests.test_campaign_content_versioning` — 21 testes, 20 passaram e 1 falhou em `test_legacy_campaign_upgrade_backs_up_and_preserves_materialized_offers` (`cpu_completed` esperado `expired`), fora do escopo deste lote.

## Matriz de decisões BUG-008

As faixas reutilizam os oito intervalos de `BANDS`. Variantes com menos registros usam o estágio de progressão proporcional ao índice local; todos os registros de um estágio compartilham o desbloqueio e a raridade do estágio. A curva é por progressão local da família, nunca por índice global:

| Estágio | Faixa de guilda | Nível mínimo | Variantes (5 estágios) | Raridade |
|---|---:|---:|---|---|
| 1 | 1–20 | 1 | variante 1 da família | Comum |
| 2 | 21–50 | 21 | variante 2 da família | Incomum |
| 3 | 51–100 | 51 | variante 3 da família | Raro |
| 4 | 101–200 | 101 | variante 4 da família | Épico |
| 5 | 201–300 | 201 | variante 5 da família | Lendário |
| 6 | 301–350 | 301 | variante 5 da família | Mítico |

Famílias cobertas pelo seed: madeira, minério, pedra, couro, fibra, erva, carne, essência, gema, parte de criatura, relíquia, catalisador e insígnia. Postos de coleta existentes são madeira, minério, couro, fibra, erva, carne, essência, gema e relíquia. Famílias sem posto continuam alcançáveis por suas fontes existentes; este lote não promete que possam ser coletadas em um posto inexistente.

Respeitar templates administrativos: versão de conteúdo aditiva corrige somente registros cujo valor ainda coincide com a versão canônica anterior; alterações administrativas são preservadas. A atualização é idempotente, não reescreve inventário/histórico nem converte saves alterados pelo jogador, e mantém os IDs dos templates. A designação guarda FK opcional ao template alvo; durante a primeira atualização da campanha, linhas legadas recebem fallback determinístico por família/nível e congelam um único alvo, sem alternar raridades. Em saves importados com a versão atual e alvo nulo, o fallback ocorre no primeiro avanço e também congela.

## Matriz de decisões ML-024 / ML-027

- Cancelamento válido somente enquanto `now < ends_at`; em `now == ends_at`, o cancelamento é rejeitado e a venda está pronta para coleta. Estado muda condicionalmente de `in_progress` para `cancelled` na mesma transação da devolução, sem ouro/XP/estatística de venda. Exigir capacidade para devolver a pilha inteira; se insuficiente, rejeitar sem alterar o anúncio e preservar os itens reservados. Equipamento devolve a mesma instância liberando a referência `item_instance_id`.
- Coleta e cancelamento usam atualização condicional por guilda, ID, estado e prazo dentro da transação; dois cancelamentos simultâneos (e cancelamento versus coleta) têm apenas um vencedor. Cancelados saem dos espaços ativos e aparecem no histórico com ouro zero. Os `ends_at` já persistidos são snapshot e não mudam com esta regra.
- Duração: base em segundos por raridade `{common:10, uncommon:25, rare:60, epic:180, legendary:600, mythic:1200}` × quantidade, depois redução atual do Mercado, piso 5s. `tier` e `item_level` não participam.
- Interface usa tabela Raridade/Tempo-base; formulários/cards mostram prazo absoluto e estimativa calculada pelo servidor. Reutilizar confirmação nativa já presente.


## Validação final Lote B

- `tests.test_lot_b_materials_market`, `tests.test_gathering_service`, `tests.test_market_max_quantity`, `tests.test_salvage_balance`, o caso direcionado de `tests.test_stage5_runtime_validation` e o caso de versão atual de `tests.test_campaign_content_versioning`: 34 testes aprovados (inclui regressão da inicialização de estimativas após atualização parcial).
- `tests.test_desktop_http_smoke`: 1 teste aprovado em 51,8 s, com servidor/campanha loopback temporários. O runner deste Windows precisou de shim de inicialização temporário para contornar consulta WMI e carregar `cryptography` do ambiente desktop; nenhum arquivo de aplicação foi alterado por esse shim.
- `compileall` e `git diff --check`: aprovados.
- O teste legado `test_legacy_campaign_upgrade_backs_up_and_preserves_materialized_offers` permanece falhando com `cpu_completed` vs `expired`, reproduzindo a falha do baseline anterior ao lote.

- CR no commit `64f4954a2f32e7e7496926f84e3b75f3ad6ab550`: um achado P2 acionável sobre estimativas não inicializadas após `replaceGameContent`; corrigido no Lote B com chamada de inicialização e regressão JavaScript. A nova revisão ainda está pendente.
