# coding=utf-8
# Fork addition (not part of upstream Qwen3-TTS).
#
# Builds the Gradio Web UI (a thin client over the TTS API server).
#
# Multilingual strategy: instead of fragile live re-labelling, we build one
# Blocks per language and mount each at its own route (/ja, /en, ...). The
# language selector simply navigates to the chosen route. Blocks are cheap to
# build (no models are loaded here), so this is fast and robust.
#
# SPDX-License-Identifier: Apache-2.0
import gradio as gr

from ui import config
from ui.i18n import LANGUAGES, normalize_lang, t
from ui.tabs.custom_voice import create_custom_voice_tab
from ui.tabs.voice_design import create_voice_design_tab
from ui.tabs.voice_clone import create_voice_clone_tab
from ui.tabs.finetune import create_finetune_tab
from ui.tabs.settings import create_settings_tab


def build_blocks(lang: str) -> gr.Blocks:
    """Build the full 4-tab UI for a single language."""
    lang = normalize_lang(lang)

    with gr.Blocks(title=t(lang, "app_title")) as demo:
        with gr.Row():
            gr.Markdown(f"# {t(lang, 'app_title')}")
            ui_lang = gr.Dropdown(
                label=t(lang, "ui_language"),
                choices=[(name, code) for code, name in LANGUAGES.items()],
                value=lang,
                scale=0,
            )

        with gr.Tabs():
            with gr.Tab(t(lang, "tab_custom")):
                create_custom_voice_tab(lang)
            with gr.Tab(t(lang, "tab_design")):
                create_voice_design_tab(lang)
            with gr.Tab(t(lang, "tab_clone")):
                create_voice_clone_tab(lang)
            with gr.Tab(t(lang, "tab_finetune")):
                create_finetune_tab(lang)
            with gr.Tab(t(lang, "tab_settings")):
                create_settings_tab(lang)

        # Navigate to the route for the chosen language (one Blocks per lang).
        ui_lang.change(
            fn=None,
            inputs=[ui_lang],
            outputs=None,
            js="(code) => { window.location.pathname = '/' + code; }",
        )

    return demo


def build_all_blocks():
    """Return {lang_code: Blocks} for every supported UI language."""
    return {code: build_blocks(code) for code in LANGUAGES}
