# coding=utf-8
# Fork addition (not part of upstream Qwen3-TTS).
#
# Settings tab: live GPU/VRAM stats (periodic refresh) and cache control.
# SPDX-License-Identifier: Apache-2.0
import gradio as gr

from ui import config
from ui.client import get_client
from ui.i18n import t


def _format_stats(lang: str, stats: dict) -> str:
    def _(key: str) -> str:
        return t(lang, key)

    if not stats.get("available"):
        return f"**{_('device')}:** {stats.get('device', '?')} (CUDA not available)"

    models = stats.get("models_loaded", {})
    loaded = ", ".join(k for k, v in models.items() if v) or "-"
    whisper = stats.get("whisper_loaded") or "-"
    lines = [
        f"**{_('device')}:** {stats.get('device_name', '?')} (`{stats.get('device', '?')}`)",
        f"**{_('gpu_memory')}:** {stats.get('used_gb', 0)} / {stats.get('total_gb', 0)} GB",
        f"**{_('models_loaded')}:** {loaded}",
        f"**{_('whisper_loaded')}:** {whisper}",
    ]
    return "  \n".join(lines)


def create_settings_tab(lang: str) -> None:
    def _(key: str) -> str:
        return t(lang, key)

    def refresh():
        try:
            stats = get_client().gpu_stats()
            return _format_stats(lang, stats)
        except ConnectionError:
            return _("not_connected")
        except Exception as exc:  # noqa: BLE001
            return f"{_('error')}: {exc}"

    def clear_cache():
        try:
            get_client().clear_gpu_cache()
            return refresh()
        except ConnectionError:
            return _("not_connected")
        except Exception as exc:  # noqa: BLE001
            return f"{_('error')}: {exc}"

    with gr.Column():
        gr.Markdown(f"### {_('server_url')}: `{config.API_SERVER_URL}`")
        gr.Markdown(f"## {_('gpu_status')}")
        gpu_info = gr.Markdown(_("ready"))
        with gr.Row():
            refresh_btn = gr.Button(_("refresh"))
            clear_btn = gr.Button(_("clear_cache"))
            auto = gr.Checkbox(label=_("auto_refresh"), value=True)

        timer = gr.Timer(config.GPU_REFRESH_SECONDS)

        refresh_btn.click(refresh, outputs=[gpu_info])
        clear_btn.click(clear_cache, outputs=[gpu_info])
        # Periodic refresh; the checkbox enables/disables the timer.
        timer.tick(refresh, outputs=[gpu_info])
        auto.change(
            lambda on: gr.Timer(active=bool(on)),
            inputs=[auto],
            outputs=[timer],
        )
