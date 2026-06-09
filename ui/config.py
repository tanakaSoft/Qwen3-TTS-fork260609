# coding=utf-8
# Fork addition (not part of upstream Qwen3-TTS).
#
# Configuration for the Gradio Web UI (thin client over the TTS API server).
#
# SPDX-License-Identifier: Apache-2.0
import os

# The UI is a thin HTTP client: it never loads models itself. It talks to the
# FastAPI server (server/tts_server_async.py) over HTTP. Point this at wherever
# the API server runs (same machine by default).
API_SERVER_URL = os.environ.get("QWEN_TTS_API_URL", "http://localhost:8001")

# Gradio bind host/port. Auto-port selection in launch_ui.py starts here.
UI_HOST = os.environ.get("QWEN_TTS_UI_HOST", "127.0.0.1")
UI_PORT = int(os.environ.get("QWEN_TTS_UI_PORT", "7860"))

# Default UI language (one of ui/i18n.py LANGUAGES). Overridable via ?lang= too.
DEFAULT_UI_LANG = os.environ.get("QWEN_TTS_UI_LANG", "ja")

# Default generation language shown in the tabs.
DEFAULT_GEN_LANGUAGE = os.environ.get("QWEN_TTS_GEN_LANG", "Japanese")

# How often (seconds) the Settings tab refreshes GPU stats.
GPU_REFRESH_SECONDS = float(os.environ.get("QWEN_TTS_GPU_REFRESH", "5"))

# Request timeout (seconds) for generation calls from the UI to the API.
REQUEST_TIMEOUT = float(os.environ.get("QWEN_TTS_UI_TIMEOUT", "600"))

# --- Dropdown choices (sensible defaults; refine against the running server) ---
# Whisper models offered in the Voice Clone tab (mirror server/tts_whisper.py).
WHISPER_MODEL_CHOICES = ["tiny", "base", "small", "medium", "large-v3"]
DEFAULT_WHISPER_MODEL = os.environ.get("QWEN_TTS_WHISPER", "large-v3")

# Languages offered for transcription (Whisper) and generation (TTS).
TRANSCRIBE_LANG_CHOICES = ["Auto", "Japanese", "English", "Chinese", "Korean"]
GEN_LANGUAGE_CHOICES = ["Japanese", "English", "Chinese", "Korean", "Auto"]
