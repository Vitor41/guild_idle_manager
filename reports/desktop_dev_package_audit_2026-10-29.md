# Auditoria estática do pacote Desktop DEV — 29/10/2026

Escopo: leitura de `dist/GuildIdleManager-DEV`, artefatos ZIP/Setup, arquivos atuais e GDD §27. Nenhum pacote foi construído/instalado; nenhum dado de campanha ou artefato foi alterado/removido. Os JSONs brutos desta auditoria (inventário de arquivos e métricas) permanecem locais e não fazem parte deste commit; o resumo abaixo preserva as conclusões.

## Inventário e proveniência

- Diretório: 859 arquivos, 79,636,333 bytes; janela de timestamps 2026-10-27T03:18:29.025050Z a 2026-10-27T17:40:34.467745Z.
- `dist/GuildIdleManager-DEV.zip` — 56,764,050 bytes; UTC `2026-10-27T17:40:58.462868Z`; SHA-256 `e0755a8050f1677844ec177c0f3fce5cc19939934f0bcc5bd4fdfb6372b1dd6e`.
- `dist/GuildIdleManager-DEV-Setup.exe` — 56,348,672 bytes; UTC `2026-10-27T17:41:58.957246Z`; SHA-256 `bc4d70fafff3b880a28cb45cfe061541cab56889898ec39818afcc9987572080`.
- `dist/GuildIdleManager-DEV/GuildIdleManager/GuildIdleManager.exe` — 11,713,613 bytes; UTC `2026-10-27T17:40:32.965361Z`; SHA-256 `6d4b5adf6336773924eeff993912b1e85da66e110e92a8632b5a9dd69770719f`.
- `dist/GuildIdleManager/GuildIdleManager.exe` — 11,713,613 bytes; UTC `2026-10-27T17:40:32.965361Z`; SHA-256 `6d4b5adf6336773924eeff993912b1e85da66e110e92a8632b5a9dd69770719f`.
- `packaging/desktop/Install-Desktop-Dev.ps1` — 6,396 bytes; UTC `2026-10-27T20:54:31.773293Z`; SHA-256 `12cc87b0dd91b52fa738cc1ef1cd70d93ff135b0e60296b5fa794203a6b4a9fe`.
- `dist/GuildIdleManager-DEV/Install-Desktop-Dev.ps1` — 6,262 bytes; UTC `2026-10-27T03:18:29.025050Z`; SHA-256 `b81531fe59b5e5d6d2bec2b4e11a7098c214da5b679496a1add7837976b0f885`.
- `docs/DEV_DESKTOP.md` — 6,994 bytes; UTC `2026-10-27T20:54:31.714115Z`; SHA-256 `c9eb101515dda43559c7c9130cf65290aef3fd7073ca8dc80c6c6ea8108392e4`.
- `dist/GuildIdleManager-DEV/DEV_DESKTOP.md` — 6,894 bytes; UTC `2026-10-27T17:19:39.709619Z`; SHA-256 `3ca7b5a582098690a6d7ffc8b7c6a5b540c2d3e1c412cbff5badd8ca649809f7`.

O ZIP contém os mesmos 859 caminhos e tamanhos do diretório (sem diferença); isso verifica consistência de conteúdo por caminho/tamanho, não assinatura nem equivalência do Setup extraível. O executável dentro de `GuildIdleManager-DEV` coincide por SHA-256 com `dist/GuildIdleManager/GuildIdleManager.exe`. O inventário preserva hashes por arquivo. O pacote foi gerado em 27/10; o material de origem inclui alterações de 28–29/10, portanto esses hashes identificam a build antiga, não validam a branch atual. O executável não fornece versão do produto útil para atribuir commit/build; a versão do Python embarcado é metadado de runtime, não proveniência do PyInstaller.

## Diferenças concretas da branch atual

