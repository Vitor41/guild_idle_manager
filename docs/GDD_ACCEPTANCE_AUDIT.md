# Auditoria de aceite da campanha desktop offline

Base: `GDD_DESKTOP_OFFLINE.md`, principalmente as seções 3 a 9 e 13. Esta matriz distingue evidência direta (`Comprovado`) de cobertura parcial (`Parcial`). Nenhum `Parcial` autoriza fechar a branch. O relatório detalhado de QA e as capturas estão em `WORK3_QA_DESKTOP.md` e `qa/`.

| Critério do GDD | Estado | Evidência atual / lacuna |
| --- | --- | --- |
| Janela própria, sem URL, navegador ou console | Comprovado neste host | Smoke opt-in `tests/test_desktop_runtime.py`; capturas da instalação em `qa/desktop-dashboard.jpg` e `qa/desktop-minimum.jpg`. Não substitui outro Windows. |
| Funciona sem login, PostgreSQL e `.env` | Comprovado neste host | Rotas de auth/admin e `SessionMiddleware` excluídos no modo desktop em `app/main.py`; smoke congelado SQLite/Alembic e inspeção do ZIP. |
| Funciona sem internet | Parcial | Assets e manifestos locais; busca estática sem dependência remota; smoke de pacote local. Falta execução com rede efetivamente desconectada em Windows limpo. |
| Duas campanhas isoladas, criar, retomar e persistir | Comprovado | `tests/test_campaign_service.py::test_two_campaigns_create_open_and_persist_in_isolation`; runtime nativo cria, abre e retorna ao gerenciador. |
| Fechar e reabrir sem perda ou conclusão antecipada | Comprovado neste host | `tests/test_desktop_runtime.py`, `tests/test_clock_guard.py`, testes de coleta manual; QA nativa de missão, Masmorra e Mercado. |
| Gameplay end-to-end da seção 13 | Comprovado neste host | `WORK3_QA_DESKTOP.md` e capturas `qa/work3-*.jpg`: mercenário, missão e loot de sucesso/falha, equipamento, construção, Masmorra/Chefe, Mercado, Docas, profissão, forja/desmontagem/refino, progresso, conquista e Codex. |
| Timers e backend como fonte de verdade | Comprovado | Matriz transacional `tests/test_campaign_service.py`; HTTP com timers ativos em `tests/test_desktop_http_smoke.py`; correção UTC em `app/core/time.py` e serviços. |
| Conteúdo versionado, sem re-seed em cada abertura | Comprovado | `app/services/campaign_service.py` aplica `apply_initial_campaign_content` apenas ao criar; teste de reabertura e conteúdo em SQLite. |
| Interface PT-BR e nova identidade visual offline | Parcial; gate visual reprovado pela DA | Sprites e ilustrações locais aparecem nas capturas nativas; `tests/test_desktop_art.py` verifica manifesto/sprite. Porém `app/static/css/main.css` ainda usa a paleta marrom e a tipografia anteriores. A DA comparou capturas instaladas com `docs/art_direction/DESKTOP_VISUAL_SYSTEM.md` e `design/preview/operations-desktop.png`: faltam paleta teal, hierarquia do salão, tratamento das Masmorras e revisão da janela mínima. A iconografia sozinha não cumpre o GDD §7.1. |
| Backup, exportação, importação e integridade | Comprovado por testes | `tests/test_campaign_service.py` cobre ciclo de vida, `PRAGMA integrity_check`, restauração e saves incompatíveis; diálogos da bridge ficam fora do HTTP. A passagem manual nativa dessas operações é menos extensa que a de gameplay. |
| Migração de save antigo com backup, mensagem e recuperação | Pendente | Testes cobrem backup antes de migration e restauração automática ao falhar. Falta aviso de sucesso ao jogador na abertura; ajuste solicitado ao DEV. |
| Atualização/reinstalação preserva saves | Comprovado neste host | `tests/test_desktop_installer.py` e Setup em `%LOCALAPPDATA%` temporário: update gerenciado preserva sentinela de saves. Falta segundo Windows. |
| Checkout DEV reflete edições sem reinstalar | Comprovado | `Iniciando_jogo_dev.bat`, `docs/DEV_DESKTOP.md`; janela pywebview executa checkout e `Ctrl+R` recarrega Jinja/CSS/JS sem cache. |
| Idle somente com app fechado; mínimo, teto, duplicidade | Comprovado | `tests/test_clock_guard.py` cobre sessão aberta, saída limpa, mínimo, teto de 8h e crédito único. |
| Rollback/salto de relógio, crash e âncora corrompida | Comprovado por testes | `tests/test_clock_guard.py` injeta relógio, testa high-water mark, monotônico, rollback, salto e recuperação sem crédito retroativo. |
| Limite honesto da proteção local documentado | Comprovado | Seção 6.2 do GDD e `docs/DEV_DESKTOP.md`; não se promete anti-cheat inviolável. |
| Regressão web e transações SQLite | Comprovado neste host | Suíte independente: 67 testes, zero falhas, um smoke nativo opt-in passado separadamente; smoke web `/`, `/docs`, CSS; matriz de serviços em `WORK3_QA_DESKTOP.md`. |
| Instalador limpo sem Python/PostgreSQL/rede | Parcial | ZIP/Setup e smoke offline congelado passaram em perfil local temporário, sem `.env` e com `PATH` limitado. Falta instalação e inicialização em outro Windows limpo, sem Python/PostgreSQL e com rede desligada. |
| Pacote sem segredos, contas de teste, saves ou logs | Comprovado por inspeção | Entradas do ZIP examinadas; não há `.env`, saves, logs, testes, `.git` ou `.aws`. Perfis de QA são temporários e não fazem parte do pacote. |
| QA declara lacunas e branch permanece aberta | Comprovado | `WORK3_QA_DESKTOP.md`, `REVIEW_GATES_DESKTOP.md`; branch `feature/desktop-offline`, sem merge. |

## Gates pendentes

1. Aviso visível e testado de migração bem-sucedida de save antigo, com pacote reconstruído.
2. Integração da nova identidade visual nas telas reais, com prioridade para tokens de cor, tipografia/hierarquia do salão, Masmorras e responsividade mínima; depois, nova aprovação da DA e revisão textual PT-BR das telas e descrições geradas.
3. Instalação e smoke em outro Windows 10/11 x64 limpo, sem Python/PostgreSQL e sem rede, incluindo abertura de campanha e persistência após reinício.

Até esses gates passarem, o GDD não está aceito integralmente. Não fechar nem integrar a branch.
