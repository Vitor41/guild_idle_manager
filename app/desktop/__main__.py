import os
import sys
import traceback
from pathlib import Path

from app.core.version import APP_VERSION


def _run_cli_smoke(smoke, result_environment_key: str) -> None:
    try:
        smoke()
    except Exception:
        result_path = os.environ.get(result_environment_key)
        if result_path:
            destination = Path(result_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("FAIL: " + traceback.format_exc(), encoding="utf-8")
        raise SystemExit(1)


if "--version" in sys.argv:
    result_path = os.environ.get("GIM_VERSION_RESULT")
    if result_path:
        from pathlib import Path

        Path(result_path).write_text(APP_VERSION, encoding="utf-8")
    else:
        print(APP_VERSION)
elif "--smoke" in sys.argv:
    os.environ["APP_MODE"] = "desktop"
    from app.desktop.offline_smoke import run_offline_smoke

    _run_cli_smoke(run_offline_smoke, "GIM_SMOKE_RESULT")
elif "--launcher-smoke" in sys.argv:
    from app.desktop.update_launcher import run_launcher_smoke

    _run_cli_smoke(run_launcher_smoke, "GIM_LAUNCHER_SMOKE_RESULT")
elif "--play" in sys.argv:
    from app.desktop.launcher import run

    run()
elif getattr(sys, "frozen", False):
    from app.desktop.update_launcher import run_prelaunch

    run_prelaunch()
else:
    from app.desktop.launcher import run

    run()
