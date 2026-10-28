from contextlib import ExitStack
import os
import sys
from types import ModuleType, SimpleNamespace
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

        def start_webview(**kwargs):
            self.assertEqual(kwargs, {"gui": "edgechromium"})
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
            stack.enter_context(patch.dict(os.environ, {"APP_MODE": "web"}))
            stack.enter_context(patch.dict(sys.modules, {
                "app.main": main_module,
                "app.desktop.bridge": bridge_module,
                "webview": webview_module,
            }))
            stack.enter_context(patch.object(launcher, "_configure_logging"))
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

        return listener, app, servers, config_calls, _Thread.instances, webview_module, error_dialog

    def test_launcher_uses_loopback_healthchecks_before_window_and_cleans_up_after_close(self):
        listener, app, servers, config_calls, threads, webview, error_dialog = self._run_with_stubs()

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
        webview.start.assert_called_once_with(gui="edgechromium")
        error_dialog.assert_not_called()

    def test_launcher_stops_server_and_closes_listener_when_healthcheck_fails(self):
        listener, _app, servers, _config_calls, threads, webview, error_dialog = self._run_with_stubs(
            RuntimeError("healthcheck stub failure")
        )

        self.assertTrue(listener.closed)
        self.assertTrue(servers[0].should_exit)
        self.assertTrue(threads[0].started)
        self.assertTrue(threads[0].joined)
        webview.create_window.assert_not_called()
        error_dialog.assert_called_once()


if __name__ == "__main__":
    unittest.main()
