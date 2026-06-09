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
# リポジトリルートで、Python 3.12 の仮想環境を作成
uv venv --python 3.12

# 仮想環境をアクティベート
.venv\Scripts\activate

# プロジェクトと依存をインストール
uv pip install -e .

# プロンプトが (.venv) で始まれば OK
# 例: (.venv) PS C:\Users\YourName\Projects\Qwen3-TTS-fork260609>
```

> **なぜ `uv sync` を使わないのか（実機検証で確認）**
> upstream の `pyproject.toml` は `requires-python = ">=3.9"` だが、依存の
> `accelerate==1.12.0` は Python>=3.10 を要求するため、`uv sync` のユニバーサル
> 依存解決が **失敗** する（`No solution found ... python_full_version == '3.9.*'`）。
> `pyproject.toml` は upstream 追従のため変更せず、現行インタプリタ向けに解決する
> `uv pip install -e .` を使う（3.9 split を回避）。

---

## Step 4: PyTorch インストール（CUDA 12.8 対応）

Step 3 の `uv pip install -e .` では PyPI の **CPU 版** torch が入る。RTX 5090
（Blackwell / sm_120）で動かすには CUDA 12.8 版へ **入れ替え**が必要。バージョン
番号が同じだと `uv pip install` はスキップするため、必ず `--reinstall` を付ける。

```powershell
# CUDA 12.8 対応の PyTorch / torchaudio へ入れ替え（--reinstall が必須）
uv pip install --reinstall torch torchaudio --index-url https://download.pytorch.org/whl/cu128

# 確認（cuda_available が True、capability が (12, 0) であること）
python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA:', torch.version.cuda); print('cuda_available:', torch.cuda.is_available())"

# 出力例（実機 RTX 5090 で確認）:
# PyTorch: 2.11.0+cu128
# CUDA: 12.8
# cuda_available: True
```

**重要**: 末尾が `+cu128` で `cuda_available: True` になっていること。`+cpu` の
ままだと GPU を使えない（Step 3 直後はこの状態なので必ず入れ替える）。

---

## Step 5: Attention 実装（eager を使用）

PyTorch の **eager attention**（標準 attention）を使用します。

**理由:**
- RTX 5090 の 32GB VRAM で十分動作可能（約 10-12GB 使用）
- eager attention は **PyTorch 公式・完全サポート**（セキュリティリスク 0）
- Blackwell（sm_120）での Flash Attention 2 は非公式ホイール頼みで保守リスクが高い
- 推奨しない：非公式ホイール（marcorez8 等）は更新・互換性保証がなく、メンテナンスリスク大

eager は標準実装で何もインストール不要です。次のステップに進んでください。

**参考: 性能目安**
- eager（標準）: 100% ベースライン、メモリ効率は標準レベル
- RTX 5090 32GB: eager で全モデル（voice_design, voice_clone, custom）をロード可能

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

# デフォルト: eager attention を使用（変更不要）
# $env:QWEN_TTS_ATTN = "eager"  # すでにデフォルト
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

### CUDA Out of Memory (OOM)

```powershell
# エラー: "CUDA out of memory"

# 解決法:
# 1. ロードするモデルを減らす（最初のテストでは voice_clone のみ推奨）
$env:QWEN_TTS_LOAD = "voice_clone"
python server\tts_server_async.py

# 2. GPU メモリ使用量を確認
# PowerShell で以下を実行
nvidia-smi
# RTX 5090 で全モデル + eager attention なら約 12-14GB で収まるはず
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

## Web UI を使う（推奨）

API サーバーに加えて、ブラウザで使える **Gradio Web UI** があります。
リポジトリ直下の **`Qwen3-TTS-Studio.bat`** をダブルクリックすれば、
API サーバーと Web UI が自動で起動し、ブラウザが開きます。

詳細は `docs/webui_setup.md` を参照。

```powershell
# 手動で UI を起動する場合（API サーバー起動後）
python ui\launch_ui.py
```

---

## 次のステップ

- Web UI ガイド: `docs/webui_setup.md`
- API ドキュメント: `docs/api_server.md`
- API サーバーコード: `server/tts_server_async.py`
- クライアントコード: `server/tts_client_async.py`
- ファインチューニング: `finetuning/README.md`

---

## サポート

問題が発生した場合：

1. `docs/api_server.md` / `docs/webui_setup.md` の「Troubleshooting」を確認
2. GitHub Issues を検索
3. GPU メモリ不足時は `QWEN_TTS_LOAD` でロードするモデルを絞る
