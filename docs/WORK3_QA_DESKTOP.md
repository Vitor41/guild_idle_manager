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

- `dist/GuildIdleManager-DEV.zip` — SHA-256 `7A8B728912385BACF690341E7B7939DBBAD5245F83E75763A8B36E8E528E4770`.
- `dist/GuildIdleManager-DEV-Setup.exe` — SHA-256 `E8E31FD998A907331474E19CFA8C7793E5271E92B08BFE80C5BCDECC0A501AB0`.

IExpress returned exit code 0 before the Setup file appeared; the build script now waits up to 90 seconds for a stable output and verifies its PE header before moving it into `dist`. The final Setup passed isolated first install and managed update (`Start-Process -Wait`: exit 0 for both) with a temporary `%LOCALAPPDATA%`. The saves sentinel remained unchanged, the marker identified the DEV install, and a planted obsolete app file was removed. All 856 installed app files had hashes identical to the current packaged bundle. The Setup now matches the final ZIP used by the build script.

## Native window gate

The frozen bundle smoke and HTTP smoke do not prove the native WebView. The current native smoke reaches `shown`; WebView2 initialization reports `IsSuccess=true` on an STA thread and its task completes. pywebview calls `load_url` with the campaign manager URL and sets the control's `Source`, but the WebView2 core stays at `about:blank` at the immediate read. In the baseline run, navigation and response evidence was inconsistent, and `loaded`, DOM and bridge were not confirmed. The desktop CSP allows same-origin navigation, local scripts, and `unsafe-eval` required by the bridge; it does not explain the missing initial page by itself.

One isolated diagnostic set `GIM_TEST_DIRECT_NAVIGATE=1` to call `CoreWebView2.Navigate(real_url)` after pywebview's original handler. It produced `NavigationStarting`, then a `NavigationCompleted` with `IsSuccess=false` and `WebErrorStatus=ConnectionAborted`; pywebview logged `_pywebviewready`, but the smoke still did not confirm `loaded`, DOM, or bridge and closed the window/server cleanly. Because the extra navigation overlaps the control's `Source` navigation, this experiment does not establish a production fix. The separate unmodified run also failed before `loaded` and the bridge.

A minimal pywebview EdgeChromium window served from Python's standard-library HTTP server reproduced the failure without FastAPI, desktop middleware, CSP, campaign data, or the application launcher: `shown=true`, the local route returned HTTP 200, `loaded=false`, and the window closed cleanly. A second minimal window using only inline HTML also reached `shown`, initialized WebView2 successfully, emitted no `NavigationCompleted`, and never reached `loaded`; it then closed cleanly. A direct `ExecuteScriptAsync` DOM query in the network probe timed out at the 60-second bound, so there is no evidence that the page rendered despite the HTTP 200. This host has Microsoft Edge WebView2 Runtime `155.0.4283.62`; no matching recent Application Error, .NET Runtime, or Windows Error Reporting events were found. These results narrow the failure to the host's pywebview/WebView2 rendering/event path or a lower-level interaction; they do not identify a root cause or a fix. Acceptance still requires the native path to render and complete campaign create/return/close. **Native release gate remains open.**

The minimal inline-HTML case was also launched as `python.exe` in a normal interactive user session, outside the app launcher and without the console-free `pythonw.exe` path. The window was shown and WebView2 initialization succeeded on an STA thread (`BrowserProcessId=10088`), but no navigation event fired, `loaded` stayed false, and neither DOM nor bridge was confirmed. A fresh-profile rerun with `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--disable-gpu` behaved the same (`BrowserProcessId=23192`; no navigation events; `loaded=false`, `bridge=false`; clean close). These probes do not support the hypothesis that the failure is caused by `pythonw.exe` or GPU acceleration. A screenshot attempt using the host's window-capture API failed with an invalid-handle error, so window pixels could not be inspected. The process IDs were captured during initialization; no per-process exit code or WebView2 debug log establishing a renderer crash was collected. No alternate renderer was evaluated because the game's modern JavaScript and bridge requirements would make an older renderer an invalid acceptance substitute.

