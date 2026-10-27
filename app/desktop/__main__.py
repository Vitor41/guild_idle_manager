import os
import sys

from app.desktop.launcher import run


if "--smoke" in sys.argv:
    os.environ["APP_MODE"] = "desktop"
    from app.desktop.offline_smoke import run_offline_smoke

    run_offline_smoke()
else:
    run()
