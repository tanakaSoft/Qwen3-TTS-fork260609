# coding=utf-8
# Fork addition (not part of upstream Qwen3-TTS).
#
# Custom Voice tab: generate speech with a fine-tuned CustomVoice model.
# SPDX-License-Identifier: Apache-2.0
import gradio as gr

from ui import config
from ui.client import get_client
from ui.i18n import t


def create_custom_voice_tab(lang: str) -> None:
    def _(key: str) -> str:
        return t(lang, key)

    def generate(text, speaker, instruct, gen_language):
        if not (text or "").strip():
            return None, _("error") + ": empty text"
        try:
            client = get_client()
            audio, sr = client.generate_custom_voice(
                text=text, speaker=speaker or "speaker_custom",
                instruct=instruct or "", language=gen_language,
            )
            return (sr, audio), _("done")
        except ConnectionError:
            return None, _("not_connected")
        except Exception as exc:  # noqa: BLE001
            return None, f"{_('error')}: {exc}"

    with gr.Column():
        text = gr.Textbox(label=_("text"), lines=4, placeholder=_("text"))
        with gr.Row():
            speaker = gr.Textbox(label=_("speaker"), value="speaker_custom")
            gen_language = gr.Dropdown(
                label=_("gen_language"),
                choices=config.GEN_LANGUAGE_CHOICES,
                value=config.DEFAULT_GEN_LANGUAGE,
            )
        instruct = gr.Textbox(label=_("instruct"), lines=2)
        btn = gr.Button(_("generate"), variant="primary")
        out_audio = gr.Audio(label=_("output_audio"), type="numpy")
        status = gr.Textbox(label=_("status"), value=_("ready"), interactive=False)

        btn.click(
            generate,
            inputs=[text, speaker, instruct, gen_language],
            outputs=[out_audio, status],
        )
