# Web UI セットアップ・利用ガイド

Qwen3-TTS Studio の **Gradio Web UI** の使い方です。
UI は **API サーバーの薄いクライアント**で、モデルは一切ロードしません
（モデルは API サーバーに1回だけ常駐）。そのため、同じ PC の他のアプリも
同じ API を叩いて TTS を利用できます。

```
  ┌─ API サーバー (:8001) ── モデルを1回だけGPUにロード
  │     ├ /generate_voice_design /generate_voice_clone …
  │     ├ /auto_transcribe（Whisper 自動文字起こし）
  │     └ /gpu_stats（GPU 状態）
  │        ↑ HTTP            ↑ HTTP
  ├─ Web UI (:7860)       ├─ あなたの動画生成ソフト等
  │  =薄いクライアント        =同じ API を利用
```

---

## 1. ワンクリック起動（推奨・Windows）

リポジトリ直下の **`Qwen3-TTS-Studio.bat`** をダブルクリック。

1. API サーバーが別ウィンドウで起動（モデルロード）
2. `/health` が OK になるまで自動待機
3. Web UI が起動し、ブラウザが自動で開く

> 前提: `uv sync` で `.venv` を作成済みであること（`docs/windows_setup.md` 参照）。

---

## 2. 手動起動（2ターミナル）

### ターミナル1: API サーバー

```powershell
.venv\Scripts\activate
python server\tts_server_async.py
# "Uvicorn running on http://127.0.0.1:8001" が出ればOK
```

### ターミナル2: Web UI

```powershell
.venv\Scripts\activate
python ui\launch_ui.py
# 空きポートを自動選択し、ブラウザが自動で開く
```

---

## 3. 5つのタブ

| タブ | 機能 |
|---|---|
| **カスタムボイス** | モデルを選んでロードし生成。ファインチューニング済み or 公式プリセット |
| **ボイスデザイン** | 「落ち着いた大人の女性」等の説明文から音声を生成 |
| **ボイスクローン** | 参照音声から声を複製。**Whisper で参照テキストを自動入力** |
| **ファインチューニング** | 学習ジョブを開始し、進捗を確認。完了後そのままカスタムボイスで使用 |
| **設定** | GPU/VRAM 使用状況の定期更新表示、GPU キャッシュ解放 |

### カスタムボイスタブのモデル選択

カスタムボイスは内部で1つのモデル枠を使い、以下のどちらかをロードできます：

- **公式 CustomVoice モデル**（`Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`）
  プリセット話者を持つ既製モデル。初回ロード時に HuggingFace から自動DL。
- **ファインチューニング済みモデル**（`outputs/<名前>/checkpoint-epoch-N/`）
  自分で学習した声。

使い方：
1. 「カスタムモデル」ドロップダウンから選択（「一覧を更新」で `outputs/` を再スキャン）
2. 「ロード」→ モデルが読み込まれ、話者ドロップダウンがプリセット話者で更新される
3. テキスト・話者・言語を指定して「生成」

> 同時にロードできるカスタムモデルは1つ。新しくロードすると前のものはメモリから解放されます
> （ディスクの `outputs/` には残ります）。サーバー再起動後は再度ロードが必要
> （または起動時に `QWEN_TTS_CUSTOM` で指定）。

### ファインチューニングタブ

1. 「学習データ」にサーバー上の JSONL パスを入力
   （形式: `{"audio": "...", "text": "...", "ref_audio": "..."}` — 詳細は `finetuning/README.md`）
2. 出力モデル名・話者名・エポック数・バッチサイズ・学習率を設定
3. 「ファインチューニング開始」→ ジョブIDが発行される
4. 進捗は5秒ごとに自動更新（手動更新も可）。完了するとカスタムボイスタブで利用可能

> ジョブはサーバー側で**同時に1件ずつ**実行されます（GPU 集約処理のため）。
> ジョブ登録はメモリ上で管理され、サーバー再起動でリセットされます。

### ボイスクローンの Whisper 自動文字起こし

1. 「参照音声」に音声ファイルをアップロード
2. 「Whisper モデル」を選択（tiny / base / small / medium / **large-v3**）
3. 「自動文字起こし」ボタン → 参照テキスト欄が自動で埋まる
4. 生成したいテキストを入力して「生成」

> Whisper は **transformers 実装**（既存の torch/transformers に同梱）を使用。
> faster-whisper や ffmpeg などの追加 native 依存は不要です。

---

## 4. 多言語 UI

画面右上の言語セレクタで 10 言語を切替（日本語/English/中文/한국어/Русский/
Español/Italiano/Deutsch/Français/Português）。各言語は専用ルート
（`/ja`, `/en`, …）として提供され、セレクタはルート間を移動します。

デフォルト言語は環境変数で変更可能:

```powershell
$env:QWEN_TTS_UI_LANG = "en"   # 既定は ja
python ui\launch_ui.py
```

---

## 5. 設定（環境変数）

| 変数 | 既定 | 説明 |
|---|---|---|
| `QWEN_TTS_API_URL` | `http://localhost:8001` | UI が叩く API サーバーの URL |
| `QWEN_TTS_UI_HOST` | `127.0.0.1` | UI のバインドホスト |
| `QWEN_TTS_UI_PORT` | `7860` | UI の開始ポート（空きを自動探索） |
| `QWEN_TTS_UI_LANG` | `ja` | UI のデフォルト言語 |
| `QWEN_TTS_GPU_REFRESH` | `5` | 設定タブの GPU 自動更新間隔（秒） |
| `QWEN_TTS_WHISPER` | `large-v3` | Whisper の既定モデル |

---

## 6. 他アプリから API を使う

Web UI と同じ API を、あなたの別アプリからも利用できます
（UI を起動していなくても API サーバーさえ動いていればOK）。

```python
from server.tts_client_async import QwenTTSAsyncClient

tts = QwenTTSAsyncClient("http://localhost:8001")

# 参照音声を Whisper で文字起こし → そのままクローン生成
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

## 7. トラブルシューティング

| 症状 | 対処 |
|---|---|
| UI に「API サーバーに接続できません」 | API サーバー（:8001）が起動・`/health` OK か確認 |
| カスタムボイスが 503 | ファインチューニング済みモデル未ロード。`QWEN_TTS_CUSTOM` 設定か `/finetune_async` 実行 |
| Whisper 初回が遅い | 初回のみモデルをDL/ロード。2回目以降はキャッシュ |
| ポートが使用中 | UI は空きポートを自動選択。API は `QWEN_TTS_PORT` で変更 |

---

## 次のステップ

- API 詳細: `docs/api_server.md`
- Windows 基本セットアップ: `docs/windows_setup.md`
- フォークの設計と変更履歴: `FORK_CHANGES.md`
