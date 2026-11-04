import os
import sys

from app.core.version import APP_VERSION


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

    run_offline_smoke()
else:
    from app.desktop.launcher import run

    run()
