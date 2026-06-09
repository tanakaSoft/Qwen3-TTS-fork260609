# coding=utf-8
# Fork addition (not part of upstream Qwen3-TTS).
#
# Fine-tuning tab: start a background fine-tuning job and poll its progress.
# The job runs server-side (one at a time); when it completes, the fine-tuned
# model becomes the active CustomVoice model usable from the Custom Voice tab.
# SPDX-License-Identifier: Apache-2.0
import gradio as gr

from ui.client import get_client
from ui.i18n import t


def create_finetune_tab(lang: str) -> None:
    def _(key: str) -> str:
        return t(lang, key)

    def start(train_jsonl, output_model_name, speaker_name, num_epochs, batch_size, lr):
        if not (train_jsonl or "").strip():
            return "", _("error") + ": " + _("ft_need_jsonl")
        try:
            client = get_client()
            job_id = client.start_finetune(
                train_jsonl=train_jsonl,
                output_model_name=output_model_name or "finetuned_model",
                num_epochs=int(num_epochs),
                batch_size=int(batch_size),
                lr=float(lr),
                speaker_name=speaker_name or "speaker_custom",
            )
            return job_id, f"{_('ft_started')} (job_id={job_id})"
        except ConnectionError:
            return "", _("not_connected")
        except Exception as exc:  # noqa: BLE001
            return "", f"{_('error')}: {exc}"

    def poll(job_id):
        if not (job_id or "").strip():
            return "", _("ft_no_job")
        try:
            status = get_client().get_finetune_status(job_id)
            progress = status.get("progress", 0)
            state = status.get("status", "?")
            message = status.get("message", "")
            bar = "█" * (progress // 5) + "░" * (20 - progress // 5)
            text = f"[{bar}] {progress}%  ({state})\n{message}"
            if status.get("model_path"):
                text += f"\n{_('ft_model_path')}: {status['model_path']}"
            return text, state
        except ConnectionError:
            return _("not_connected"), "error"
        except Exception as exc:  # noqa: BLE001
            return f"{_('error')}: {exc}", "error"

    def list_jobs():
        try:
            data = get_client().list_finetune_jobs()
            jobs = data.get("jobs", [])
            if not jobs:
                return _("ft_no_jobs")
            lines = [
                f"- `{j['job_id'][:8]}…`  {j.get('status', '?'):10s} "
                f"{j.get('progress', 0):3d}%  {j.get('message', '')}"
                for j in jobs
            ]
            return "\n".join(lines)
        except ConnectionError:
            return _("not_connected")
        except Exception as exc:  # noqa: BLE001
            return f"{_('error')}: {exc}"

    with gr.Column():
        gr.Markdown(f"## {_('tab_finetune')}")
        gr.Markdown(_("ft_help"))

        train_jsonl = gr.Textbox(
            label=_("ft_train_jsonl"),
            placeholder=r"C:\Users\you\train_raw.jsonl",
        )
        with gr.Row():
            output_model_name = gr.Textbox(label=_("ft_model_name"), value="my_voice")
            speaker_name = gr.Textbox(label=_("ft_speaker_name"), value="my_speaker")
        with gr.Row():
            num_epochs = gr.Slider(
                label=_("ft_epochs"), minimum=1, maximum=50, step=1, value=10
            )
            batch_size = gr.Slider(
                label=_("ft_batch_size"), minimum=1, maximum=64, step=1, value=32
            )
            lr = gr.Number(label=_("ft_lr"), value=2e-6)

        start_btn = gr.Button(_("ft_start"), variant="primary")

        with gr.Row():
            job_id = gr.Textbox(label=_("ft_job_id"), interactive=True)
            state = gr.Textbox(label=_("status"), value=_("ready"), interactive=False)

        progress_box = gr.Textbox(label=_("ft_progress"), lines=4, interactive=False)
        with gr.Row():
            poll_btn = gr.Button(_("ft_poll"))
            refresh_jobs_btn = gr.Button(_("ft_list_jobs"))

        jobs_box = gr.Markdown("")

        # Auto-poll the active job's progress while a job is running.
        timer = gr.Timer(5)

        start_btn.click(
            start,
            inputs=[train_jsonl, output_model_name, speaker_name, num_epochs, batch_size, lr],
            outputs=[job_id, state],
        )
        poll_btn.click(poll, inputs=[job_id], outputs=[progress_box, state])
        timer.tick(poll, inputs=[job_id], outputs=[progress_box, state])
        refresh_jobs_btn.click(list_jobs, outputs=[jobs_box])
