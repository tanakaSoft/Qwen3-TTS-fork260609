# Qwen3-TTS Async API Server (fork addition)

A FastAPI server that keeps Qwen3-TTS models resident on the GPU and serves
**CustomVoice / VoiceDesign / VoiceClone** generation plus **asynchronous
fine-tuning** over HTTP. Designed to run on **Windows (primary)** or **WSL2 (alternative)**.

> This is a fork addition. It lives entirely under `server/` and `docs/` and
> does not modify upstream `qwen_tts/` code. See `FORK_CHANGES.md`.

---

## 1. Install

### **Windows (Recommended)**

Requires Python 3.10+ and CUDA 12.8+. We recommend using `uv` for fast, reliable setup.

```powershell
# 1. Clone/checkout the fork
git clone https://github.com/tanakaSoft/Qwen3-TTS-fork260609.git
cd Qwen3-TTS-fork260609
git checkout claude/qwen3-tts-finetuning-6lixq8

# 2. Install uv (if not already installed)
irm https://astral.sh/uv/install.ps1 | iex

# 3. Create and activate virtual environment
uv sync

# Activate the venv
.venv\Scripts\activate

# 4. Install PyTorch with CUDA 12.8 support
pip install torch --index-url https://download.pytorch.org/whl/cu128

# 5. Install API server dependencies
# (No Flash Attention 2 needed; eager attention is the standard implementation)
pip install -r server\requirements-server.txt
```

### **WSL2 (Alternative)**

Similar to Windows, but use bash and Linux paths:

```bash
git clone https://github.com/tanakaSoft/Qwen3-TTS-fork260609.git
cd Qwen3-TTS-fork260609
git checkout claude/qwen3-tts-finetuning-6lixq8

uv sync
source .venv/bin/activate

pip install torch --index-url https://download.pytorch.org/whl/cu128

# No Flash Attention 2 needed; eager attention is the standard implementation
pip install -r server/requirements-server.txt
```

---

## 2. Start the Server

### **Windows (PowerShell)**

```powershell
# Activate venv if not already active
.venv\Scripts\activate

# Default: load all models (requires ~10 GB VRAM)
python server\tts_server_async.py

# OR with custom configuration
$env:QWEN_TTS_HOST = "0.0.0.0"
$env:QWEN_TTS_PORT = "8001"
$env:QWEN_TTS_LOAD = "voice_design,voice_clone,custom"
$env:QWEN_TTS_CUSTOM = "C:\path\to\finetuned\checkpoint"
python server\tts_server_async.py
```

### **WSL2 (Bash)**

```bash
source .venv/bin/activate

python server/tts_server_async.py
```

Then open the interactive API docs: **<http://localhost:8001/docs>**

---

## 3. Configuration

Environment variables control server behavior:

| Variable | Default | Example |
|---|---|---|
| `QWEN_TTS_HOST` | `0.0.0.0` | `localhost` (Windows only) or `0.0.0.0` (accessible from other machines) |
| `QWEN_TTS_PORT` | `8001` | `8080` |
| `QWEN_TTS_DEVICE` | `cuda:0` | `cuda:1` (if multiple GPUs) or `cpu` |
| `QWEN_TTS_LOAD` | `voice_design,voice_clone,custom` | `voice_clone` (load only one to save memory) |
| `QWEN_TTS_ATTN` | `eager` | `eager` (standard PyTorch attention, recommended) |
| `QWEN_TTS_CUSTOM` | _(empty)_ | `C:\Users\YourName\outputs\my_model\checkpoint-epoch-9` |

**Example: load only voice_clone on a smaller GPU**

```powershell
# Windows PowerShell
$env:QWEN_TTS_LOAD = "voice_clone"
$env:QWEN_TTS_ATTN = "eager"
python server\tts_server_async.py
```

---

## 4. Model Cache Location

HuggingFace models are downloaded to:

| Platform | Path |
|---|---|
| **Windows** | `C:\Users\<username>\.cache\huggingface` |
| **WSL2** | `~/.cache/huggingface` |

**Override cache location:**

```powershell
# Windows PowerShell
$env:HF_HOME = "D:\models\huggingface"
python server\tts_server_async.py
```

(Useful if your default drive is full)

---

## 5. Endpoints

| Method | Path | Description |
|---|---|---|
| GET  | `/health` | Server + model status |
| GET  | `/supported_speakers` | Speaker list (for CustomVoice) |
| GET  | `/supported_languages` | Language list |
| POST | `/generate_custom_voice` | CustomVoice (fine-tuned model) generation |
| POST | `/batch_generate_custom_voice` | CustomVoice, multiple texts in one call |
| POST | `/generate_voice_design` | VoiceDesign from natural-language instruct |
| POST | `/generate_voice_clone` | VoiceClone from uploaded reference clip |
| POST | `/finetune_async` | Start a background fine-tuning job |
| GET  | `/finetune_status/{job_id}` | Poll a fine-tuning job |
| GET  | `/finetune_jobs` | List all fine-tuning jobs |

Audio responses return 16-bit PCM as base64-encoded `audio_base64` plus `sample_rate`.
The client library decodes this automatically.

