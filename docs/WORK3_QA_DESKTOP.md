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

**Setup gate remains open:** IExpress exited with code 1 during the current build, so there is no matching `dist/GuildIdleManager-DEV-Setup.exe`. A bounded repeat with `Start-Process ... /N /Q "<SED>"` also exited 1 immediately and produced no Setup, DDF, or CAB in the preserved diagnostics folder. The current ZIP is 57,191,468 bytes and its bundled `--smoke` passed; install-script tests passed in isolation. An older temporary Setup at `%TEMP%\gim_iexpress_a0a7ef2df5fb4bf78f029d8b77b86af8\GuildIdleManager-DEV-Setup.exe` (SHA-256 `85E151DF1BDCE9670CFB59D1E29237A0C03EBFC843DC9C923B9F2EF67B53C5A5`) passed first install and update tests, but it contains an older ZIP and does not validate or represent the current build. Do not treat it as a deliverable.

## Native window gate

The frozen bundle smoke and HTTP smoke do not prove the native WebView. The current native smoke reaches `shown`; WebView2 initialization reports `IsSuccess=true` on an STA thread and its task completes. pywebview calls `load_url` with the campaign manager URL and sets the control's `Source`, but the WebView2 core stays at `about:blank` at the immediate read. In the baseline run, navigation and response evidence was inconsistent, and `loaded`, DOM and bridge were not confirmed. The desktop CSP allows same-origin navigation, local scripts, and `unsafe-eval` required by the bridge; it does not explain the missing initial page by itself.

One isolated diagnostic set `GIM_TEST_DIRECT_NAVIGATE=1` to call `CoreWebView2.Navigate(real_url)` after pywebview's original handler. It produced `NavigationStarting`, then a `NavigationCompleted` with `IsSuccess=false` and `WebErrorStatus=ConnectionAborted`; pywebview logged `_pywebviewready`, but the smoke still did not confirm `loaded`, DOM, or bridge and closed the window/server cleanly. Because the extra navigation overlaps the control's `Source` navigation, this experiment does not establish a production fix. Acceptance still requires the unmodified native path to render, expose the bridge, and complete campaign create/return/close. **Native release gate remains open.**

