# Handover — Qwen3-TTS Fork Development

## Current Status

**Date:** 2026-06-09  
**Branch:** `claude/qwen3-tts-finetuning-6lixq8`  
**Development environment:** Windows (local development completed)  
**Next step:** WSL2 deployment

---

## What's Done (Windows Development)

### Files Created
- `server/tts_server_async.py` — FastAPI server (CustomVoice, VoiceDesign, VoiceClone, async fine-tuning)
- `server/tts_client_async.py` — Lightweight HTTP client (no GPU dependency)
- `server/requirements-server.txt` — API server dependencies
- `docs/windows_setup.md` — Windows PowerShell setup guide (11 steps)
- `docs/api_server.md` — API reference & usage guide
- `FORK_CHANGES.md` — Fork documentation & design philosophy

### Design Decisions
- **Attention implementation:** Eager (standard PyTorch), **not** Flash Attention 2 wheels
  - Why: Official support, zero risk, RTX 5090 32GB is sufficient
  - Non-official FA2 wheels (marcorez8, etc.) rejected due to maintenance risk
- **Architecture:** Async API server (FastAPI) + lightweight client
- **Platform:** Windows primary, WSL2 alternative (both use eager)

---

## What's Next: WSL2 Deployment

### Before Moving to WSL2

1. **Verify Windows setup works** (optional, but recommended to confirm API behavior)
2. **Test local HuggingFace cache**
   - Existing cache at `C:\Users\bshon\.cache\huggingface\hub\` will be reused
   - Cache is shared if using WSL2 with Windows GPU passthrough
3. **Plan WSL2 cache location**
   - WSL2 will use `~/.cache/huggingface` (typically `/root/.cache/huggingface` in WSL2 root)
   - Models will be **re-downloaded to WSL2** (separate from Windows cache)

### WSL2 Setup Steps

```bash
# 1. Clone/checkout on WSL2
cd /path/to/projects
git clone https://github.com/tanakaSoft/Qwen3-TTS-fork260609.git
cd Qwen3-TTS-fork260609
git checkout claude/qwen3-tts-finetuning-6lixq8

# 2. Install uv (Rust-based package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# 3. Create virtual environment & dependencies
uv sync
source .venv/bin/activate

# 4. Install PyTorch (CUDA 12.8)
pip install torch --index-url https://download.pytorch.org/whl/cu128

# 5. Install API server dependencies (no FA2 needed)
pip install -r server/requirements-server.txt

# 6. Start server
python server/tts_server_async.py
# Should print: "Uvicorn running on http://0.0.0.0:8001"
```

### WSL2 Configuration Notes

**Environment variables (bash):**
```bash
# Optional: customize server behavior
export QWEN_TTS_DEVICE="cuda:0"       # GPU device
export QWEN_TTS_HOST="0.0.0.0"        # Listen on all interfaces
export QWEN_TTS_PORT="8001"           # Port
export QWEN_TTS_LOAD="voice_design,voice_clone,custom"  # Models to load
export QWEN_TTS_ATTN="eager"          # Attention (eager is default)

python server/tts_server_async.py
```

**Model cache (WSL2 specific):**
```bash
# Models will be downloaded to:
~/.cache/huggingface

# To override:
export HF_HOME="/path/to/large/disk/huggingface"
python server/tts_server_async.py
```

---

## Testing Checklist (WSL2)

After starting the server on WSL2:

1. **API health check**
   ```bash
   curl http://localhost:8001/health
   # Should return JSON with status: "ok"
   ```

2. **Swagger UI**
   - Open browser: http://localhost:8001/docs
   - Should see FastAPI interactive documentation

3. **Client test** (from WSL2 or Windows)
   ```python
   from server.tts_client_async import QwenTTSAsyncClient
   
   tts = QwenTTSAsyncClient("http://localhost:8001")
   audio, sr = tts.generate_voice_design(
       text="これはテストです。",
       instruct="明るく元気な女性の声",
       language="Japanese"
   )
   tts.save_speech(audio, sr, "test.wav")
   print("✅ Audio saved to test.wav")
   ```

4. **Windows client → WSL2 server** (if testing cross-platform)
   - Replace `localhost` with WSL2 IP or hostname
   - Confirm Windows Defender allows Python network access

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `server/tts_server_async.py` | Main API server |
| `server/tts_client_async.py` | HTTP client library |
| `server/requirements-server.txt` | Dependencies |
| `docs/windows_setup.md` | Windows setup (reference) |
| `docs/api_server.md` | API documentation |
| `FORK_CHANGES.md` | Fork design & history |

---

## Important Notes

### Eager Attention (Not Flash Attention 2)
- **Why:** Official PyTorch support, zero risk, sufficient for RTX 5090 32GB
- **Memory:** ~12-14 GB with all models loaded (comfortable on RTX 5090)
- **Performance:** 100% baseline; adequate for real-world use
- **No wheels needed:** Eager is part of PyTorch core

### Model Download & Cache
- First startup will download models (~2-3 GB total) to HuggingFace cache
- **Windows cache** (`C:\Users\bshon\.cache\huggingface`) is separate from **WSL2 cache** (`~/.cache/huggingface`)
- Models will re-download on WSL2 (unless cache is shared via mount)

### Multi-App Usage (WSL2 + Windows)
- API server runs on WSL2, listens on `http://0.0.0.0:8001`
- Windows apps can connect via `http://<wsl2-ip>:8001` or WSL2 hostname
- WSL2 apps can use `http://localhost:8001` directly
- Single server, serialized requests (not parallel due to GPU memory)

---

## Troubleshooting (WSL2)

### "CUDA out of memory"
- Try loading fewer models: `export QWEN_TTS_LOAD="voice_clone"`
- Check GPU memory: `nvidia-smi`
- Reduce batch size in API requests

### "Cannot import torch"
- Ensure PyTorch is installed: `python -c "import torch; print(torch.cuda.is_available())"`
- Should print: `True` (if NVIDIA driver & CUDA 12.8 available)

### Models not downloading
- Check HF_HOME is writable: `ls ~/.cache/huggingface`
- Internet access from WSL2: `curl https://huggingface.co` (should succeed)

### WSL2 GPU access issues
- Verify NVIDIA driver on Windows: `nvidia-smi` (Windows PowerShell)
- WSL2 uses Windows GPU passthrough (no separate driver needed in WSL2)
- If no GPU: fallback to CPU (slow, for testing only)

---

## Next Steps After WSL2 Deployment

1. **Fine-tuning setup**
   - Prepare training data: `finetuning/README.md`
   - Test fine-tuning API: `/finetune_async` endpoint

2. **Video generation integration** (later phase)
   - Use client library to call TTS API
   - Integrate with video automation software

3. **Production deployment** (future)
   - Consider process manager (systemd on Linux, NSSM on Windows)
   - Persistent job storage (currently in-memory)

---

**Last updated:** 2026-06-09  
**Session:** claude-code (Windows development)  
**Branch:** `claude/qwen3-tts-finetuning-6lixq8`  
**Status:** Ready for WSL2 migration
