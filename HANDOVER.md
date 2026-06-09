# Qwen3-TTS Windows セットアップ引き継ぎ事項

**作成日**: 2026-06-09
**セッション**: Claude Code Session 012w8GPthDadnbsr86rDp8za（クラウド環境）
**次のセッション**: ローカル Windows（ユーザー環境）

---

## 🎯 現在の状況

### ブランチ・コミット情報

```
リポジトリ: https://github.com/tanakaSoft/Qwen3-TTS-fork260609
ブランチ: claude/qwen3-tts-finetuning-6lixq8
最新コミット: 0d1af8f (2026-06-09)
  refactor: redesign for Windows-native execution with FA2 optimization
```

### 実装済み機能

| 項目 | 状態 | ファイル |
|---|---|---|
| **API サーバー** | ✅ 完成 | `server/tts_server_async.py` |
| **HTTP クライアント** | ✅ 完成 | `server/tts_client_async.py` |
| **Windows セットアップガイド** | ✅ 完成 | `docs/windows_setup.md` |
| **API ドキュメント** | ✅ 改訂完了 | `docs/api_server.md` |
| **変更履歴** | ✅ 記録 | `FORK_CHANGES.md` |

---

## 🚀 次のステップ（ローカル環境で実施）

### Step 1: リポジトリクローン（未実施なら）

```powershell
cd C:\Users\bshon\Projects  # 任意のディレクトリ
git clone https://github.com/tanakaSoft/Qwen3-TTS-fork260609.git
cd Qwen3-TTS-fork260609
git checkout claude/qwen3-tts-finetuning-6lixq8
```

### Step 2-10: Windows セットアップ

詳細は以下のドキュメントを参照：

**`docs/windows_setup.md`** を Step 1 から Step 11 まで順番に実行

簡略版：
```powershell
# Step 1: uv インストール
irm https://astral.sh/uv/install.ps1 | iex

# Step 3: 仮想環境構築
uv sync
.venv\Scripts\activate

# Step 4: PyTorch CUDA 12.8
pip install torch --index-url https://download.pytorch.org/whl/cu128

# Step 5: Flash Attention 2（Windows ホイール）
pip install https://huggingface.co/marcorez8/flash-attn-windows-blackwell/resolve/main/flash_attn-2.8.3-cp311-cp311-win_amd64.whl

# Step 6: API サーバー依存
pip install -r server\requirements-server.txt

# Step 8: サーバー起動
python server\tts_server_async.py
```

---

## ⚡ 重要な確認事項

### 1. GPU ドライバ確認

```powershell
nvidia-smi
# 出力: NVIDIA-SMI 560.xx  Driver Version: 560.xx  CUDA Version: 12.8
```

**CUDA Version が 12.8 以上であることを確認**

### 2. HuggingFace キャッシュ（既存）

