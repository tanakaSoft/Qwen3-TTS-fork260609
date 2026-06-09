# Qwen3-TTS Async API Server (fork addition)

A FastAPI server that keeps Qwen3-TTS models resident on the GPU and serves
**CustomVoice / VoiceDesign / VoiceClone** generation plus **asynchronous
fine-tuning** over HTTP. Designed to run inside WSL2 and be called from both
Windows apps and other WSL2 apps on the same machine.

> This is a fork addition. It lives entirely under `server/` and `docs/` and
> does not modify upstream `qwen_tts/` code. See `FORK_CHANGES.md`.

---

## 1. Install

Inside WSL2, with the `qwen-tts` environment active:

```bash
cd /home/user/Qwen3-TTS-fork260609
pip install -e .                                  # core qwen-tts package
pip install -r server/requirements-server.txt     # fastapi / uvicorn / requests
```

GPU note: RTX 5090 requires a CUDA 12.8+ PyTorch build. FlashAttention 2 is used
by default; set `QWEN_TTS_ATTN=eager` to disable it.

---

## 2. Start the server

```bash
python server/tts_server_async.py
```

Then open the interactive docs at <http://localhost:8001/docs>.

### Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `QWEN_TTS_HOST` | `0.0.0.0` | Bind address (0.0.0.0 makes it reachable from Windows) |
| `QWEN_TTS_PORT` | `8001` | Port |
| `QWEN_TTS_DEVICE` | `cuda:0` | Torch device |
| `QWEN_TTS_ATTN` | `flash_attention_2` | Attention impl (`eager` to disable) |
| `QWEN_TTS_LOAD` | `voice_design,voice_clone,custom` | Which models to load at startup |
| `QWEN_TTS_BASE` | `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | Base model (VoiceClone) |
| `QWEN_TTS_VOICE_DESIGN` | `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | VoiceDesign model |
| `QWEN_TTS_CUSTOM` | _(empty)_ | Path to a fine-tuned CustomVoice checkpoint to load at startup |
| `QWEN_TTS_TOKENIZER` | `Qwen/Qwen3-TTS-Tokenizer-12Hz` | Tokenizer used by fine-tuning |

Loading all three models needs roughly 10 GB VRAM. On a smaller GPU, load just
one, e.g.:

```bash
QWEN_TTS_LOAD=voice_clone python server/tts_server_async.py
```

---

## 3. Endpoints

| Method | Path | Description |
|---|---|---|
| GET  | `/health` | Server + model status |
| GET  | `/supported_speakers` | Speaker list of the active model |
| GET  | `/supported_languages` | Language list of the active model |
| POST | `/generate_custom_voice` | CustomVoice (fine-tuned model) |
| POST | `/batch_generate_custom_voice` | CustomVoice, multiple texts in one call |
| POST | `/generate_voice_design` | VoiceDesign from a natural-language instruct |
| POST | `/generate_voice_clone` | VoiceClone from an uploaded reference clip |
| POST | `/finetune_async` | Start a background fine-tuning job |
| GET  | `/finetune_status/{job_id}` | Poll a fine-tuning job |
| GET  | `/finetune_jobs` | List all fine-tuning jobs |

Audio responses return 16-bit PCM as base64 in `audio_base64`, with the
`sample_rate`. The client library decodes this back into a float waveform.

---

## 4. Client usage

`server/tts_client_async.py` is a dependency-light client (`requests`, `numpy`,
`soundfile` — no torch). It works from Windows too.

```python
from server.tts_client_async import QwenTTSAsyncClient

tts = QwenTTSAsyncClient("http://localhost:8001")

# VoiceDesign
audio, sr = tts.generate_voice_design(
    text="こんにちは、今日はいい天気ですね。",
    instruct="落ち着いた大人の女性の声で、ゆっくり丁寧に",
)
tts.save_speech(audio, sr, "design.wav")

# VoiceClone (upload a reference clip)
audio, sr = tts.generate_voice_clone(
    text="これはクローンした声です。",
    ref_audio_path="reference.wav",
    ref_text="参考音声の文字起こしです。",
    language="Japanese",
)
tts.save_speech(audio, sr, "clone.wav")
```

### Fine-tuning then generating

```python
job_id = tts.start_finetune(
    train_jsonl="/home/user/Qwen3-TTS-fork260609/train_raw.jsonl",
    output_model_name="my_voice",
    num_epochs=10,
    speaker_name="my_speaker",
)
tts.wait_finetune_completion(job_id)   # prints progress until done

# The fine-tuned model is now the active CustomVoice model:
audio, sr = tts.generate_custom_voice(
    text="ファインチューニングした声です。",
    speaker="my_speaker",
    instruct="元気よく",
)
tts.save_speech(audio, sr, "finetuned.wav")
```

`train_jsonl` is the **raw** JSONL (`audio` / `text` / `ref_audio` per line);
the server runs `prepare_data.py` automatically before training. See
`finetuning/README.md` for the data format.

---

## 5. Notes & limitations

- **Single GPU, serialized requests.** The server holds models in memory and
  processes requests one at a time on the GPU. For higher throughput, batch via
  `/batch_generate_custom_voice` rather than issuing many parallel requests.
- **Fine-tuning runs as an in-process background task.** Only one should run at a
  time (it uses the GPU fully). The job registry is in-memory and resets when the
  server restarts.
- **Reachability from Windows.** With `QWEN_TTS_HOST=0.0.0.0`, WSL2 forwards
  `localhost:8001` to Windows automatically on recent Windows versions. If not
  reachable, use the WSL2 IP from `hostname -I`.
- For production, put this behind a process manager (e.g. systemd) and consider a
  real job queue + persistent storage for fine-tuning jobs.
