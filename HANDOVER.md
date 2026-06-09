# Handover — Qwen3-TTS Studio (local Windows testing)

**Date:** 2026-06-10
**Branch:** `claude/qwen3-tts-finetuning-6lixq8`
**Status:** ✅ **Verified end-to-end on local Windows 11 + RTX 5090.** All Test
checklist items below pass. No application-code changes were needed — the only
fixes were to the **setup steps** (see "Local verification results"). Stack
actually used: Python 3.12.13, torch 2.11.0+cu128, transformers 4.57.3,
gradio 6.17.3, fastapi/starlette 1.x.

---

## What this is

A **TTS API server** (models resident on the GPU) plus a **Gradio Web UI** that
is a *thin client* over that API. Other apps on the same PC call the same API.

```
  API server (:8001)  ── loads models ONCE on the GPU
     ├ /generate_voice_design / _voice_clone / _custom_voice
     ├ /custom_models / load_custom_model  (pick fine-tuned or preset)
     ├ /auto_transcribe  (Whisper, fills VoiceClone ref_text)
     ├ /gpu_stats /clear_gpu_cache
     └ /finetune_async ...
        ↑ HTTP                ↑ HTTP
  Web UI (:7860)          your other apps
  = thin client           = same API
```

**Key design decisions (already made):**
- Attention = **eager** (official PyTorch, no Flash Attention 2 wheels).
- Whisper = **transformers** implementation (no faster-whisper / ffmpeg / cuDNN).
- UI talks to the API over HTTP; **models load only once** (in the server).
- `qwen_tts/` is **never modified** → upstream merges stay conflict-free.

---

## Why testing must happen locally

The cloud dev environment has **no GPU, no models, not Windows**, so the server
and UI cannot actually run there. All Python was written and **syntax-checked
(`py_compile`) only**. Everything below needs a real run on your machine.

---

## Setup (Windows, once)

See `docs/windows_setup.md` for the full guide. Short version:

```powershell
git clone https://github.com/tanakaSoft/Qwen3-TTS-fork260609.git
cd Qwen3-TTS-fork260609
git checkout claude/qwen3-tts-finetuning-6lixq8
git pull origin claude/qwen3-tts-finetuning-6lixq8

uv venv --python 3.12
.venv\Scripts\activate
uv pip install -e .
uv pip install --reinstall torch torchaudio --index-url https://download.pytorch.org/whl/cu128
uv pip install -r server\requirements-server.txt
```

No Flash Attention 2, no faster-whisper, no ffmpeg needed.

> ⚠️ **Do NOT use `uv sync`.** Upstream `pyproject.toml` declares
> `requires-python = ">=3.9"`, but `accelerate==1.12.0` needs Python>=3.10, so
> `uv sync`'s universal resolver fails. We must not edit the upstream
> `pyproject.toml`, so use `uv pip install -e .` (resolves for the active
> interpreter only). Then **`--reinstall`** torch from the cu128 index — a plain
> install is a no-op because the CPU build already satisfies the version pin,
> leaving you on `2.x+cpu` with no GPU.

---

## Run

**One-click (recommended):** double-click `Qwen3-TTS-Studio.bat`
(starts API → waits for `/health` → starts UI → opens browser).

**Manual (two terminals):**
```powershell
# Terminal 1 — API server
.venv\Scripts\activate
python server\tts_server_async.py

# Terminal 2 — Web UI
.venv\Scripts\activate
python ui\launch_ui.py
```

---

## Test checklist (please verify locally)

### API server
- [ ] Server starts; `http://localhost:8001/health` returns `status: ok`.
- [ ] `http://localhost:8001/docs` shows all endpoints incl. `/auto_transcribe`,
      `/gpu_stats`, `/whisper_models`.
- [ ] `/gpu_stats` returns real VRAM numbers (RTX 5090 ~32 GB total).
- [ ] VoiceDesign generation works (client smoke test in `tts_client_async.py`).

### Whisper auto-transcription
- [ ] `POST /auto_transcribe` with a short WAV returns text.
- [ ] First call downloads `openai/whisper-large-v3` (~3 GB) to the HF cache;
      second call is fast (cached).
- [ ] **Watch for**: the transformers ASR pipeline call signature. We pass
      `{"raw": waveform, "sampling_rate": 16000}` + `generate_kwargs`. If the
      installed transformers version rejects `generate_kwargs=None`, change the
      call in `server/tts_whisper.py` to omit it when empty.

### Web UI (the most likely place to need fixes — untestable in cloud)
- [ ] UI launches; browser opens at `/ja`.
- [ ] All 5 tabs render. Custom / Design / Clone / Fine-tuning / Settings.
- [ ] Fine-tuning tab: start a small job, progress auto-polls (gr.Timer),
      completed model becomes usable in the Custom Voice tab.
- [ ] **Language selector** switches routes (`/ja` ↔ `/en` …). This relies on
      `gr.mount_gradio_app(...)` per language + a JS navigation in `ui/app.py`.
      If the JS `.change(fn=None, js=...)` form errors on your Gradio version,
      replace with a small `fn` that returns nothing, or use `gr.Dropdown`'s
      newer JS hook.
- [ ] **Settings tab GPU auto-refresh** uses `gr.Timer`. If `gr.Timer` is not
      in your Gradio version, fall back to `demo.load(refresh, every=N)`.