### `app/templates` — origem 47, pacote 45
- Ausentes: 2; conteúdos diferentes em caminhos comuns: 20; extras no pacote: 0.
- Ausentes: `gathering/index.html`, `regional/index.html`.
- Diferentes: `base.html`, `blacksmith/index.html`, `buildings/index.html`, `class_change/index.html`, `classes/index.html`, `codex/index.html`, `components/treasury.html`, `dashboard.html`, `desktop/campaigns.html`, `docks/index.html`, `dungeons/index.html`, `guide/index.html`, `home.html`, `inventory/index.html`, `market/index.html`, `mercenaries/detail.html`, `mercenaries/index.html`, `missions/index.html`, `professions/index.html`, `tavern/index.html`.
### `app/static` — origem 605, pacote 581
- Ausentes: 24; conteúdos diferentes em caminhos comuns: 8; extras no pacote: 0.
- Ausentes: `assets/desktop/evolution/illustrations/achievement-reliquary.webp`, `assets/desktop/evolution/illustrations/dimensional-portal.webp`, `assets/desktop/evolution/illustrations/gathering-worksite.webp`, `assets/desktop/evolution/illustrations/region-home.webp`, `assets/desktop/evolution/illustrations/regional-rebellion.webp`, `assets/desktop/evolution/illustrations/regional-vigil.webp`, `assets/desktop/evolution/manifest.json`, `assets/desktop/evolution/sprites/master_512/achievement-medal.png`, `assets/desktop/evolution/sprites/master_512/gathering-kit.png`, `assets/desktop/evolution/sprites/master_512/portal-gate.png`, `assets/desktop/evolution/sprites/master_512/rebellion-shield.png`, `assets/desktop/evolution/sprites/master_512/vigil-tower.png`, `assets/desktop/evolution/sprites/ui_128/achievement-medal.png`, `assets/desktop/evolution/sprites/ui_128/gathering-kit.png`, `assets/desktop/evolution/sprites/ui_128/portal-gate.png`, `assets/desktop/evolution/sprites/ui_128/rebellion-shield.png`, `assets/desktop/evolution/sprites/ui_128/vigil-tower.png`, `assets/desktop/evolution/sprites/ui_64/achievement-medal.png`, `assets/desktop/evolution/sprites/ui_64/gathering-kit.png`, `assets/desktop/evolution/sprites/ui_64/portal-gate.png`, `assets/desktop/evolution/sprites/ui_64/rebellion-shield.png`, `assets/desktop/evolution/sprites/ui_64/vigil-tower.png`, `css/desktop-evolution.css`, `js/evolution-dialogs.js`.
- Diferentes: `css/desktop-art.css`, `css/desktop-campaigns.css`, `css/desktop-theme.css`, `css/main.css`, `js/desktop-art.js`, `js/desktop-campaigns.js`, `js/desktop-security.js`, `js/main.js`.
### `app/data` — origem 1, pacote 1
- Ausentes: 0; conteúdos diferentes em caminhos comuns: 0; extras no pacote: 0.
### `alembic_python` — origem 26, pacote 21
- Ausentes: 5; conteúdos diferentes em caminhos comuns: 10; extras no pacote: 0.
- Ausentes: `versions/a6b7c8d9e0f1_add_campaign_economy_foundations.py`, `versions/b7c8d9e0f1a2_add_gathering_capacity_pause.py`, `versions/c0d1e2f3a4b5_expand_building_caps_to_100.py`, `versions/d7e8f9a0b1c2_add_regional_vigilia_snapshots.py`, `versions/e3f4a5b6c7d8_add_regional_events.py`.
- Diferentes: `env.py`, `versions/7bd557d33fad_add_run_multipliers_and_building_level_.py`, `versions/a1b2c3d4e5f6_add_offline_campaign_metadata.py`, `versions/b8c9d0e1f2a3_reconcile_material_treasury.py`, `versions/c27a934be410_add_expeditions_offline_and_market.py`, `versions/c9d0e1f2a3b4_add_blacksmith_salvage_jobs.py`, `versions/d4e5f6a7b8c9_add_massive_content_docks_and_tutorial.py`, `versions/d9e2cd17a723_add_tavern_classes_and_guild_progression.py`, `versions/e8f676d861ef_create_missions_timer_loot_admin.py`, `versions/ef8f80ce71ab_add_mission_display_order.py`.

