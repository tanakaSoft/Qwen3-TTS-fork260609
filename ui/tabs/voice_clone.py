# coding=utf-8
# Fork addition (not part of upstream Qwen3-TTS).
#
# Voice Clone tab: clone a voice from a reference clip. Includes Whisper
# auto-transcription to fill the reference text (idea from Qwen3-TTS-JP).
# SPDX-License-Identifier: Apache-2.0
import gradio as gr

from ui import config
from ui.client import get_client
from ui.i18n import t


def create_voice_clone_tab(lang: str) -> None:
    def _(key: str) -> str:
        return t(lang, key)

    def transcribe(ref_audio_path, whisper_model, transcribe_language):
        if not ref_audio_path:
            return "", _("error") + ": no reference audio"
        try:
            client = get_client()
            language = "" if transcribe_language == "Auto" else transcribe_language
            text = client.auto_transcribe(
                audio_path=ref_audio_path, model=whisper_model, language=language,
            )
            return text, _("done")
        except ConnectionError:
            return "", _("not_connected")
        except Exception as exc:  # noqa: BLE001
            return "", f"{_('error')}: {exc}"

    def generate(text, ref_audio_path, ref_text, gen_language, x_vector_only):
        if not (text or "").strip():
            return None, _("error") + ": empty text"
        if not ref_audio_path:
            return None, _("error") + ": no reference audio"
        try:
            client = get_client()
            audio, sr = client.generate_voice_clone(
                text=text, ref_audio_path=ref_audio_path, ref_text=ref_text or "",
                language=gen_language, x_vector_only_mode=bool(x_vector_only),
            )
            return (sr, audio), _("done")
        except ConnectionError:
            return None, _("not_connected")
        except Exception as exc:  # noqa: BLE001
            return None, f"{_('error')}: {exc}"

    with gr.Column():
        ref_audio = gr.Audio(label=_("ref_audio"), type="filepath")
        with gr.Row():
            whisper_model = gr.Dropdown(
                label=_("whisper_model"),
                choices=config.WHISPER_MODEL_CHOICES,
                value=config.DEFAULT_WHISPER_MODEL,
            )
            transcribe_language = gr.Dropdown(
                label=_("transcribe_language"),
                choices=config.TRANSCRIBE_LANG_CHOICES,
                value="Auto",
            )
            transcribe_btn = gr.Button(_("auto_transcribe"))
        ref_text = gr.Textbox(label=_("ref_text"), lines=2)
        text = gr.Textbox(label=_("text"), lines=4)
        with gr.Row():
            gen_language = gr.Dropdown(
                label=_("gen_language"),
                choices=config.GEN_LANGUAGE_CHOICES,
                value="Auto",
            )
            x_vector_only = gr.Checkbox(label=_("x_vector_only"), value=False)
        btn = gr.Button(_("generate"), variant="primary")
        out_audio = gr.Audio(label=_("output_audio"), type="numpy")
        status = gr.Textbox(label=_("status"), value=_("ready"), interactive=False)

        transcribe_btn.click(
            transcribe,
            inputs=[ref_audio, whisper_model, transcribe_language],
            outputs=[ref_text, status],
        )
        btn.click(
            generate,
            inputs=[text, ref_audio, ref_text, gen_language, x_vector_only],
            outputs=[out_audio, status],
        )