---

## 6. Client Usage

`server/tts_client_async.py` is a dependency-light HTTP client (no torch needed).
Works from **Windows**, **WSL2**, or **any machine on the network**.

```python
from server.tts_client_async import QwenTTSAsyncClient

# Connect to the API server (on the same machine or network)
tts = QwenTTSAsyncClient("http://localhost:8001")

# VoiceDesign: create a custom voice from natural-language description
audio, sr = tts.generate_voice_design(
    text="こんにちは、今日は良い天気ですね。",
    instruct="落ち着いた大人の女性、ゆっくり丁寧に話す",
    language="Japanese",
)
tts.save_speech(audio, sr, "design.wav")

# VoiceClone: clone a voice from a reference clip
audio, sr = tts.generate_voice_clone(
    text="これはクローンした声です。",
    ref_audio_path="reference.wav",
    ref_text="参考音声の文字起こしです。",
    language="Japanese",
)
tts.save_speech(audio, sr, "clone.wav")

# Batch: generate multiple texts at once (CustomVoice)
texts = ["テキスト1", "テキスト2", "テキスト3"]
audios, sr = tts.batch_generate_custom_voice(
    texts=texts,
    speaker="speaker_custom",
    instruct="元気よく",
)
for i, audio in enumerate(audios):
    tts.save_speech(audio, sr, f"batch_{i}.wav")
```

### Fine-tuning Workflow

```python
# 1. Start fine-tuning with raw training data
job_id = tts.start_finetune(
    train_jsonl="C:\\Users\\YourName\\train_raw.jsonl",  # Windows path
    output_model_name="my_voice",
    num_epochs=10,
    speaker_name="my_speaker",
)
print(f"Job ID: {job_id}")

# 2. Wait for completion (prints progress)
status = tts.wait_finetune_completion(job_id, check_interval=10)
print(f"✅ Fine-tuning done: {status['model_path']}")

# 3. The fine-tuned model is now the active CustomVoice model
audio, sr = tts.generate_custom_voice(
    text="ファインチューニングした声です。",
    speaker="my_speaker",
    instruct="元気よく",
)
tts.save_speech(audio, sr, "finetuned.wav")
```

**Data format:** `train_jsonl` is a **raw** JSONL file with columns
`audio` (WAV path), `text` (transcript), `ref_audio` (reference speaker WAV).
The server runs `prepare_data.py` automatically. See `finetuning/README.md`.

---

## 7. Troubleshooting

### CUDA Out of Memory (OOM)

**Symptom:** `RuntimeError: CUDA out of memory` during inference

**Causes:**
- Multiple models loaded when RTX 5090 has only 32 GB
- Eager attention with all models can use 12-14 GB VRAM

**Solutions:**
1. First test: load only one model to confirm setup works:
   ```powershell
   $env:QWEN_TTS_LOAD = "voice_clone"
   python server\tts_server_async.py
   ```
2. Once working, gradually increase loaded models as needed
3. Check GPU memory with `nvidia-smi`

### Server not reachable from Windows app

**Symptom:** `ConnectionError: Cannot reach TTS server at http://localhost:8001`

**Check:**
1. Is the server running? (Should print "Uvicorn running on..." )
2. Is the port correct? (default `8001`)
3. If on different machine, use WSL2 IP or Windows hostname instead of `localhost`

---

## 8. Windows vs WSL2 Comparison

Both use eager attention (standard PyTorch, officially supported).

| Factor | Windows | WSL2 |
|---|---|---|
| **Inference speed** | ✅ 100% (native GPU) | ⚠️ 90-95% (WSL2 overhead) |
| **Memory usage** | ✅ 12-14 GB (all models) | ✅ 12-14 GB (all models) |
| **Setup complexity** | ⭐⭐ Easy | ⭐⭐⭐ Medium |
| **Fine-tuning** | ✅ Batch 32 | ✅ Batch 24-32 |
| **Recommended** | ✅ **Yes** | ✅ Alternative |

**Recommendation:** Run on **Windows** for simplicity and peak performance, or **WSL2** if your development environment is already Linux-based.

---

## 9. Notes & Limitations

- **Single GPU, serialized requests.** The server processes one request at a time.
  Use `/batch_generate_custom_voice` for multiple texts rather than parallel requests.
- **Fine-tuning runs in-process.** Only one at a time (GPU-intensive).
  Job registry is in-memory; resets on server restart.
- **Network access.** With `QWEN_TTS_HOST=0.0.0.0`, the server is accessible
  from `localhost` (Windows/WSL2 same machine) or `<machine-ip>:8001` (other machines).
- **Production deployment.** Use a process manager (e.g., NSSM on Windows, systemd on Linux)
  and persistent job storage.

---

## References

- **Flash Attention 2 Windows wheels:** [marcorez8/flash-attn-windows-blackwell](https://huggingface.co/marcorez8/flash-attn-windows-blackwell)
- **Fine-tuning data format:** `finetuning/README.md`
- **API server source:** `server/tts_server_async.py`
- **Client source:** `server/tts_client_async.py`
