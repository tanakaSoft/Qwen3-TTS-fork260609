# coding=utf-8
# Fork addition (not part of upstream Qwen3-TTS).
#
# Lazy, fault-tolerant accessor for the TTS API client used by the Web UI.
# The UI must build even when the API server is still starting, so the client
# is created on first use and connection errors surface as friendly messages.
#
# SPDX-License-Identifier: Apache-2.0
import sys
from pathlib import Path

# Make both `server/` and `ui/` importable no matter how the UI was launched
# (e.g. `python ui/launch_ui.py` puts ui/ on sys.path, not the repo root).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from server.tts_client_async import QwenTTSAsyncClient  # noqa: E402
from ui import config  # noqa: E402

_client = None


def get_client() -> QwenTTSAsyncClient:
    """Return a connected client, creating it on first use.

    Raises ConnectionError (from the client constructor) if the API server is
    unreachable; callers should catch this and show a friendly message.
    """
    global _client
    if _client is None:
        _client = QwenTTSAsyncClient(config.API_SERVER_URL, timeout=config.REQUEST_TIMEOUT)
    return _client
