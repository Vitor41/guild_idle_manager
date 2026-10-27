"""Opt-in end-to-end smoke for the real pywebview window lifecycle."""

import json
import os
from contextlib import closing
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from urllib.error import URLError
from urllib.request import urlopen
import sqlite3


RUNTIME_SMOKE_ENABLED = os.environ.get("GIM_RUN_DESKTOP_RUNTIME_SMOKE") == "1"


@unittest.skipUnless(os.name == "nt" and RUNTIME_SMOKE_ENABLED, "Set GIM_RUN_DESKTOP_RUNTIME_SMOKE=1 on Windows to run the native window smoke.")
class DesktopRuntimeSmokeTests(unittest.TestCase):
    def test_window_create_return_close_stops_server_and_closes_campaign(self):
        with tempfile.TemporaryDirectory(prefix="gim-desktop-smoke-") as temp_dir:
            root = Path(temp_dir)
            marker_path = root / "runtime-smoke.json"
            child_script = textwrap.dedent(
                r'''
                import json
                import os
                import logging
                from pathlib import Path
                import threading
                import time
                import traceback
                import webview
                from app.desktop.launcher import run

                marker = Path(os.environ["GIM_RUNTIME_SMOKE_MARKER"])
                pywebview_log = Path(os.environ["LOCALAPPDATA"]) / "pywebview-runtime.log"
                pywebview_handler = logging.FileHandler(pywebview_log, encoding="utf-8")
                pywebview_handler.setLevel(logging.DEBUG)
                pywebview_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
                pywebview_logger = logging.getLogger("pywebview")
                pywebview_logger.setLevel(logging.DEBUG)
                pywebview_logger.addHandler(pywebview_handler)
                original_start = webview.start
                window_closed = threading.Event()
                webview_responses = []

                def smoke_window_lifecycle():
                    window = webview.windows[0]
                    result = {
                        "probe_started": True,
                        "window_shown": False,
                        "webview_page_loaded": False,
                        "manager_dom_visible": False,
                        "dashboard_dom_visible": False,
                        "campaign_created_and_opened": False,
                        "returned_to_menu": False,
                        "manager_restored": False,
                        "window_closed": False,
                    }

                    def save_progress():
                        marker.write_text(json.dumps(result), encoding="utf-8")

                    def wait_for_dom(script, timeout=30):
                        deadline = time.monotonic() + timeout
                        while time.monotonic() < deadline:
                            if window.evaluate_js(script) is True:
                                return True
                            time.sleep(0.1)
                        return False

                    save_progress()
                    try:
                        if not window.events.shown.wait(30):
                            raise RuntimeError("pywebview window did not reach its shown event")
                        result["window_shown"] = True
                        save_progress()

                        result["webview_page_loaded"] = window.events.loaded.wait(30)
                        if not result["webview_page_loaded"]:
                            result["bridge_ready"] = window.events._pywebviewready.is_set()
                            result["webview_responses"] = list(webview_responses)
                            raise RuntimeError(f"campaign manager did not load in pywebview; bridge_ready={result['bridge_ready']}, responses={result['webview_responses']!r}")
                        if window.evaluate_js("document.querySelector('#create-campaign-form') !== null") is not True:
                            raise RuntimeError("campaign manager DOM was not present in the native WebView")
                        result["manager_dom_visible"] = True
                        result["bridge_api_visible"] = window.evaluate_js(
                            "typeof window.pywebview?.api?.export_campaign === 'function'"
                        ) is True
                        if not result["bridge_api_visible"]:
                            raise RuntimeError("desktop bridge API was not present in the native WebView")
                        save_progress()

                        from app.main import app
                        window.evaluate_js("""(() => {
                            document.querySelector('#campaign-name').value = 'Smoke runtime';
                            document.querySelector('#guild-name').value = 'Guilda de teste';
                            document.querySelector('#create-campaign-form').requestSubmit();
                            return true;
                        })()""")

                        deadline = time.monotonic() + 35
                        while time.monotonic() < deadline:
                            if window.evaluate_js("window.location.pathname") == "/dashboard":
                                break
                            time.sleep(0.1)
                        else:
                            raise RuntimeError("the native WebView did not navigate to the new campaign dashboard")
                        if not wait_for_dom("document.querySelector('form[action=\"/desktop/return-to-campaigns\"]') !== null"):
                            raise RuntimeError("campaign dashboard did not show the return-to-campaigns action")
                        result["dashboard_dom_visible"] = True
                        result["campaign_id"] = app.state.active_campaign.campaign_id
                        result["campaign_created_and_opened"] = True
                        save_progress()

                        window.evaluate_js("document.querySelector('form[action=\"/desktop/return-to-campaigns\"]').requestSubmit(); true")
                        deadline = time.monotonic() + 35
                        while time.monotonic() < deadline:
                            if window.evaluate_js("window.location.pathname") == "/desktop/campaigns":
                                break
                            time.sleep(0.1)
                        else:
                            raise RuntimeError("the native WebView did not return to the campaign manager")
                        if not wait_for_dom("document.querySelector('#campaign-list-title') !== null"):
                            raise RuntimeError("campaign manager DOM was not restored after returning")
                        result["returned_to_menu"] = True
                        result["manager_restored"] = True
                        save_progress()
                        if app.state.active_campaign is not None or result["campaign_id"] not in app.state.suspended_campaigns:
                            raise RuntimeError("campaign lifecycle state did not match the returned campaign menu")
                        result["health_url"] = app.state.desktop_allowed_origin + "/desktop/health"
                    except BaseException:
                        result["error"] = traceback.format_exc()
                        if pywebview_log.exists():
                            result["pywebview_log_tail"] = "\n".join(pywebview_log.read_text(encoding="utf-8", errors="replace").splitlines()[-40:])
                    finally:
                        result["window_close_requested"] = True
                        save_progress()
                        window.confirm_close = False
                        window.destroy()
                        result["window_closed"] = window_closed.wait(15)
                        if not result["window_closed"] and "error" not in result:
                            result["error"] = "pywebview did not emit its closed event after window.destroy()"
                        save_progress()

                def start_with_lifecycle_probe(*args, **kwargs):
                    window = webview.windows[0]
                    window.events.closed += window_closed.set
                    window.events.response_received += lambda response: webview_responses.append(repr(response))
                    kwargs["func"] = smoke_window_lifecycle
                    return original_start(*args, **kwargs)

                webview.start = start_with_lifecycle_probe
                run()
                '''
            )
            environment = os.environ.copy()
            environment["APP_MODE"] = "desktop"
            environment["LOCALAPPDATA"] = str(root)
            environment["GIM_RUNTIME_SMOKE_MARKER"] = str(marker_path)
            pythonw = Path(sys.executable).with_name("pythonw.exe")
            process = subprocess.Popen(
                [str(pythonw), "-c", child_script],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
            )
            try:
                stdout, stderr = process.communicate(timeout=90)
            except subprocess.TimeoutExpired:
                progress = marker_path.read_text(encoding="utf-8") if marker_path.exists() else "no lifecycle callback marker was written"
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
                process.kill()
                stdout, stderr = process.communicate(timeout=10)
                self.fail(f"desktop runtime smoke timed out at {progress}\n{stdout}\n{stderr}")

            self.assertTrue(marker_path.exists(), (stdout or "") + (stderr or ""))
            result = json.loads(marker_path.read_text(encoding="utf-8"))
            self.assertNotIn("error", result, result.get("error", "") + result.get("pywebview_log_tail", ""))
            self.assertTrue(result["window_shown"])
            self.assertTrue(result["webview_page_loaded"])
            self.assertTrue(result["manager_dom_visible"])
            self.assertTrue(result["bridge_api_visible"])
            self.assertTrue(result["dashboard_dom_visible"])
            self.assertTrue(result["campaign_created_and_opened"])
            self.assertTrue(result["returned_to_menu"])
            self.assertTrue(result["manager_restored"])
            self.assertTrue(result["window_closed"])
            self.assertEqual(process.returncode, 0, (stdout or "") + (stderr or ""))

            database_path = root / "GuildIdleManager" / "saves" / f"{result['campaign_id']}.db"
            with closing(sqlite3.connect(database_path)) as connection:
                state, closed_at = connection.execute(
                    "SELECT last_session_state, last_clean_shutdown_utc FROM campaign_metadata WHERE campaign_id = ?",
                    (result["campaign_id"],),
                ).fetchone()
            self.assertEqual(state, "closed")
            self.assertIsNotNone(closed_at)

            server_stopped = False
            for _ in range(25):
                try:
                    with urlopen(result["health_url"], timeout=0.5):
                        time.sleep(0.1)
                except (OSError, URLError):
                    server_stopped = True
                    break
            self.assertTrue(server_stopped, "loopback server still answered after the window process exited")


if __name__ == "__main__":
    unittest.main()
