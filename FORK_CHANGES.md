# Fork Changes — Qwen3-TTS-fork260609

このファイルは、本フォークが **upstream（QwenLM/Qwen3-TTS）から加えた変更点** を記録するものです。
README.md は upstream のまま保持し、フォーク独自の変更はすべてここに集約します。

---

## 基本方針

- **README.md は触らない**（upstream 更新時のコンフリクトを避けるため）
- 追加コードは **`server/` など独立ディレクトリに隔離** し、`qwen_tts/` 本体への改変は最小限にする
- 変更を加えるたびに、本ファイルの「変更履歴」へ追記する

---

## 安全地点（復元ポイント）

フォーク直後の状態は以下に保存されています。いつでも復元可能です。

| 保護手段 | コミット | 場所 |
|---|---|---|
| `origin/main` ブランチ | `022e286` | リモート（GitHub） |
| ローカル `main` ブランチ | `022e286` | ローカル |
| `fork-original` タグ | `022e286` | ローカル（リモート push は環境制約で未実施） |

### 復元コマンド

```bash
# ローカルタグから復元
git reset --hard fork-original

# リモートの main から復元（環境を作り直しても有効）
git fetch origin main
git checkout origin/main
```

---

## 開発ブランチ

- 改変はすべて `claude/qwen3-tts-finetuning-6lixq8` ブランチで行う
- `main` ブランチは upstream の状態を保持し、原則として直接コミットしない

---

## 追加予定の構成

```
Qwen3-TTS-fork260609/
├── README.md              # upstream のまま（変更しない）
├── FORK_CHANGES.md        # このファイル（変更記録）
├── docs/
│   └── api_server.md      # API サーバーの使い方（予定）
├── server/                # 追加コード（元コードと分離）
│   ├── tts_server_async.py    # 非同期 TTS + ファインチューニング API（予定）
│   ├── tts_client_async.py    # クライアントライブラリ（予定）
│   └── requirements-server.txt # 追加依存（fastapi, uvicorn 等）（予定）
└── qwen_tts/              # upstream パッケージ（改変は最小限）
```

### 追加予定の機能

- **非同期 API サーバー**: WSL2 上で常駐し、Windows / WSL2 の複数アプリから HTTP 経由で利用
- **対応する生成方式**:
  - CustomVoice（ファインチューニング済みモデル）
  - Voice Design（自然言語での音声デザイン）
  - Voice Clone（参考音声からのクローン）
- **ファインチューニング API**: バックグラウンドジョブとして実行し、完了後そのまま音声生成に利用
- **バッチ処理**: 複数テキストの一括音声生成

---

## 変更履歴

### [Unreleased]

- `FORK_CHANGES.md` を新規作成。フォークの変更管理方針と復元ポイントを記録。
