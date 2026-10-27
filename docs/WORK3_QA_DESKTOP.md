# Work 3 QA — desktop offline

## SQLite gameplay transaction matrix

`tests/test_campaign_service.py::CampaignServiceTests.test_two_campaigns_create_open_and_persist_in_isolation` creates two temporary campaign databases, opens the first, runs these service transactions, then reopens both saves and checks that their state remains isolated. The QA fixture supplies resources through campaign inventory and guild resources; it does not alter a user save.

| System | Transaction evidence |
| --- | --- |
| Mercenary / tavern | Hires two mercenaries from apprentice previews; checks them after campaign reopen. |
| Mission and loot | Starts a mission, rejects collection before its timer, manually collects a forced success, then forces a failed run and checks its outcome. |
| Item and equipment | Verifies mission material inventory, creates a chest equipment instance, and equips it to a mercenary. |
| Buildings | Upgrades housing, tavern, scouts, market, docks, and blacksmith using the real material-cost transaction. |
| Dungeon and boss | Starts and manually claims a dungeon and the introductory boss; rejects early collection for both timers. |
| Market | Lists an owned material, rejects collection before sale completion, advances the fixture timer, and collects the sale. |
| Profession | Starts training, rejects early completion, advances the timer, and verifies the mercenary receives the profession. |
| Docks | Creates a local merchant rotation, purchases a stocked offer, and checks that stock decreases. |
| Blacksmith | Supplies the recipe materials in the temporary inventory and crafts a rotating recipe. |
| Progression | Grants guild XP and checks the persisted guild level after reopening. |
| Achievement and Codex | Evaluates achievement progress, synchronizes unlocked references, and loads Codex entries from SQLite. |

Desktop HTTP smoke also renders dashboard, tavern, mercenary list/detail, missions, dungeons, inventory, buildings, market, blacksmith, and tutorial pages against the temporary campaign. It fetches a semantic sprite URL from the rendered HTML and checks for HTTP 200/PNG. Tutorial start and confirmation preference mutations are verified over loopback.

## Packaging evidence

The packaged executable's `--smoke` path verifies that the frozen app can apply Alembic migrations to a temporary SQLite save, create and list a campaign, load the local mercenary-name catalog, and read the desktop art manifest. It runs without a console window and does not use network services.

Installer regression tests cover refusal of a foreign install directory and a junction target. The current bundle and install script passed first install and managed update tests under a temporary `%LOCALAPPDATA%`; an out-of-install saves sentinel remained unchanged and an obsolete app file was replaced. The current ZIP is `dist/GuildIdleManager-DEV.zip`.

Current artifacts from the final build:

- `dist/GuildIdleManager-DEV.zip` — SHA-256 `728E307C6BD7ACAA1106C9D047E914413BA70E2ECD79E93C5994DDE88A8F2198`.
- `dist/GuildIdleManager-DEV-Setup.exe` — SHA-256 `6684FF82326017A33EF1D55BEC99E5ACC601385F30304DCDD390E7A285C45CC9`.

IExpress returned exit code 0 before the Setup file appeared; the build script now waits up to 90 seconds for a stable output and verifies its PE header before moving it into `dist`. The final Setup passed isolated first install and managed update (`Start-Process -Wait`: exit 0 for both) with a temporary `%LOCALAPPDATA%`. The saves sentinel remained unchanged, the marker identified the DEV install, and a planted obsolete app file was removed. All 856 installed app files had hashes identical to the current packaged bundle. The Setup now matches the final ZIP used by the build script.

## Native window, return flow and visual QA

### Fixes

The return form and the tutorial invitation used native HTML POSTs. In the frozen WebView, those POSTs omitted `Origin`, so the existing server-side loopback Origin check correctly rejected them with HTTP 403. The desktop client now intercepts only campaign return and tutorial invitation forms, sends same-origin `fetch` requests with same-origin credentials, checks the expected redirect, then navigates to the confirmed destination. Server-side Origin validation remains enabled and unchanged.

The frozen launcher healthcheck now uses `http.client.HTTPConnection` for its validated HTTP loopback URL. This avoids the frozen `urllib` path initializing TLS/proxy support before the local healthcheck.

