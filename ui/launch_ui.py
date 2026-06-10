# coding=utf-8
# Fork addition (not part of upstream Qwen3-TTS).
#
# Launcher for the Qwen3-TTS Web UI.
#   - Auto-selects a free port (starting from QWEN_TTS_UI_PORT).
#   - Mounts one Gradio app per UI language at /<code> (e.g. /ja, /en).
#   - Redirects / to the default language and opens the browser.
#
# The UI is a thin client: it talks to the API server over HTTP and never
# loads models itself. Start the API server first (server/tts_server_async.py).
#
# Run:  python ui/launch_ui.py
# SPDX-License-Identifier: Apache-2.0
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Ensure the repo root is importable when run as a script.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import gradio as gr  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402

from ui import config  # noqa: E402
from ui.app import build_blocks  # noqa: E402
from ui.i18n import LANGUAGES, normalize_lang  # noqa: E402


def find_free_port(start: int, host: str = "127.0.0.1", limit: int = 50) -> int:
    """Return the first free TCP port at or after `start`."""
    for port in range(start, start + limit):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, port)) != 0:  # nothing listening -> free
                return port
    raise RuntimeError(f"No free port found in [{start}, {start + limit})")


def build_app() -> FastAPI:
    """Build a FastAPI app with one Gradio UI mounted per language."""
    app = FastAPI(title="Qwen3-TTS Web UI")
    default_lang = normalize_lang(config.DEFAULT_UI_LANG)

    @app.get("/")
    def _root():
        return RedirectResponse(url=f"/{default_lang}")

    # Browsers request a PWA manifest at the site root; without this stub every
    # page load logs a 404 (Gradio is mounted under /<lang>, not /).
    @app.get("/manifest.json", include_in_schema=False)
    def _manifest():
        return {
            "name": "Qwen3-TTS Studio",
            "short_name": "Qwen3-TTS",
            "start_url": f"/{default_lang}",
            "display": "browser",
        }

    for code in LANGUAGES:
        app = gr.mount_gradio_app(app, build_blocks(code), path=f"/{code}")
    return app


def _open_browser(url: str, delay: float = 1.5) -> None:
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 - browser is best-effort
            pass

    threading.Thread(target=_open, daemon=True).start()


def main() -> None:
    import uvicorn

    host = config.UI_HOST
    port = find_free_port(config.UI_PORT, host="127.0.0.1")
    default_lang = normalize_lang(config.DEFAULT_UI_LANG)

    browse_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
    url = f"http://{browse_host}:{port}/{default_lang}"

    print(f"[Qwen3-TTS UI] API server : {config.API_SERVER_URL}")
    print(f"[Qwen3-TTS UI] Web UI     : {url}")
    print(f"[Qwen3-TTS UI] Languages  : {', '.join(LANGUAGES)}")

    _open_browser(url)
    uvicorn.run(build_app(), host=host, port=port)


if __name__ == "__main__":
    main()