As duas telas novas e `base.html`/JS/CSS atuais referenciam recursos de evolução ausentes (CSS/JS e imagens/manifesto), então as telas de Gathering e Regional e a nova direção visual não estão no pacote antigo. O arquivo de dados `mercenary_names.json` confere byte a byte. `alembic.ini` também confere byte a byte. Nas migrations Python, cinco arquivos da cadeia atual estão ausentes; dez arquivos comuns, incluindo `env.py`, diferem. Não afirmar que abrir a campanha com o binário antigo necessariamente corrompe dados: a incompatibilidade significa que ele não contém a cadeia atual e não foi testado com saves da branch de 29/10.

### Impressões digitais atuais de fontes-chave

A tabela abaixo permite comparar o timestamp/hash da origem atual; os itens ausentes no pacote estão listados na seção anterior.

| Fonte | Tamanho | Modificado UTC | SHA-256 |
|---|---:|---|---|
| `app/templates/base.html` | 16,489 | `2026-10-29T16:58:24.673693Z` | `10e5ca481036b33772802dd81a625b640d812af452b763f7b26a892b67d1e5cd` |
| `app/templates/gathering/index.html` | 3,929 | `2026-10-29T14:21:38.603541Z` | `fa0f6fdebf88197e9ba82809daad984808ddcde8bcf45df423b76cff614f0fac` |
| `app/templates/regional/index.html` | 29,377 | `2026-10-29T15:41:11.346656Z` | `60c4ebaab728307b9161f1405f8870cdd90b82b3b52e0b3366b82ff31b3f2a89` |
| `app/static/css/desktop-evolution.css` | 17,269 | `2026-10-29T04:01:47.735323Z` | `7d5c078759c43f6068d3e1478597865877b5dc7b69a1ea55dcd455e2cd569b10` |
| `app/static/js/evolution-dialogs.js` | 1,819 | `2026-10-29T16:02:28.019997Z` | `f61102b56030c874354e965251e163b8a9feb34447f598f0344de8f24c11e7ab` |
| `app/static/assets/desktop/evolution/manifest.json` | 3,032 | `2026-10-28T20:38:21.894005Z` | `de46cea3daba447640d40ca32e876ed7ff52d4f133325d44faa6197774c0c6d8` |
| `alembic/versions/d7e8f9a0b1c2_add_regional_vigilia_snapshots.py` | 19,312 | `2026-10-29T00:15:16.353242Z` | `8ce04b318ab68e3f99e10ebd6f89e6432c73d924d0918a9891c96c102c06841e` |
| `alembic/versions/e3f4a5b6c7d8_add_regional_events.py` | 6,351 | `2026-10-29T00:58:17.862634Z` | `95b64502bc9a4d1124f6a2ede8fdcf6278e3372fad429711f50ecc159438a01d` |
| `docs/DEV_DESKTOP.md` | 6,994 | `2026-10-27T20:54:31.714115Z` | `c9eb101515dda43559c7c9130cf65290aef3fd7073ca8dc80c6c6ea8108392e4` |
| `packaging/desktop/Install-Desktop-Dev.ps1` | 6,396 | `2026-10-27T20:54:31.773293Z` | `12cc87b0dd91b52fa738cc1ef1cd70d93ff135b0e60296b5fa794203a6b4a9fe` |

## Instalação, saves, restauração e remoção