At widths up to 980 px, the desktop shell uses a native `details/summary` navigation control. It is expanded by default at desktop widths and collapses to the labeled “Navegação” control at narrow widths. The small-window header reserves a fixed 86 px action column so “Campanhas” stays fully visible. The web-mode navigation retains its horizontal layout at narrow widths.

### Execution results — 2026-10-27

| Target | Context and result |
| --- | --- |
| Source native runtime | Two consecutive runs from `.venv-desktop`, with `APP_MODE=desktop`, isolated temporary data and the elevated interactive host: both passed campaign create, return-to-campaigns and clean window/server close (30.2 s and 23.2 s). |
| Source restricted shell | The native WebView did not initialize before page load in the restricted run. No campaign flow ran in that context. |
| Installed frozen application | Final Setup installed under `%TEMP%\gim-installed-final-narrow-1732826dd20846a3ac97fc0260e3bf16\Programs\GuildIdleManager` with a temporary `LOCALAPPDATA`; the installer’s offline smoke passed. The elevated GUI opened, created a temporary campaign, dismissed the tutorial invitation, opened the compact menu, navigated to Missions and Overview, and returned to the campaigns page. Earlier installed GUI checks also renamed a campaign and created a backup. The Work 3 package was subsequently reinstalled at `%TEMP%\gim-work3-final-QA-20261027\Programs\GuildIdleManager` and its current campaign list and gameplay pages were verified below. |
| Full test suite | `APP_MODE=desktop`, `DATABASE_URL=sqlite:///:memory:`; 67 tests passed and one opt-in native runtime test was skipped (the native test was run separately twice above). |
| Web-mode smoke | Ran the original web project with its working `.venv`, `APP_MODE=web`, and a temporary SQLite file/schema created from model metadata. `/`, `/docs`, and `/static/css/main.css` all returned HTTP 200; the local server shut down cleanly. Alembic migration against SQLite was not used: the web migration chain contains PostgreSQL-only `ALTER COLUMN ... DROP DEFAULT`, which SQLite rejects. No PostgreSQL connection or real save was used. |
| Final package | Setup completed first install in the isolated profile; marker was present and installer smoke passed. `dist/GuildIdleManager-DEV.zip` and `dist/GuildIdleManager-DEV-Setup.exe` hashes are recorded below. |

The final installed GUI was captured at 1920×1032 and at the narrowest reached window size of 747×593. The minimum-size dashboard has no horizontal scrollbar; the header remains compact and “Campanhas” is fully visible. The compact menu opened and routed to Missions. Missions and the campaigns manager were also inspected at the same narrow size and showed no horizontal overflow.

- [desktop-dashboard.jpg](qa/desktop-dashboard.jpg) — final frozen GUI, desktop size.
- [desktop-minimum.jpg](qa/desktop-minimum.jpg) — final frozen GUI, narrow size, scrolled to the top.
- [desktop-navigation-minimum.jpg](qa/desktop-navigation-minimum.jpg) — compact navigation expanded at narrow size.
- [desktop-missions-minimum.jpg](qa/desktop-missions-minimum.jpg) — Missions at narrow size.
- [desktop-campaigns-minimum.jpg](qa/desktop-campaigns-minimum.jpg) — campaigns manager at narrow size.

The frozen installed GUI and source runtime pass in the elevated interactive host. The restricted shell result remains an environment-specific limitation because WebView initialization stopped before page navigation.

## Work 3 native gameplay QA — 2026-10-27

### Defect fixes and regression coverage

SQLite returns timezone-naive timestamps for stored timers. Timer display preparation now treats these values as UTC and normalizes explicit offsets before comparing with the current UTC clock. The blacksmith page also skips timer preparation when no rotation end exists, so a guild with an unbuilt or newly built blacksmith can render normally.

Mission and dungeon cards now label their displayed values **Chance base** and explain the final chance rules. Standard missions and dungeons adjust the base chance using party bonuses and cap the result at 95%; long missions use their displayed fixed chance. A base chance of 100% therefore allows a failure on roll 96–100. The dungeon test now verifies the 95% cap and deterministically exercises roll 100; the RNG and resolution timing remain unchanged.

