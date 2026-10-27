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

- `dist/GuildIdleManager-DEV.zip` — SHA-256 `9B5AACC55E0EC5556B5DEAFE314D704F4174251A79700318593A649F0D2ACF67`.
- `dist/GuildIdleManager-DEV-Setup.exe` — SHA-256 `531A2E6D1A1367C94F0B1D8537865C4FF337C86BF241B30B5722FDDC23569D7A`.

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
| Installed frozen application | Final Setup installed under `%TEMP%\gim-installed-final-narrow-1732826dd20846a3ac97fc0260e3bf16\Programs\GuildIdleManager` with a temporary `LOCALAPPDATA`; the installer’s offline smoke passed. The elevated GUI opened, created a temporary campaign, dismissed the tutorial invitation, opened the compact menu, navigated to Missions and Overview, and returned to the campaigns page. Earlier installed GUI checks also renamed a campaign and created a backup. |
| Full test suite | `APP_MODE=desktop`, `DATABASE_URL=sqlite:///:memory:`; 64 tests passed, with one opt-in native runtime test skipped in the suite (the native test was run separately twice above). |
| Web-mode smoke | Ran the original web project with its working `.venv`, `APP_MODE=web`, and a temporary SQLite file/schema created from model metadata. `/`, `/docs`, and `/static/css/main.css` all returned HTTP 200; the local server shut down cleanly. Alembic migration against SQLite was not used: the web migration chain contains PostgreSQL-only `ALTER COLUMN ... DROP DEFAULT`, which SQLite rejects. No PostgreSQL connection or real save was used. |
| Final package | Setup completed first install in the isolated profile; marker was present and installer smoke passed. `dist/GuildIdleManager-DEV.zip` and `dist/GuildIdleManager-DEV-Setup.exe` hashes are recorded below. |

The final installed GUI was captured at 1920×1032 and at the narrowest reached window size of 747×593. The minimum-size dashboard has no horizontal scrollbar; the header remains compact and “Campanhas” is fully visible. The compact menu opened and routed to Missions. Missions and the campaigns manager were also inspected at the same narrow size and showed no horizontal overflow.

- [desktop-dashboard.jpg](qa/desktop-dashboard.jpg) — final frozen GUI, desktop size.
- [desktop-minimum.jpg](qa/desktop-minimum.jpg) — final frozen GUI, narrow size, scrolled to the top.
- [desktop-navigation-minimum.jpg](qa/desktop-navigation-minimum.jpg) — compact navigation expanded at narrow size.
- [desktop-missions-minimum.jpg](qa/desktop-missions-minimum.jpg) — Missions at narrow size.
- [desktop-campaigns-minimum.jpg](qa/desktop-campaigns-minimum.jpg) — campaigns manager at narrow size.

The frozen installed GUI and source runtime pass in the elevated interactive host. The restricted shell result remains an environment-specific limitation because WebView initialization stopped before page navigation.
