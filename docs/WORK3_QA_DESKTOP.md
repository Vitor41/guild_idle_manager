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

**Setup gate remains open:** IExpress exited with code 1 during the current build, so there is no matching `dist/GuildIdleManager-DEV-Setup.exe`. An older temporary Setup from package version 2026-10-27 00:04 was separately exercised, but it does not validate the current ZIP and is not a deliverable. Re-run IExpress and first-install/update checks against the exact current Setup before accepting the installer.

## Native window gate

The frozen bundle smoke and HTTP smoke do not prove the native WebView. The current native smoke reaches `shown`; WebView2 initialization reports `IsSuccess=true` on an STA thread and the initialization task completes. pywebview calls `load_url` with the campaign manager URL and sets the control's `Source`, but the WebView2 core remains at `about:blank`. No navigation callback, response, `loaded`, DOM or bridge event follows. The smoke then closes the window and server cleanly. Acceptance still requires the native page and bridge plus campaign create/return/close through the real window. **Native release gate remains open.**