The loopback HTTP smoke test seeds active timer rows in a temporary SQLite campaign, then requests `/missions`, `/dungeons`, `/market`, `/professions`, `/class-change`, and `/blacksmith`. Each page returned HTTP 200 and rendered a `data-ends-at` timestamp with an explicit `+00:00` UTC offset. It also requests `/dashboard`, `/tavern`, and `/docks` with those timer states enabled and verifies their UTC offsets, alongside both chance explanations in the rendered mission and dungeon pages.

### Isolated native app results

The frozen DEV Setup was installed under a fresh `%TEMP%` profile and opened with a copied disposable QA campaign. No user save or normal installation was used. Manual flows completed through the native app UI: mission success and failure, profession completion, dock purchase, dungeon timer and failure collection, boss completion, guild progression, Codex claims, market sale start and collection, building upgrade, tavern hire, equipment purchase, and equipment equip. The dungeon failure was consistent with the 95% final chance cap; its previous “Chance 100%” label was misleading and has been corrected.

The forge and dismantling flows also passed through the native UI after seeding two recipe materials into the copied QA save only. The app crafted an Elmo Reforçado da Fortaleza for 80 gold, then started the first dismantling bench for 50 gold. Its 10-second timer reached “Pronto”; collecting returned 2 Minério de Mithril and showed the completion message. The fixture used no user save.

Equipment refinement also passed through the native UI in the same disposable save. The Forge level was set to 10 in the QA fixture to unlock the panel; refining the seeded Martelo Afiado da Fortaleza consumed 100 gold and 5 ore, raised its power from 5 to 6, and displayed the next cost as 200 gold and 10 ore. This check used the normal UI confirmation and transaction flow.

Selected native evidence:

- Mission [success](qa/work3-mission_success.jpg), [timer ready](qa/work3-mission_timer_ready.jpg), and [failure](qa/work3-mission_failure.jpg).
- Installed mission chance label and cap note [shown in the native app](qa/work3-chance_base_installed.jpg).
- Profession [timer ready](qa/work3-profession_timer_ready.jpg) and [completed](qa/work3-profession_complete.jpg).
- Docks [purchase](qa/work3-docks_purchase.jpg) and [equipment offer](qa/work3-docks_equipment_purchase.jpg); equipped result [here](qa/work3-equipment_equipped.jpg).
- Dungeon [timer ready](qa/work3-dungeon_timer_ready.jpg) and [failure result](qa/work3-dungeon_failure.jpg); boss [timer ready](qa/work3-boss_timer_ready.jpg) and [success](qa/work3-boss_success.jpg).
- [Progression](qa/work3-progression.jpg), Codex [claimable](qa/work3-codex_claimable.jpg) and [claimed](qa/work3-codex_claims.jpg).
- Market sale [started](qa/work3-market_sale_started.jpg), [ready](qa/work3-market_sale_ready.jpg), and [collected](qa/work3-market_sale_collected.jpg).
- Forge and dismantling [timer running](qa/work3-salvage_started.jpg), [ready](qa/work3-salvage_ready.jpg), and [materials collected](qa/work3-salvage_collected.jpg).
- Refinement [completed](qa/work3-refine_completed.jpg); the item shows +1 and power 6 after consuming the displayed first-level cost.
- Installed dungeon [chance base and 95% cap note](qa/work3-dungeon_chance_base_installed.jpg).

The source/dist/install hashes matched for the template during packaging verification. An earlier app instance retained its old template in memory; restarting from a fresh isolated Setup resolved this cache issue. The DEV Setup itself uses staged installation with rollback on failure. No active-updater scenario exists in this DEV flow, so no updater behavior was introduced or evaluated.

Final Work 3 package hashes are recorded above. The mission template SHA-256 is `BFC22E3C54CB9A59E1B6D66BE5957A28B19973C6DCC3A90D327F4CBCC2DF3ACF` in source, `dist`, and the fresh final QA installation. The packaged offline smoke wrote `PASS: SQLite, Alembic, conteúdo inicial, nomes e manifesto local` to its result file. The updated native installation displayed both **Chance base** labels and the 95% cap explanations.

Final regression run: 67 tests passed, one optional native-runtime test skipped. The loopback HTTP smoke, campaign isolation/chance-cap test, installer first-install/update tests, and three SQLite timestamp normalization tests passed.

