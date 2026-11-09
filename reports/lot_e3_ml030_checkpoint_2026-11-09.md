# Checkpoint DEV — E3 / ML-030

## Base, estado e preservação

- Branch: `feature/lot-e3-ml030-multi-bonus`.
- Base aprovada: `2144fe302d3835e8594650e65486a1f36caec923` (E1; ML-029 E2 não integrado).
- Checkout único: `C:\Users\vitor\Guild Idle Manager\App GIM`; nenhuma worktree temporária E3 permanece.
- `AGENTS.md`, `ML-BUGS.md` e os 307 caminhos locais não rastreados estavam presentes antes do E3 e foram preservados. O texto ML-030 em `ML-BUGS.md` está em alteração local do usuário e permanece sem edição/staging; os critérios abaixo foram lidos dessa cópia para orientar o trabalho.
- Saves reais, credenciais, branch E2, worktrees antigas, instalação, build, push, PR e release não foram usados.

## Escopo e pontos observáveis

O ML-030 pede auditoria completa dos bônus de equipamentos; geração por raridade de 1–2/2–3/3–4/4–5/5–7/8–10 tipos distintos (Comum a Mítico), com pontos normais no mesmo intervalo numérico; persistência de múltiplos bônus na instância; FORTE FOR/VIT/AGI/INT apenas em Lendário/Mítico, de 10–20 pontos, com as garantias Lendário máximo 7 → ≥1 FORTE, Mítico → ≥2 e Mítico máximo 10 → os quatro. Repetir bônus ao renderizar/equipar é proibido. A soma FORTE acrescenta-se ao mesmo atributo normal sem duplicar cálculo. Não recalcular instâncias já gravadas nem substituir configuração administrativa por seeds.

Superfícies a comprovar: Inventário e detalhe, equipamento selecionado/equipado, loot/histórico, Ferreiro/refino/desmontagem, Mercado, Docas e Guia visível/exportado. A regra de FORTE e sua badge devem vir dos bônus persistidos; ofertas ainda não materializadas não podem prometer bônus sorteados.

## Auditoria inicial

No baseline, `GuildItemInstance` guarda apenas um par `rng_bonus_attribute`/`rng_bonus_value`; o único construtor físico é `create_item_instance()` em `item_repository.py`. A geração central está em `create_equipment_instance_from_template()` e é usada por recompensas de conquistas, Docas, fabricação, drops de missão e drops de masmorra/chefe. Refino altera `upgrade_level` da instância existente. Atributos gerados entram no cálculo por `equipment_service.py`; Inventário e seletor do mercenário são os únicos templates encontrados que leem diretamente o par legado. A auditoria detalhada por origem/superfície será completada após rastrear snapshots de resultado, administração e os templates do Guia.

## Baseline pré-edição

- Verificador do pipeline: `pipeline.ps1 command --name baseline --project-root <checkout>` retornou `ENOENT` porque a base E1 não contém `.pipeline/project.adapter.yaml`.
- A suíte integral foi tentada com o comando do README (`APP_MODE=desktop`, `DATABASE_URL=sqlite:///:memory:`, `unittest discover`). Sem ajuste local, Python encerrou por exceção fatal WMI `0xc06d007e` em `platform.machine()`. Com `sitecustomize.py` temporário dentro de `.lot-e3-test-tmp/evidence-runtime` (mapeia apenas a detecção de arquitetura para `AMD64`), iniciou, mas apresentou problemas baseline e ficou sem progresso em `test_market_estimates_initialize_for_replaced_game_content` (`test_desktop_art.py`). Foi interrompida por Ctrl+C após a orientação do usuário; sem resumo total.
- Falhas/erros observados nessa execução parcial: `test_legacy_migration_reactivates_only_required_meat_gathering_material` (FAIL), `test_campaign_listing_explains_unknown_migration_revision` (ERROR), `test_clock_guard` (ERROR). Outros casos após o ponto de interrupção não foram avaliados.
- Suíte focal executada antes da alteração: 7 testes; 6 passaram. Passaram: `test_four_unique_slot_rewards_create_one_rng_instance_each_and_retries_do_not_duplicate`, os três cenários de crafting/loot/equipamento no `test_stage5_runtime_validation.py`, e os dois testes de `test_guide_routes.py`. Falhou o baseline `test_legacy_campaign_upgrade_backs_up_and_preserves_materialized_offers`: esperava `migrated_old_offer.status == "expired"`, recebeu `"cpu_completed"` (linha 597). Este desvio já ocorre na base E1 e é alheio à implementação ML-030.

## Auditoria final e decisões de balanceamento