- [ ] Audio output components accept `(sample_rate, np.ndarray)` — confirm
      playback. If not, set `gr.Audio(type="numpy")` expectations accordingly.
- [ ] Voice Clone: upload WAV → "Auto Transcribe" fills ref text → "Generate".

### CustomVoice model picker (new)
- [ ] Custom Voice tab: "Refresh" lists fine-tuned models under `outputs/` plus
      the official preset; "Load" loads the selected model.
- [ ] `GET /custom_models` returns the list + currently-loaded path.
- [ ] `POST /load_custom_model` loads the **official preset**
      (`Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`) — first load downloads from HF.
- [ ] **VRAM swap**: loading a new model frees the old one first
      (`models["custom"]=None; gc; empty_cache`). Confirm no OOM on RTX 5090
      when switching between models.
- [ ] After load, the speaker dropdown is populated from the model's preset
      speakers (`get_supported_speakers`). Generation with a preset speaker works.

### Multi-app / API reuse
- [ ] From a separate Python process, `QwenTTSAsyncClient("http://localhost:8001")`
      connects and generates while the UI is also running (lock serializes GPU).

---

## Local verification results (2026-06-10, Windows 11 + RTX 5090)

Every Test-checklist item above passed. Highlights:

- **API server**: `/health` ok, `/docs` shows all endpoints, `/gpu_stats` reads
  real VRAM. VoiceDesign generated 24 kHz audio (client smoke test in
  `tts_client_async.py` saved `design_test.wav`).
- **Whisper**: `/auto_transcribe` works — 1st call ~24 s (model load), 2nd ~2.6 s
  (cached). transformers 4.57.3 accepts `generate_kwargs={"language": ...}` and
  `{"raw": waveform, "sampling_rate": 16000}` — **no fix needed**.
- **Web UI (gradio 6.17.3)**: all 5 tabs render, route mounting (`/ja`, `/en`, …)
  works, `gr.Timer` exists and the Settings GPU refresh returns live VRAM. Audio
  components are `type="numpy"` and the tabs return `(sr, ndarray)` — playback OK.
  End-to-end UI generation verified via `gradio_client` against `/generate_1`.
- **CustomVoice picker**: `/custom_models` lists preset, `/load_custom_model`
  loads `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`. **VRAM swap**: used stayed flat
  (~16.7 GB) across free-then-load — no OOM. Speaker dropdown populated with 9
  preset speakers; generation with `serena` works.
- **Multi-app**: 3 concurrent client processes all succeeded, serialized by
  `_GEN_LOCK` (staggered completion), while the UI was also running.

### Non-blocking deprecation warnings (cosmetic, left as-is)

| Where | Warning | Note |
|---|---|---|
| `server/tts_server_async.py` `@app.on_event("startup")` | FastAPI: use lifespan handlers | still works on starlette 1.x |
| `server/tts_whisper.py` `torch_dtype=` | transformers: use `dtype=` | pipeline still honors `torch_dtype` on 4.57.3 |
| qwen_tts import | "SoX could not be found" | upstream `sox` pkg; not needed for the verified paths |

## Known risk points — all verified OK against the installed versions

| Area | File | Result |
|---|---|---|
| Gradio version API | `ui/app.py`, `ui/tabs/settings.py` | ✅ `gr.Timer`, JS `.change(js=...)`, `mount_gradio_app` all present in 6.17.3 |
| transformers ASR call | `server/tts_whisper.py` | ✅ `generate_kwargs` + raw-array input accepted on 4.57.3 |
| Audio tuple format | `ui/tabs/*.py` | ✅ `(sr, ndarray)` → `gr.Audio(type="numpy")` plays back |
| CustomVoice VRAM swap | `server/tts_server_async.py` `load_custom_model` | ✅ free-then-load, no OOM on RTX 5090 |
| Dropdown dynamic update | `ui/tabs/custom_voice.py` | ✅ speaker dropdown populated from `get_supported_speakers` |
| `.bat` health wait | `Qwen3-TTS-Studio.bat` | not re-tested (manual launch used); see note below |

---

## Upstream updates (when QwenLM/Qwen3-TTS changes)

```powershell
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
git checkout claude/qwen3-tts-finetuning-6lixq8
git merge main   # server/ ui/ are ours; qwen_tts/ stays in sync, no conflicts
```

See `FORK_CHANGES.md` → "upstream（本家）追従戦略".

---

## File map

| Path | Purpose |
|---|---|
| `server/tts_server_async.py` | API server (TTS + Whisper + GPU + finetune) |
| `server/tts_whisper.py` | transformers Whisper wrapper |
| `server/tts_client_async.py` | HTTP client library |
| `ui/app.py` | builds the 4-tab UI per language |
| `ui/launch_ui.py` | UI launcher (auto-port, browser, route mounting) |
| `ui/tabs/*.py` | the four tabs |
| `ui/i18n.py` | 10-language translations |
| `Qwen3-TTS-Studio.bat` | Windows one-click launcher |
| `docs/webui_setup.md` | Web UI guide |
| `docs/api_server.md` | API reference |
| `docs/windows_setup.md` | Windows setup |

---

**When you hit a runtime issue locally:** note the file + error and we fix it in
the next session. The structure is in place; remaining work is runtime
adjustment against your actual Gradio / transformers versions.