キャッシュパス: `C:\Users\bshon\.cache\huggingface\hub\`

✅ **既にモデルがダウンロード済みなので、再ダウンロード不要**

デフォルトで自動利用されます。確認：

```powershell
python -c "from huggingface_hub import HfFolder; print(HfFolder.home())"
# 出力: C:\Users\bshon\.cache\huggingface
```

### 3. Python バージョン確認

```powershell
python --version
# Python 3.11.x が必要（Flash Attention ホイール）
# 3.12.x の場合は White2Hand ホイールを使用
```

---

## ⚠️ トラブルシューティング

### Flash Attention インストール失敗

**原因**: Python バージョン不一致（ホイールが cp311 = Python 3.11 用）

**解決**:
1. Python バージョン確認: `python --version`
2. Python 3.12 なら White2Hand ホイールを使用:
   ```powershell
   pip install https://huggingface.co/White2Hand/flash-attention-v2.8.3-blackwell-windows/resolve/main/flash_attn-2.8.3-cp312-cp312-win_amd64.whl
   ```
3. FA2 スキップして起動:
   ```powershell
   $env:QWEN_TTS_ATTN = "eager"
   python server\tts_server_async.py
   ```

### CUDA Out of Memory

```powershell
# ロードするモデルを減らす
$env:QWEN_TTS_LOAD = "voice_clone"
python server\tts_server_async.py
```

### サーバーに接続できない

1. サーバーが起動しているか確認
2. ポート 8001 が空いているか確認
3. ブラウザで確認: http://localhost:8001/docs

詳細は `docs/windows_setup.md` の「トラブルシューティング」を参照

---

## 📚 ドキュメント位置

| ドキュメント | パス | 用途 |
|---|---|---|
| **Windows セットアップ** | `docs/windows_setup.md` | ステップバイステップガイド |
| **API リファレンス** | `docs/api_server.md` | エンドポイント・設定・使い方 |
| **変更履歴** | `FORK_CHANGES.md` | フォークの改変内容 |
| **ファインチューニング** | `finetuning/README.md` | 訓練データ形式・手順 |

---

## 🧪 セットアップ完了後の確認

### 1. ブラウザで API ドキュメント確認

```
http://localhost:8001/docs
```

Swagger UI が表示されれば OK

### 2. ヘルスチェック

```powershell
Invoke-RestMethod -Uri "http://localhost:8001/health"
```

出力例:
```
status               : ok
device               : cuda:0
models               : @{custom=False; voice_design=True; voice_clone=True}
active_finetune_jobs : 0
```

### 3. クライアント テスト

```powershell
python -c "
from server.tts_client_async import QwenTTSAsyncClient
tts = QwenTTSAsyncClient('http://localhost:8001')
audio, sr = tts.generate_voice_design(
    text='これはテストです。',
    instruct='明るく元気な女性の声'
)
tts.save_speech(audio, sr, 'test.wav')
print('✅ 完了: test.wav')
"
```

---

## 🔄 設計方針の背景

### なぜ Windows か？

| 項目 | Windows | WSL2 |
|---|---|---|
| **Flash Attention 2** | ✅ ホイール充実 | ⚠️ 少ない |
| **メモリ効率** | 3-4 GB（FA2） | 10-12 GB（eager） |
| **推論速度** | 100% | 70-80% |
| **セットアップ** | ⭐⭐ | ⭐⭐⭐ |

**Windows で FA2 を使う = RTX 5090 の性能を最大活用**

### なぜ非同期ファインチューニング？

- GPU がブロックされない
- 複数ジョブを管理可能
- 進捗をポーリングで確認

---

## 📞 問題が発生した場合

1. **エラーメッセージを確認**
   ```powershell
   # サーバーのログを見る（起動中のターミナル）
   # または
   python server\tts_server_async.py 2>&1 | Tee-Object -FilePath error.log
   ```

2. **docs/windows_setup.md のトラブルシューティング参照**

3. **GitHub Issues を検索**
   https://github.com/QwenLM/Qwen3-TTS/issues

4. **Flash Attention ホイール互換性確認**
   - Python バージョン
   - CUDA バージョン
   - ホイールの whl ファイル名

---

## 💡 Tips

### サーバーをバックグラウンドで実行

```powershell
# 新規 PowerShell ウィンドウで実行して、元のウィンドウで作業継続
Start-Process powershell -ArgumentList "cd $PWD; .venv\Scripts\activate; python server\tts_server_async.py"
```

### 複数テキストをバッチ処理

```python
tts = QwenTTSAsyncClient("http://localhost:8001")
texts = ["テキスト1", "テキスト2", "テキスト3"]
audios, sr = tts.batch_generate_custom_voice(texts=texts)
for i, audio in enumerate(audios):
    tts.save_speech(audio, sr, f"batch_{i}.wav")
```

### 動画生成ソフト統合

`server/tts_client_async.py` を import して使用。
例: `from server.tts_client_async import QwenTTSAsyncClient`

---

## ✅ セットアップ完了チェックリスト

- [ ] Git クローン・ブランチチェックアウト完了
- [ ] CUDA 12.8 確認（`nvidia-smi`）
- [ ] uv インストール完了
- [ ] `uv sync` 完了
- [ ] PyTorch インストール完了
- [ ] Flash Attention 2 インストール完了（または eager で回避）
- [ ] API サーバー依存インストール完了
- [ ] サーバー起動確認（`http://localhost:8001/docs`）
- [ ] ヘルスチェック OK（`/health` エンドポイント）
- [ ] クライアント テスト完了（音声生成 OK）

---

**ローカル Windows 環境での作業、よろしくお願いします！**

何か質問や問題が発生したら、新しいセッションでサポートします。