### Save-version migration notice

The desktop open flow now carries a migration report separately from offline progress. In an isolated campaign with save version 1, opening it created a pre-migration backup, advanced the save to version 2, and returned the previous/current revisions without a filesystem path. The following dashboard response rendered an accessible `role="status"` notice with the version change and backup confirmation; the notice appeared once and remained separate from the idle-progress dialog. The loopback smoke verifies the API response, the saved pre-migration version, the rendered notice, and that no backup path is exposed.

The rebuilt Setup installed successfully in a fresh temporary profile. The frozen executable smoke again reported `PASS: SQLite, Alembic, conteúdo inicial, nomes e manifesto local`. Current package hashes are listed above.

### Identidade visual desktop — 2026-10-27

The GDD §7.1 visual system is implemented for the real desktop pages through `app/static/css/desktop-theme.css`, loaded only in desktop mode. The dashboard leads with the operation queue and keeps resource totals in one place; Missions and Dungeons use compact page introductions so the first operation is visible sooner. At narrow widths, the teal navigation remains a compact menu. The save label describes local campaign storage without implying a live autosave state. Gameplay rules and saves were not changed. `tests/test_desktop_art.py` checks that the desktop theme and markup do not leak into web mode; the HTTP smoke checks the stylesheet and compact introductions on real routes.

The final Setup was installed into disposable `%LOCALAPPDATA%` profiles. The installed executable, stylesheet, dashboard, Missions, and Dungeons templates match the corresponding final build files by SHA-256. The packaged `--smoke` result file reports `PASS: SQLite, Alembic, conteúdo inicial, nomes e manifesto local`.

| Final artifact | SHA-256 |
| --- | --- |
| `dist/GuildIdleManager-DEV.zip` | `728E307C6BD7ACAA1106C9D047E914413BA70E2ECD79E93C5994DDE88A8F2198` |
| `dist/GuildIdleManager-DEV-Setup.exe` | `6684FF82326017A33EF1D55BEC99E5ACC601385F30304DCDD390E7A285C45CC9` |
| Installed and packaged `GuildIdleManager.exe` | `4AEC56FE956209328796B97E4B3BC4CF9E1EE3FA8C8E55AB773958A5235DDB2A` |
| Installed and packaged `desktop-theme.css` | `093D29F79CB0F13150225370E9DCC99C61961D54C5A86FC7387ABB8A916D3F12` |
| Installed and packaged `dashboard.html` | `5ECC16C089BFE092B400C43C1ED92AA17D038AAD19FE47ADD7E1BA91E2365008` |
| Installed and packaged `missions/index.html` | `30DBD8ECD82D48F55238FF91E60A8B77F928D7A7B78BAEDD0A6CBC34ED0286EB` |
| Installed and packaged `dungeons/index.html` | `AE11B649BDDEBA379FC33078C508ACD39017CDC02BF139711096A10D0B02B2C0` |

The final visual-review screenshots are **not yet available**. After updating the disposable install, the app opened only in the elevated session, and the UI controller could not deliver clicks or keyboard input to that window. Per instruction, screenshots from an earlier process/package were not used as proof. This blocked capture of the installed dashboard, Missions, and Dungeons with an unlocked challenge, as well as Taverna, Mercenaries, and Inventory. The DA visual review remains pending until these final pages can be captured in an interactive elevated session.

### Final validation — 2026-10-27

| Check | Result |
| --- | --- |
| Full regression suite | 70 tests ran; 69 passed and one opt-in native runtime test was skipped. |
| Restricted-context source native smoke | Failed before page load: the WebView core was unavailable (`webview_page_loaded=false`, `bridge_ready=false`); no application flow ran. |
| Elevated source native smoke, diagnostics disabled | Passed; campaign create, return flow, and clean close completed (`Ran 1 test in 24.917s`). |
| Final Setup and installed package smoke | Setup installed in a disposable profile; installed file hashes matched the final package. The packaged offline smoke result file reports `PASS: SQLite, Alembic, conteúdo inicial, nomes e manifesto local`. |
| Final installed visual interaction | Blocked because the elevated app window did not accept UI input. No page-specific screenshot is claimed for this final package. |
