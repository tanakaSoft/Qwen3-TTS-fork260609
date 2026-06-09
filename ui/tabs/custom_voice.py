# coding=utf-8
# Fork addition (not part of upstream Qwen3-TTS).
#
# Custom Voice tab: pick/load a CustomVoice model (fine-tuned checkpoint or the
# official preset model), then generate speech with it.
# SPDX-License-Identifier: Apache-2.0
import gradio as gr

from ui import config
from ui.client import get_client
from ui.i18n import t


def create_custom_voice_tab(lang: str) -> None:
    def _(key: str) -> str:
        return t(lang, key)

    def list_models():
        """Return (dropdown choices, current-loaded label) for the model picker."""
        try:
            data = get_client().list_custom_models()
            # choices as (display, path) so the value is the loadable path/id.
            choices = [(m["name"], m["path"]) for m in data.get("models", [])]
            loaded = data.get("loaded")
            return choices, loaded
        except Exception:  # noqa: BLE001 - server may be down at build time
            return [], None

    def refresh_models():
        choices, loaded = list_models()
        current = loaded or _("cv_none")
        return gr.update(choices=choices, value=loaded), f"{_('cv_current')}: {current}"

    def load_model(model_path):
        if not model_path:
            return _("cv_no_models"), gr.update()
        try:
            result = get_client().load_custom_model(model_path)
            speakers = result.get("speakers") or []
            speaker_update = (
                gr.update(choices=speakers, value=(speakers[0] if speakers else None))
                if speakers
                else gr.update()
            )
            return f"{_('cv_loaded')}: {result.get('loaded')}", speaker_update
        except ConnectionError:
            return _("not_connected"), gr.update()
        except Exception as exc:  # noqa: BLE001
            return f"{_('error')}: {exc}", gr.update()

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

    init_choices, init_loaded = list_models()

    with gr.Column():
        # --- Model selection -------------------------------------------------
        with gr.Row():
            model_dd = gr.Dropdown(
                label=_("cv_model"),
                choices=init_choices,
                value=init_loaded,
                scale=3,
            )
            load_btn = gr.Button(_("cv_load"), scale=1)
            refresh_btn = gr.Button(_("cv_refresh_models"), scale=1)
        model_status = gr.Textbox(
            label=_("cv_current"),
            value=(init_loaded or _("cv_none")),
            interactive=False,
        )

        # --- Generation ------------------------------------------------------
        text = gr.Textbox(label=_("text"), lines=4)
        with gr.Row():
            speaker = gr.Dropdown(
                label=_("speaker"),
                choices=["speaker_custom"],
                value="speaker_custom",
                allow_custom_value=True,
            )
            gen_language = gr.Dropdown(
                label=_("gen_language"),
                choices=config.GEN_LANGUAGE_CHOICES,
                value=config.DEFAULT_GEN_LANGUAGE,
            )
        instruct = gr.Textbox(label=_("instruct"), lines=2)
        btn = gr.Button(_("generate"), variant="primary")
        out_audio = gr.Audio(label=_("output_audio"), type="numpy")
        status = gr.Textbox(label=_("status"), value=_("ready"), interactive=False)

        refresh_btn.click(refresh_models, outputs=[model_dd, model_status])
        load_btn.click(load_model, inputs=[model_dd], outputs=[model_status, speaker])
        btn.click(
            generate,
            inputs=[text, speaker, instruct, gen_language],
            outputs=[out_audio, status],
        )
