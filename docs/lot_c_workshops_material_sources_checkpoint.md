# Lote C — checkpoint de entrega

- Branch: `feature/lot-c-workshops-material-sources`.
- Base fixada: `b7806123f141fb57317e1f4514072c516cd0e0cd` (Lote B aprovado).
- Escopo: ML-022 e auditoria estruturada de fontes de ML-025. Busca/wiki/exportação visual do Guia permanecem no Lote D.
- Arquivos de usuário preservados: `AGENTS.md`, `ML-BUGS.md` e todo untracked preexistente; nenhum foi staged.
- DA: handoff lido em `docs/art_direction/LOT_C_SUPPLY_BATCH_VISUAL_HANDOFF.md`; sprites necessários já existem. Sem geração de arte.
- Baseline oficial: falhou antes da edição porque `.pipeline/project.adapter.yaml` não existe no checkout. Comando oficial executado via runtime do plugin. Substituto focal: `tests.test_workshop_service tests.test_supply_preparation tests.test_campaign_content_versioning` — 15 testes, 14 passaram e 1 falhou em `test_legacy_campaign_upgrade_backs_up_and_preserves_materialized_offers` (`cpu_completed` vs `expired`), já reproduzido no Lote B e sem relação com o escopo C.
- Auditoria de conteúdo em SQLite em memória, via seed v6 e receitas ativas: 448 materiais ativos, sendo 447 do catálogo massivo e o Kit da Oficina; 58 receitas ativas e 138 ItemTemplates exatos referenciados por receitas; 57 materiais ativos das famílias carne/erva elegíveis como insumos do Kit. No seed padrão, todas as 447 matérias-primas têm drops ativos de missão e de masmorra/chefe; 267 também têm oferta possível nas Docas, 332 são saídas exatas de algum posto de coleta em algum nível e 169 são saídas exatas de desmontagem. O Kit é produzido pela Oficina. Nenhum material ativo ficou sem fonte no seed padrão; portanto não há rota extra a balancear nem chance a inventar.
- Fonte dos dados: `_material_rows`/`run_massive_content_seed`, `CraftingRecipeMaterial`, `MissionTemplateItemDrop`, `DungeonTemplateItemDrop`, `MerchantOfferTemplate` + `DockOffer`, `gathering_service._material_template` e `salvage_service._select_salvage_material`/mapas de grupo.

## Decisões confirmadas pelo comportamento existente

- A Oficina continua com entrega automática no Armazém, alinhada ao endpoint atual de fabricação; não se cria fluxo novo de coleta nem de cancelamento.
- Ao iniciar, a receita debita uma vez 3 Carnes e 2 Ervas por Kit, inclusive entre tiers. O registro persistido guarda quantidade, template de saída e snapshots do custo e duração por Kit.
- A duração total é `5 × N` segundos. O resultado é creditado somente quando `now >= ends_at`, por transição condicional idempotente.
- Uma operação ativa ocupa a Oficina. Índice único parcial por guilda e transação/lock serializam cliques concorrentes. Capacidade de saída fica reservada durante a fabricação para impedir que outras recompensas causem overflow antes da conclusão.
- Catch-up de prazo não depende de horas online: ao reabrir e visitar a Oficina, o prazo persistido é conferido e uma conclusão vencida é creditada uma vez. O evento de timeout por si só não credita resultado.
- O manifesto para Lote D será gerado de tabelas/configurações ativas no momento, sem armazenar ID de campanha no retorno. `drop_chance` de missões/masmorras é base configurada na tabela ativa, condicional ao sucesso e sujeita aos modificadores efetivamente usados pelo serviço; não será apresentado como chance total incondicional. Docas não têm chance de drop: o manifesto distingue ofertas-template e estoque/preço de rotação da guilda como snapshot. Coleta é determinística por família/nível. Desmontagem segue mapeamento de equipamento e regra RNG uniforme 1–3 unidades por equipamento.

## Implementação e evidências

- ML-022: `SupplyWorkshopJob` persistido em migração aditiva; índice único parcial limita a uma produção ativa por guilda. Lote desconta os insumos em uma transação e registra quantidade, custos e duração; a duração é 5 segundos por Kit. A conclusão compara estado/prazo condicionalmente e reserva a capacidade durante o timer; repetição de visita não duplica a saída. A interface permite quantidade e máximo, mostra custo, tempo e progresso, e entrega automaticamente no Armazém.
- ML-025: `build_material_source_manifest` percorre receitas e fontes vivas e separa configuração possível de snapshot individual das Docas. Seed em SQLite em memória: 448 materiais, zero lacunas ativas; fontes registradas incluem missão, masmorra/chefe, Docas, coleta, desmontagem e Oficina. O contrato do Guia está em `docs/lot_c_material_source_manifest.md`.
- Teste focal (após CR): `python -m unittest tests.test_material_source_manifest tests.test_workshop_service -v` — 9 testes passaram (inclui lote, débito, prazo, idempotência, capacidade, ausência de fonte apesar de dependência e seleção exata no nível 350).
- Verificação sintática (`compileall`) passou para serviço, manifesto, modelo e rota.
- Smoke HTTP desktop não completou: o processo-filho isolado falhou ao importar `cryptography` (`ModuleNotFoundError`) antes de carregar a aplicação. Não foi alterado ambiente nem instalado pacote.
- Baseline oficial segue bloqueado pela falta de `.pipeline/project.adapter.yaml`; baseline focal anterior tem uma falha preexistente documentada acima.
- Próximo gate: revisão independente do hash local desta branch. Nenhum build, instalação, perfil/save real, push, PR ou merge foi executado.
- Reteste após revisão CR do primeiro commit: `workshop_input` saiu de `sources[]` e foi para `dependencies[]`; lacunas agora verificam somente rotas reais de obtenção. A coleta varre guild levels 1–350. Testes cobrem variante exata desbloqueada no nível 350 e variante input-only sem fonte, que deve aparecer em `gaps[]`.
