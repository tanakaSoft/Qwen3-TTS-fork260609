# Handover — Qwen3-TTS Studio (local Windows testing)

**Date:** 2026-06-09
**Branch:** `claude/qwen3-tts-finetuning-6lixq8`
**Status:** Code written & syntax-checked in the cloud. **Needs local run/test on Windows + RTX 5090.**

---

## What this is

A **TTS API server** (models resident on the GPU) plus a **Gradio Web UI** that
is a *thin client* over that API. Other apps on the same PC call the same API.

```
  API server (:8001)  ── loads models ONCE on the GPU
     ├ /generate_voice_design / _voice_clone / _custom_voice
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

uv sync
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -r server\requirements-server.txt
```

No Flash Attention 2, no faster-whisper, no ffmpeg needed.

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

### Multi-app / API reuse
- [ ] From a separate Python process, `QwenTTSAsyncClient("http://localhost:8001")`
      connects and generates while the UI is also running (lock serializes GPU).

---

## Known risk points (cloud-unverifiable)

| Area | File | Risk / fallback |
|---|---|---|
| Gradio version API | `ui/app.py`, `ui/tabs/settings.py` | `gr.Timer`, JS `.change`, route mounting may differ by version |
| transformers ASR call | `server/tts_whisper.py` | `generate_kwargs` / raw-array input signature |
| Audio tuple format | `ui/tabs/*.py` | Gradio expects `(sr, ndarray)` for numpy audio |
| `.bat` health wait | `Qwen3-TTS-Studio.bat` | PowerShell `Invoke-RestMethod` availability/policy |

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
