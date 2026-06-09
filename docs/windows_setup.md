# Windows セットアップガイド（RTX 5090 推奨）

このガイドは、Windows 上で Qwen3-TTS API サーバーをセットアップするための **ステップバイステップ手順** です。
RTX 5090 + CUDA 12.8 を想定していますが、他の NVIDIA GPU でも動作します。

---

## 前提条件

- **OS**: Windows 10/11（64bit）
- **GPU**: NVIDIA RTX 5090（または他の NVIDIA GPU）
- **CUDA**: 12.8 以上（リポジトリから自動DL）
- **ドライバ**: NVIDIA GPU ドライバ（最新）
- **Python**: 3.10 以上（uv で管理）

### GPU ドライバ確認

```powershell
# PowerShell でドライババージョン確認
nvidia-smi

# 出力例：
# NVIDIA-SMI 560.68       Driver Version: 560.68       CUDA Version: 12.8
```

CUDA バージョンが **12.8 以上** であることを確認してください。

---

## Step 1: 基本ツール インストール

### 1.1 Git のインストール

[Git for Windows](https://git-scm.com/download/win) から最新版をダウンロード・インストール。

```powershell
git --version
# git version 2.x.x が表示されれば OK
```

### 1.2 uv のインストール

uv は Python パッケージ管理ツール（Rust 製、高速）。PowerShell で以下を実行：

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

ターミナルを再起動し、確認：

```powershell
uv --version
# uv 0.x.x が表示されれば OK
```

---

## Step 2: リポジトリ クローン

任意のフォルダで以下を実行：

```powershell
# 例: C:\Users\YourName\Projects に配置
cd C:\Users\YourName\Projects

# リポジトリをクローン
git clone https://github.com/tanakaSoft/Qwen3-TTS-fork260609.git
cd Qwen3-TTS-fork260609

# 開発ブランチをチェックアウト
git checkout claude/qwen3-tts-finetuning-6lixq8
```

---

## Step 3: Python 仮想環境 セットアップ

```powershell
# リポジトリルートで、uv で環境構築
uv sync

# 仮想環境をアクティベート
.venv\Scripts\activate

# プロンプトが (.venv) で始まれば OK
# 例: (.venv) PS C:\Users\YourName\Projects\Qwen3-TTS-fork260609>
```

---

## Step 4: PyTorch インストール（CUDA 12.8 対応）

```powershell
# CUDA 12.8 対応の PyTorch をインストール
pip install torch --index-url https://download.pytorch.org/whl/cu128

# 確認
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.version.cuda}')"

# 出力例:
# PyTorch: 2.6.0
# CUDA: 12.8
```

**重要**: CUDA バージョンが **12.8 以上** であることを確認。

---

## Step 5: Flash Attention 2 インストール（重要！）

RTX 5090 では Flash Attention 2 が **ほぼ必須**（メモリ効率 2-3 倍）。

### Option A: 推奨（marcorez8 ホイール）

```powershell
# marcorez8 の公式ホイール（RTX 5090 テスト済み）
pip install https://huggingface.co/marcorez8/flash-attn-windows-blackwell/resolve/main/flash_attn-2.8.3-cp311-cp311-win_amd64.whl

# 確認
python -c "import flash_attn; print('Flash Attention 2: OK')"
```

**注意**: Python バージョンが 3.11 である必要があります。
他のバージョンの場合は、URL 内の `cp311` を適切なバージョンに変更するか、Option B を試してください。

### Option B: 代替（White2Hand ホイール）

```powershell
# Python 3.12 の場合
pip install https://huggingface.co/White2Hand/flash-attention-v2.8.3-blackwell-windows/resolve/main/flash_attn-2.8.3-cp312-cp312-win_amd64.whl
```

### Option C: FA2 スキップ（フォールバック）

FA2 インストール失敗時でも動作します（標準 PyTorch attention を使用）：

```powershell
# スキップしても OK。あとで環境変数で制御
echo "[warn] Flash Attention 2 installation skipped. Using standard attention."
```

---

## Step 6: API サーバー依存 インストール

```powershell
pip install -r server\requirements-server.txt

# 確認
python -c "import fastapi; import uvicorn; print('FastAPI: OK')"
```

---

## Step 7: HuggingFace キャッシュ設定（オプション）

デフォルトでは、モデルは以下に保存されます：

```
C:\Users\YourName\.cache\huggingface
```

**大きなドライブに変更したい場合**:

```powershell
# PowerShell で環境変数設定
$env:HF_HOME = "D:\models\huggingface"

# または .bashrc 相当に追加（永続化）
# [Environment]::SetEnvironmentVariable("HF_HOME", "D:\models\huggingface", "User")
```

---

## Step 8: サーバー起動

```powershell
# 仮想環境が active であることを確認
# プロンプトが (.venv) で始まっていないら：
.venv\Scripts\activate

# サーバー起動
python server\tts_server_async.py

# 出力例:
# INFO:     Uvicorn running on http://0.0.0.0:8001
# 🚀 Qwen3-TTS モデルをロード中...
#   1. VoiceDesign: Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
#   2. VoiceClone (Base): Qwen/Qwen3-TTS-12Hz-1.7B-Base
#   3. CustomVoice (fine-tuned): (not loaded)
# ✅ Startup complete.
```

### カスタム設定で起動

```powershell
# 例: VoiceClone のみロード（メモリ節約）
$env:QWEN_TTS_LOAD = "voice_clone"
python server\tts_server_async.py

# 例: 標準 attention を使用（FA2 がない場合）
$env:QWEN_TTS_ATTN = "eager"
python server\tts_server_async.py
```

---

## Step 9: サーバー確認

### 1. ブラウザで API ドキュメント確認

<http://localhost:8001/docs> をブラウザで開く

- **Swagger UI** が表示されれば成功
- エンドポイント一覧を確認可能

### 2. ヘルスチェック

```powershell
# 別ターミナルで実行（サーバーは起動したまま）
Invoke-RestMethod -Uri "http://localhost:8001/health"

# 出力例:
# status               : ok
# device               : cuda:0
# models               : @{custom=False; voice_design=True; voice_clone=True}
# active_finetune_jobs : 0
```

---

## Step 10: クライアント テスト

別のターミナルで、クライアント Python スクリプトを実行：

```powershell
# 別ターミナル（サーバーは起動したまま）
.venv\Scripts\activate

python -c "
from server.tts_client_async import QwenTTSAsyncClient
tts = QwenTTSAsyncClient('http://localhost:8001')
audio, sr = tts.generate_voice_design(
    text='これはテストです。',
    instruct='明るく元気な女性の声'
)
tts.save_speech(audio, sr, 'test_output.wav')
print('✅ 音声生成完了: test_output.wav')
"
```

**出力例**:
```
[OK] Connected to TTS server: http://localhost:8001
✅ 音声生成完了: test_output.wav
```

---

## Step 11: 動画生成ソフトとの統合（例）

```python
# video_generator.py
from server.tts_client_async import QwenTTSAsyncClient
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioFileClip

tts = QwenTTSAsyncClient("http://localhost:8001")

# VoiceDesign で音声生成
audio, sr = tts.generate_voice_design(
    text="こんにちは、今日のニュースです。",
    instruct="プロのナレーター、落ち着いた声"
)
tts.save_speech(audio, sr, "narration.wav")

# 動画に挿入（moviepy 等を使用）
video = VideoFileClip("template.mp4")
audio_clip = AudioFileClip("narration.wav")
final = video.set_audio(audio_clip)
final.write_videofile("output.mp4")
```

---

## トラブルシューティング

### Flash Attention インストール失敗

```powershell
# エラー例: "No module named 'flash_attn'"
# または "wheel not compatible"

# 解決法:
# 1. Python バージョン確認
python --version
# Python 3.11.x が表示されるか？
# 3.12.x の場合は White2Hand ホイールを試す

# 2. ホイール URL が正しいか確認
# https://huggingface.co/ から直接ダウンロード

# 3. FA2 なしで起動
$env:QWEN_TTS_ATTN = "eager"
python server\tts_server_async.py
```

### CUDA Out of Memory (OOM)

```powershell
# エラー: "CUDA out of memory"

# 解決法:
# 1. ロードするモデルを減らす
$env:QWEN_TTS_LOAD = "voice_clone"
python server\tts_server_async.py

# 2. Flash Attention を確認（インストール済みか）
python -c "import flash_attn; print('OK')"
# インストール済み → FA2 が有効になっているはず
```

### サーバーに接続できない

```powershell
# クライアント エラー: "Cannot reach TTS server"

# チェック:
# 1. サーバー起動しているか？
# PS プロンプトで "Uvicorn running on..." が表示されているか

# 2. ポート番号が正しいか
# デフォルト: 8001

# 3. ファイアウォール
# Windows Defender ファイアウォールが Python をブロックしていないか確認
```

---

## ファインチューニング セットアップ

ファインチューニングを行う場合の追加手順：

### 訓練データ準備

```
train_raw.jsonl 形式:
{"audio": "path/to/audio.wav", "text": "トランスクリプト", "ref_audio": "path/to/ref.wav"}
{"audio": "path/to/audio2.wav", "text": "トランスクリプト2", "ref_audio": "path/to/ref.wav"}
```

詳細は `finetuning/README.md` を参照。

### クライアント スクリプト

```python
from server.tts_client_async import QwenTTSAsyncClient

tts = QwenTTSAsyncClient("http://localhost:8001")

# ファインチューニング開始
job_id = tts.start_finetune(
    train_jsonl="C:\\Users\\YourName\\train_raw.jsonl",
    output_model_name="my_voice",
    num_epochs=10,
    speaker_name="my_speaker",
)
print(f"Job ID: {job_id}")

# 完了を待機（進捗表示）
tts.wait_finetune_completion(job_id, check_interval=10)

# ファインチューニング済みモデルで生成
audio, sr = tts.generate_custom_voice(
    text="ファインチューニングされた声です。",
    speaker="my_speaker",
    instruct="元気よく",
)
tts.save_speech(audio, sr, "finetuned.wav")
```

---

## 次のステップ

- API ドキュメント: `docs/api_server.md`
- API サーバーコード: `server/tts_server_async.py`
- クライアントコード: `server/tts_client_async.py`
- ファインチューニング: `finetuning/README.md`

---

## サポート

問題が発生した場合：

1. `docs/api_server.md` の「Troubleshooting」を確認
2. GitHub Issues を検索
3. Flash Attention ホイールの互換性を確認
