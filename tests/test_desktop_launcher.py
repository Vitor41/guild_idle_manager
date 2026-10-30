from contextlib import ExitStack
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from app.desktop import launcher


class _Listener:
    def __init__(self):
        self.bound = None
        self.closed = False

    def setsockopt(self, *_args):
        pass

    def bind(self, address):
        self.bound = address

    def listen(self, _backlog):
        pass

    def getsockname(self):
        return ("127.0.0.1", 48123)

    def close(self):
        self.closed = True


class _Thread:
    instances = []

    def __init__(self, target, **kwargs):
        self.target = target
        self.kwargs = kwargs
        self.started = False
        self.joined = False
        self.instances.append(self)

    def start(self):
        self.started = True
        self.target()

    def join(self, timeout=None):
        self.joined = True
        self.timeout = timeout

    def is_alive(self):
        return False


class _ClosedEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


class DesktopLauncherUnitTests(unittest.TestCase):
    def _run_with_stubs(self, health_error=None):
        listener = _Listener()
        data_directory = tempfile.TemporaryDirectory(prefix="gim-launcher-test-data-")
        webview_storage = Path(data_directory.name) / "webview"
        app = SimpleNamespace(state=SimpleNamespace(campaign_service=object(), clock_guard=object()))
        servers = []
        config_calls = []

        class FakeServer:
            def __init__(self, config):
                self.config = config
                self.started = False
                self.should_exit = False
                servers.append(self)

            def run(self, sockets):
                self.started = True
                self.sockets = sockets

        closed = _ClosedEvent()
        window = SimpleNamespace(events=SimpleNamespace(closed=closed))
        bridge_module = ModuleType("app.desktop.bridge")

        class FakeBridge:
            def __init__(self, campaigns, clock_guard):
                self.campaigns = campaigns
                self.clock_guard = clock_guard
                self._window = None

        bridge_module.DesktopBridge = FakeBridge
        webview_module = ModuleType("webview")
        webview_module.create_window = Mock(return_value=window)
        focus_compatibility = Mock()

        def start_webview(**kwargs):
            self.assertEqual(kwargs, {"gui": "edgechromium", "storage_path": str(webview_storage)})
            self.assertTrue(webview_storage.is_dir())
            focus_compatibility.assert_called_once_with(webview_module)
            for handler in closed.handlers:
                handler()

        webview_module.start = Mock(side_effect=start_webview)
        main_module = ModuleType("app.main")
        main_module.app = app
        _Thread.instances = []

        def make_config(*args, **kwargs):
            config_calls.append((args, kwargs))
            return SimpleNamespace(args=args, kwargs=kwargs)

        with ExitStack() as stack:
            stack.callback(data_directory.cleanup)
            stack.enter_context(patch.dict(os.environ, {"APP_MODE": "web"}))
            stack.enter_context(patch.dict(sys.modules, {
                "app.main": main_module,
                "app.desktop.bridge": bridge_module,
                "webview": webview_module,
            }))
            stack.enter_context(patch.object(launcher, "_configure_logging"))
            stack.enter_context(patch.object(launcher, "user_data_directory", return_value=Path(data_directory.name)))
            stack.enter_context(patch.object(
                launcher,
                "_skip_pywebview_early_webview_focus",
                focus_compatibility,
            ))
            stack.enter_context(patch.object(launcher, "_acquire_single_instance_mutex", return_value="mutex"))
            release_mutex = stack.enter_context(patch.object(launcher, "_release_single_instance_mutex"))
            error_dialog = stack.enter_context(patch.object(launcher, "_show_startup_error"))
            health = stack.enter_context(patch.object(launcher, "_wait_for_health"))
            if health_error is not None:
                health.side_effect = health_error
            else:
                health.side_effect = lambda _url, server: self.assertTrue(server.started)
            socket_module = SimpleNamespace(
                AF_INET=2,
                SOCK_STREAM=1,
                SOL_SOCKET=1,
                SO_REUSEADDR=2,
                socket=Mock(return_value=listener),
            )
            stack.enter_context(patch.object(launcher, "socket", socket_module))
            stack.enter_context(patch.object(launcher.threading, "Thread", _Thread))
            stack.enter_context(patch.object(launcher.uvicorn, "Config", side_effect=make_config))
            stack.enter_context(patch.object(launcher.uvicorn, "Server", FakeServer))

            if health_error is None:
                launcher.run()
            else:
                with self.assertRaisesRegex(RuntimeError, "healthcheck stub failure"):
                    launcher.run()
            release_mutex.assert_called_once_with("mutex")

        return listener, app, servers, config_calls, _Thread.instances, webview_module, error_dialog, str(webview_storage)

    def test_launcher_uses_loopback_healthchecks_before_window_and_cleans_up_after_close(self):
        listener, app, servers, config_calls, threads, webview, error_dialog, webview_storage = self._run_with_stubs()

        self.assertEqual(listener.bound, ("127.0.0.1", 0))
        self.assertTrue(listener.closed)
        self.assertEqual(app.state.desktop_allowed_host, "127.0.0.1:48123")
        self.assertEqual(app.state.desktop_allowed_origin, "http://127.0.0.1:48123")
        self.assertEqual(config_calls[0][1]["host"], "127.0.0.1")
        self.assertEqual(config_calls[0][1]["port"], 48123)
        self.assertTrue(servers[0].should_exit)
        self.assertTrue(threads[0].started)
        self.assertTrue(threads[0].joined)
        self.assertEqual(threads[0].kwargs["name"], "gim-local-api")
        webview.create_window.assert_called_once()
        webview.start.assert_called_once_with(gui="edgechromium", storage_path=str(webview_storage))
        error_dialog.assert_not_called()

    def test_pywebview_compatibility_skips_only_early_focus_and_is_idempotent(self):
        class FakeBrowserForm:
            def __init__(self):
                self.shown = SimpleNamespace(set=Mock())
                self.browser = SimpleNamespace(webview=SimpleNamespace(Focus=Mock()))

            def on_shown(self, *_args):
                self.shown.set()
                self.browser.webview.Focus()

        form_type = FakeBrowserForm
        winforms = SimpleNamespace(
            BrowserView=SimpleNamespace(BrowserForm=form_type),
            is_cef=False,
        )
        platforms = ModuleType("webview.platforms")
        platforms.winforms = winforms
        webview_module = ModuleType("webview")

        with patch.object(launcher.os, "name", "nt"), patch.dict(
            sys.modules,
            {"webview.platforms": platforms},
        ):
            launcher._skip_pywebview_early_webview_focus(webview_module)
            launcher._skip_pywebview_early_webview_focus(webview_module)

        form = form_type()
        form.on_shown()

        form.shown.set.assert_called_once_with()
        form.browser.webview.Focus.assert_not_called()
        self.assertTrue(form_type._gim_skip_early_webview_focus)

    def test_launcher_stops_server_and_closes_listener_when_healthcheck_fails(self):
        listener, _app, servers, _config_calls, threads, webview, error_dialog, _webview_storage = self._run_with_stubs(
            RuntimeError("healthcheck stub failure")
        )

        self.assertTrue(listener.closed)
        self.assertTrue(servers[0].should_exit)
        self.assertTrue(threads[0].started)
        self.assertTrue(threads[0].joined)
        webview.create_window.assert_not_called()
        error_dialog.assert_called_once()

    def test_mutex_acquisition_and_release_wrap_win32_handle(self):
        kernel32 = SimpleNamespace(
            CreateMutexW=Mock(return_value=123),
            CloseHandle=Mock(return_value=1),
            ReleaseMutex=Mock(return_value=1),
            SetLastError=Mock(),
            GetLastError=Mock(return_value=0),
        )
        with patch.object(launcher.os, "name", "nt"), \
             patch.object(launcher.ctypes, "WinDLL", return_value=kernel32, create=True):
            mutex = launcher._acquire_single_instance_mutex("C:/temporary/profile")
            self.assertEqual(mutex, (123, kernel32))
            kernel32.CreateMutexW.assert_called_once()
            kernel32.SetLastError.assert_called_once_with(0)
            self.assertTrue(kernel32.CreateMutexW.call_args.args[1])
            self.assertTrue(kernel32.CreateMutexW.call_args.args[2].startswith("Local\\GuildIdleManager-"))
            launcher._release_single_instance_mutex(mutex)

        kernel32.ReleaseMutex.assert_called_once_with(123)
        kernel32.CloseHandle.assert_called_once_with(123)

    def test_mutex_duplicate_closes_new_handle_and_reports_existing_instance(self):
        kernel32 = SimpleNamespace(
            CreateMutexW=Mock(return_value=456),
            CloseHandle=Mock(return_value=1),
            ReleaseMutex=Mock(return_value=1),
            SetLastError=Mock(),
            GetLastError=Mock(return_value=183),
        )
        with patch.object(launcher.os, "name", "nt"), \
             patch.object(launcher.ctypes, "WinDLL", return_value=kernel32, create=True):
            with self.assertRaisesRegex(launcher.DesktopAlreadyRunningError, "já está aberto"):
                launcher._acquire_single_instance_mutex("C:/temporary/profile")

        kernel32.SetLastError.assert_called_once_with(0)
        kernel32.CloseHandle.assert_called_once_with(456)
        kernel32.ReleaseMutex.assert_not_called()

    def test_mutex_ignores_stale_last_error_when_creation_succeeds(self):
        kernel32 = SimpleNamespace(
            last_error=183,
            CreateMutexW=Mock(return_value=789),
            CloseHandle=Mock(return_value=1),
            ReleaseMutex=Mock(return_value=1),
            SetLastError=Mock(),
            GetLastError=Mock(),
        )
        kernel32.SetLastError.side_effect = lambda value: setattr(kernel32, "last_error", value)
        kernel32.GetLastError.side_effect = lambda: kernel32.last_error
        with patch.object(launcher.os, "name", "nt"), \
             patch.object(launcher.ctypes, "WinDLL", return_value=kernel32, create=True):
            mutex = launcher._acquire_single_instance_mutex("C:/temporary/profile")
            self.assertEqual(mutex, (789, kernel32))
            launcher._release_single_instance_mutex(mutex)

        self.assertEqual(kernel32.last_error, 0)

    def test_launcher_returns_cleanly_when_profile_mutex_already_exists(self):
        message_box = Mock()
        user32 = SimpleNamespace(MessageBoxW=message_box)
        with ExitStack() as stack:
            stack.enter_context(patch.object(launcher.os, "name", "nt"))
            stack.enter_context(patch.object(launcher, "_configure_logging"))
            stack.enter_context(patch.object(
                launcher,
                "_acquire_single_instance_mutex",
                side_effect=launcher.DesktopAlreadyRunningError("já está aberto"),
            ))
            socket_factory = stack.enter_context(patch.object(launcher, "socket"))
            stack.enter_context(patch.object(launcher.ctypes, "windll", SimpleNamespace(user32=user32), create=True))

            launcher.run()

        socket_factory.socket.assert_not_called()
        message_box.assert_called_once()

    @unittest.skipUnless(os.name == "nt", "Named Windows mutex is only available on Windows.")
    def test_named_mutex_rejects_second_launcher_for_same_data_profile(self):
        with tempfile.TemporaryDirectory(prefix="gim-mutex-profile-") as profile_dir:
            first = launcher._acquire_single_instance_mutex(profile_dir)
            try:
                with self.assertRaisesRegex(
                    launcher.DesktopAlreadyRunningError,
                    "já está aberto",
                ):
                    launcher._acquire_single_instance_mutex(profile_dir)
            finally:
                launcher._release_single_instance_mutex(first)

            second_after_release = launcher._acquire_single_instance_mutex(profile_dir)
            launcher._release_single_instance_mutex(second_after_release)


if __name__ == "__main__":
    unittest.main()