- **Origens de atributo:** bônus-base ficam em `item_templates.bonus_*`; valores aleatórios de saves antigos estão em `guild_item_instances.rng_bonus_*`; novas rolagens vêm exclusivamente de `create_equipment_instance_from_template()` e são persistidas em `guild_item_instances.bonus_rolls`. `create_item_instance()` não possui outro chamador de criação física.
- **Caminhos que chegam ao gerador central:** drops/recompensas de missão, masmorra e chefe, compra materializada nas Docas, receitas de fabricação e recompensas de conquistas. Taverna gera mercenários e não cria equipamento. Refino altera o item existente (+1 em Força por nível), sem chamar o gerador e sem modificar o snapshot de bônus. Seeds/configuração de catálogo criam templates; admin continua editando bônus-base. Os campos RNG antigos do template ficam preservados e não governam novas instâncias; a tela administrativa explica essa precedência e não permite alterá-los acidentalmente.
- **Saves:** migration aditiva `0a1b2c3d4e5f` cria `bonus_rolls` JSON com `[]`. Valores legados de `rng_bonus_attribute/value` permanecem intocados. Quando a lista está vazia, leitores e cálculos usam o par antigo uma vez; quando há lista, o par antigo apenas espelha o primeiro normal e não é somado outra vez.
- **Quantidade e composição:** Comum 1–2 normais; Incomum 2–3; Raro 3–4; Épico 4–5; Lendário 5–7 incluindo exatamente um FORTE; Mítico 8–10 incluindo 2–4 FORTE. Normal: pontos iguais ao intervalo da raridade; FORTE: +10–20. Mítico com 10 tipos contém os quatro FORTE. Tipos são únicos como pares `(kind, attribute)`; normal e FORTE no mesmo atributo são tipos distintos que somam.
- **Piso/teto de poder aleatório (bônus novos apenas), segundo `calculate_power_score`:** Comum 1–3; Incomum 3–5; Raro 5–10; Épico 10–13; Lendário 21–41; Mítico 41–83. O teto de cada raridade não supera o piso da imediatamente superior. A geração assegura FOR normal; categorias com mais bônus usam os atributos de peso de combate antes de Sorte, e FORTE inclui FOR. Para garantir a separação Lendário/Mítico, Lendário fica em exatamente um FORTE; Mítico sempre inclui FORTE FOR. Isso é mais restrito que o mínimo do cartão e evita que rolagens Lendárias de quatro FORTE ultrapassem o piso Mítico.
- **Base dos templates e comparações:** auditoria do catálogo seed E1 encontrou 1.706 equipamentos ativos em 974 grupos `(nível mínimo, slot)`. Antes do ajuste, 24 pares de grupos Comum/Incomum, 12 Incomum/Raro e 2 Raro/Épico tinham inversão de poder-base; pior diferença +5, +5 e +3. Há 115, 65 e 15 grupos com raridades adjacentes correspondentes, respectivamente. Não há pares de templates Épico/Lendário ou Lendário/Mítico nesses grupos.
- **Correção para novas instâncias:** templates e valores administrativos nunca são regravados. A cada criação de raridade superior, calcula-se o maior extremo de poder da raridade inferior já existente no mesmo nível/slot; se o piso atual não o alcançar, soma-se somente a diferença ao `bonus_power` da nova instância. O ajuste máximo observado foi +5 em 57 instâncias candidatas. Nova simulação com base + rolagens encontrou zero inversões nos 195 grupos adjacentes comparáveis do catálogo seed. Como o refino acrescenta +1 em cada nível, comparar itens no mesmo nível de refino preserva a mesma ordem. Sem pares no catálogo, só se valida a faixa teórica do bônus aleatório.
- **Superfícies:** inventário usa chips FORTE com estrela e diálogo quando há mais de seis bônus; ficha equipada mostra quantidade/tipos e o seletor mostra todas as rolagens em texto; resultados de loot exibem o snapshot materializado via `format_equipment_bonus`; Ferreiro mostra FORTE no refino e a lista ordenada das instâncias e bônus que a desmontagem pode consumir; Mercado distingue instância anunciada de oferta ainda não gerada; Docas não anunciam bônus sorteados; Guia visível e `/guide/export.md` compartilham o mesmo HTML com faixas, soma e garantias. Sprite DA foi copiado e registrado como `bonus-strong-star`, fora do mapa de raridade.

## Testes e evidências E3

- `test_ml030_equipment_bonus_rules.py`: 6 passaram — geração/garantias/uniquidade e faixas, extremos de poder por raridade, snapshot não mutável, migration preservando o par antigo, round-trip JSON e piso baseado em atributos-base sem reescrever templates. O piso também é exercitado com os três pares de slot legado/canônico: `weapon/main_hand`, `armor/chest` e `accessory/ring`. A verificação de extremos enumera combinações possíveis de contagem/atributos e demonstra as bandas acima.
- Fluxos focados: 3 passaram — fabricação/refino/mercado/desmontagem, drop de masmorra, drop de missão equipado afetando a masmorra. Recompensa de conquista lendária: 1 passou e verifica 5–7 tipos, faixa normal Lendária, presença de FORTE, espelho legado e retenção dos campos RNG do template.
- `test_guide_routes.py`: 2 passaram; guia HTML e exportação Markdown/itens continuam sincronizados. `AdminFormCoverageTests.test_gameplay_forms_expose_all_editable_fields`: 1 passou.
- Suíte de integração `test_stage5_runtime_validation.py` foi tentada inteira, mas o primeiro teste concorrente reportou `ERROR` e a execução ficou sem progresso no seguinte. Os processos Python iniciados por essa tentativa foram encerrados. Após isso, os três testes focados acima passaram isoladamente. A suíte integral já havia parado no baseline pré-edição descrito acima; não foi repetida para evitar gastar mais tempo nos mesmos testes alheios.
- Não houve build, instalação, push, PR, merge, release ou acesso a saves reais.

## Reteste independente

O CR identificou um P2 na consulta de templates equivalentes: os aliases legados (`weapon`, `armor`, `accessory`) não eram incluídos ao comparar nos slots canônicos. A consulta foi corrigida para buscar ambos os nomes armazenados. Os seis testes ML-030 passaram novamente e a simulação completa do catálogo (1.706 templates, mesmos 195 pares comparáveis) repetiu zero inversões após correção; os três pares de aliases também passaram no teste integrado.

## Handoff

Esta implementação precisa de revisão independente do CR antes de integrar. O cartão `ML-BUGS.md` e `AGENTS.md` continuam com alterações do usuário e não entram no commit E3.
