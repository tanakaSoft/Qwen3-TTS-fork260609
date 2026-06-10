# Qwen3-TTS Studio (fork)

A **Windows-native fork of [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)** that adds:

- 🎛️ **A resident TTS API server** — models stay on the GPU and serve every app on your PC over HTTP.
- 🌐 **A Gradio Web UI** — 5 tabs, 10-language interface, runs as a thin client over the API.
- 📝 **Whisper auto-transcription** — fills the reference text for Voice Clone automatically.
- 🛠️ **Fine-tuning from the browser** — start a job, watch progress, then use the model immediately.
- 🖱️ **One-click launch on Windows** — `Qwen3-TTS-Studio.bat` starts everything and opens the browser.

> The upstream `README.md` is kept **unchanged** so updates from QwenLM/Qwen3-TTS
> merge cleanly. This file documents the fork. See `FORK_CHANGES.md` for the full
> change log and upstream-tracking strategy.

---

## Why this fork

| | Upstream Qwen3-TTS | This fork |
|---|---|---|
| Run target | Linux-focused | **Windows-native** (RTX 5090, CUDA 12.8) |
| Attention | Flash Attention 2 | **eager** (official PyTorch, no risky wheels) |
| Interface | Gradio demo | **API server + Web UI** (thin client) |
| Reference text (clone) | Manual | **Whisper auto-transcription** |
| Multi-app use | — | **Shared HTTP API on one GPU** |

The fork deliberately avoids non-official native dependencies (Flash Attention 2
wheels, faster-whisper / CTranslate2 / cuDNN, ffmpeg). Everything rides the
official `torch` (cu128) + `transformers` stack already required by Qwen3-TTS.

---

## Architecture

```
  API server (:8001) ── loads models ONCE on the GPU
     ├ /generate_voice_design / _voice_clone / _custom_voice
     ├ /auto_transcribe   (Whisper → ref_text)
     ├ /gpu_stats / _clear_gpu_cache
     └ /finetune_async / _status / _jobs
        ↑ HTTP                 ↑ HTTP
  Web UI (:7860)           your other apps
  = thin client            = same HTTP API
```

One GPU, one model load. The Web UI uses the same API every other app uses —
so running the UI continuously validates the API for all clients.

---

## Quick start (Windows + RTX 5090)

```powershell
git clone https://github.com/tanakaSoft/Qwen3-TTS-fork260609.git
cd Qwen3-TTS-fork260609
git checkout claude/qwen3-tts-finetuning-6lixq8

uv venv --python 3.12
.venv\Scripts\activate
uv pip install -e .
uv pip install --reinstall torch torchaudio --index-url https://download.pytorch.org/whl/cu128
uv pip install -r server\requirements-server.txt
```

> Do **not** use `uv sync` — upstream's `requires-python = ">=3.9"` conflicts
> with `accelerate`'s `>=3.10` and the universal resolve fails. The `--reinstall`
> on torch is required: without it the CPU build stays in place.

Then **double-click `Qwen3-TTS-Studio.bat`** (starts API → waits for `/health`
→ starts UI → opens the browser).

Full setup: **`docs/windows_setup.md`**.

---

## The 5 tabs

| Tab | What it does |
|---|---|
| **Custom Voice** | Generate with a fine-tuned CustomVoice model |
| **Voice Design** | Synthesize from a natural-language voice description |
| **Voice Clone** | Clone from a reference clip; **Whisper auto-fills the reference text** |
| **Fine-tuning** | Start a background fine-tuning job and watch progress |
| **Settings** | Live GPU/VRAM stats (auto-refresh) + clear GPU cache |

---

## Fine-tuning from the Web UI

Train a custom voice in the browser — no scripts needed.

**1. Prepare training data** — one JSONL file, one line per clip:

```json
{"audio": "C:/data/clip1.wav", "text": "クリップ1の書き起こし", "ref_audio": "C:/data/ref.wav"}
{"audio": "C:/data/clip2.wav", "text": "クリップ2の書き起こし", "ref_audio": "C:/data/ref.wav"}
```

Paths must be readable by the API server (same PC). `text` is the transcript of
`audio`; `ref_audio` is a clip of the target voice. See `finetuning/README.md`.

**2. Start the job** — open the **Fine-tuning** tab:

| Field | Meaning |
|---|---|
| Training JSONL | Full path to the file above |
| Model name | Output folder name → `outputs/<name>/` |
| Speaker name | Name you will select when generating (e.g. `my_speaker`) |
| Epochs / Batch / LR | Training knobs (defaults: 10 / 32 / 2e-6) |

Click **Start**. A `job_id` appears and progress auto-refreshes every 5 s
(data prep → training → loading the result). The job runs in the API server,
so closing the browser does not stop it.

**3. Use the voice** — when progress reaches 100%, the new checkpoint is
**auto-loaded as the active CustomVoice model**. Switch to the **Custom Voice**
tab, enter your speaker name, and generate. Checkpoints are saved under
`outputs/<model name>/checkpoint-epoch-N` and stay selectable later via the
Custom Voice tab's model picker (**Refresh** → select → **Load**), which also
survives server restarts.

---

## Use the API from your own apps

The UI is optional — any app on the PC can call the API directly:

```python
from server.tts_client_async import QwenTTSAsyncClient

tts = QwenTTSAsyncClient("http://localhost:8001")

# Whisper-transcribe a reference clip, then clone the voice
ref_text = tts.auto_transcribe("reference.wav", model="large-v3")
audio, sr = tts.generate_voice_clone(
    text="これはクローンした声です。",
    ref_audio_path="reference.wav",
    ref_text=ref_text,
    language="Japanese",
)
tts.save_speech(audio, sr, "clone.wav")
```

---

## Documentation

| Doc | Contents |
|---|---|
| `docs/windows_setup.md` | Windows setup, step by step |
| `docs/webui_setup.md` | Web UI guide (launch, tabs, multilingual, API reuse) |
| `docs/api_server.md` | API reference (endpoints, config, client, fine-tuning) |
| `FORK_CHANGES.md` | Change log, restore points, upstream-tracking strategy |
| `README.md` | Upstream Qwen3-TTS README (unchanged) |

---

## Configuration (env vars)

| Variable | Default | Purpose |
|---|---|---|
| `QWEN_TTS_PORT` | `8001` | API server port |
| `QWEN_TTS_LOAD` | `voice_design,voice_clone,custom` | Models to load |
| `QWEN_TTS_ATTN` | `eager` | Attention implementation |
| `QWEN_TTS_WHISPER` | `large-v3` | Default Whisper model |
| `QWEN_TTS_CUSTOM` | _(empty)_ | Fine-tuned checkpoint to load at startup |
| `QWEN_TTS_API_URL` | `http://localhost:8001` | API URL the UI targets |
| `QWEN_TTS_UI_LANG` | `ja` | Default UI language |

See `docs/api_server.md` and `docs/webui_setup.md` for the complete list.

---

## License

Apache-2.0 (inherited from upstream). See `LICENSE` and `NOTICE`.