- A origem atual e a cópia empacotada do instalador têm hashes distintos (ver JSON), mas ficam idênticas após normalizar CRLF para LF. A documentação DEV empacotada registra 70 testes (69 aprovados + 1 skip), e a fonte atual registra 72 (71 aprovados + 1 skip); ambas estão desatualizadas frente à suíte completa atual: 171 testes, 170 aprovados e 1 skip.
- O instalador de atualização usa staging e preserva a pasta de saves separada (`%LOCALAPPDATA%\GuildIdleManager\saves`); o teste automatizado existente usa marcador de texto, não um banco SQLite real, e cobre primeira instalação/atualização, mas não remoção.
- Não foi encontrado script de desinstalação nem fluxo automatizado de limpeza das instalações de teste. O build script remove e recria caminhos de saída; antes de confiar na proteção contra junctions/reparse points aninhados, testar em raiz descartável com sentinel fora dela. Não se verificou comportamento de remoção real.
- O GDD `GDD_DESKTOP_OFFLINE.md` mantém a pendência explícita de restauração automática após falha de migration. Isso está desatualizado frente ao código atual (`CampaignService` cria backup SQLite, tenta migration e restaura em falha) e ao teste `test_failed_migration_restores_original_schema_and_keeps_backup`. É divergência documental; ainda requer evidência no pacote final.
- Para §27, a build velha não prova migração de save com backup, falha/restauração, recursos PT-BR/visuais atuais nem não regressão da branch; os testes de serviços atuais não substituem smoke contra o artefato final.

## Recomendações verificáveis (não executadas)

1. Atualizar somente em pasta de trabalho temporária, sem substituir `dist/GuildIdleManager-DEV`: usar comando de build já documentado em `scripts/build_desktop_dev.ps1` com parâmetro de saída redirecionado para `%TEMP%\GIM-package-audit-<id>` (confirmar o parâmetro no script; se não houver, copiar o checkout para diretório temporário antes). Comparar o manifesto gerado, as duas telas, 24 estáticos e cinco migrations; repetir SHA-256 e conferir ZIP/Setup.
2. Na cópia isolada após a build, rodar `python -m unittest tests.test_desktop_installer.DesktopInstallerSafetyTests.test_first_install_and_managed_update_preserve_saves_and_replace_app_files -v`; o teste atual cobre primeira instalação/atualização, mas só com marcador de texto. Complementar com fixture SQLite real: sentinel, `PRAGMA integrity_check`, hash antes/depois; migração bem-sucedida e migração que falha no meio, verificando backup restaurável, schema/dados originais e save inalterado em atualização/rollback. A cobertura de serviço existente pode ser reexecutada com `python -m unittest tests.test_campaign_service.CampaignServiceTests.test_failed_migration_restores_original_schema_and_keeps_backup -v`. Manter `LOCALAPPDATA` e `TEMP` sob raiz temporária exclusiva e limpar só essa raiz validada após guardar logs e hashes.
3. Para limpeza segura, preparar uma instalação de teste sob uma raiz exclusiva temporária e sentinel fora dela; adicionar junction/reparse aninhado no diretório legado e validar a rotina de remoção contra caminho resolvido antes de qualquer remoção recursiva. Definir/documentar desinstalador que preserve saves; validar apenas nele, em fixture.
4. Fazer smoke do executável candidato com runtime Windows/WebView2 opt-in e conferir telas Regional/Gathering, manifest/assets locais e logs sem dados pessoais. Guardar hashes do pacote smoke testado.
5. Estado da suíte nesta revisão: a execução completa subsequente passou com 171 testes, 0 falhas e 1 skip. O teste do instalador passou isolado e dentro da suíte; a mensagem de thread da execução anterior não se reproduziu. A causa histórica segue sem comprovação, pois não foi preservada saída integral nem estágio do processo. Não foi adicionado retry. O skip foi o smoke nativo condicionado a `GIM_RUN_DESKTOP_RUNTIME_SMOKE=1`; detalhes e logs da execução atual estão na matriz de aceite.

## Relação com GDD §27

As lacunas do pacote deixam sem evidência os gates transversais de migração SQLite com save antigo e backup/restauração, logs diagnósticos, conteúdo visual/PT-BR e não regressão na build final. A implementação de backup/restauração tem cobertura no código/teste atual; falta reproduzir a matriz na build atualizada. Nenhum save real foi aberto ou alterado durante esta auditoria.
