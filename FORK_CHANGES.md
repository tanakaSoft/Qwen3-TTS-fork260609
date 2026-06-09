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

## upstream（本家）追従戦略

本家 [QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) の更新を取り込めるよう、
`upstream` リモートを設定済み。

```bash
# 設定（一度だけ）
git remote add upstream https://github.com/QwenLM/Qwen3-TTS.git
```

### 追従の鉄則：`qwen_tts/` を絶対に触らない

本フォークの追加コードは **すべて `server/` `ui/` `docs/` に隔離** されており、
upstream パッケージ本体 `qwen_tts/` への変更は **ゼロ**。
この分離を守る限り、本家更新は **コンフリクトなしでマージ可能**。

| 確認項目 | 状態 |
|---|---|
| `qwen_tts/` への変更 | なし（`git diff fork-original HEAD` で新規ファイルのみ） |
| 本家 Gradio demo (`qwen_tts/cli/demo.py`) | upstream のまま保持（改変せず、`ui/` に独自実装） |

### 本家更新の取り込み手順

```bash
# 1. 本家の最新を取得
git fetch upstream

# 2. main を本家に追従（クリーンな fast-forward / merge）
git checkout main
git merge upstream/main
git push origin main

# 3. 開発ブランチに反映
git checkout claude/qwen3-tts-finetuning-6lixq8
git merge main
# server/ ui/ は独自コードなので衝突しない。qwen_tts/ は upstream と同期。
```

---

## 実装環境

### **推奨：Windows ネイティブ + RTX 5090 + Eager Attention**

このフォークは **Windows（Python + uv 仮想環境）での実行を前提** に設計されています。
**Eager attention（標準 PyTorch）を採用**し、セキュリティリスク 0、保守性最高。

| 環境 | Attention | メモリ | 推奨度 |
|---|---|---|---|
| **Windows + RTX 5090** | Eager | 12-14 GB | ⭐⭐⭐⭐⭐ **推奨** |
| **WSL2 + RTX 5090** | Eager | 12-14 GB | ⭐⭐⭐⭐ **代替案** |

**設計方針：**
- Eager attention は PyTorch 公式、100% サポート済み（セキュリティ 0）
- RTX 5090 32GB で eager は十分（全モデルロード可能、メモリ余裕あり）
- 非公式 Flash Attention 2 ホイール（marcorez8 等）は保守リスク大のため未採用
  - 更新保証なし、互換性ブレーク可能性、セキュリティ監査未実施
- Windows ネイティブなら API サーバーは直結で最速

### **WSL2 での実行（代替案）**

WSL2 での実行も可能です。Eager attention は両環境で同じ性能：
- メモリ消費：両環境同等（12-14 GB、余裕十分）
- 推論速度：Windows 100% に対し WSL2 90-95%（オーバーヘッド軽微）
- ファインチューニング：両環境で Batch 24-32 利用可能

詳細は `docs/api_server.md` の「Windows vs WSL2 Comparison」を参照

---

## 構成

```
Qwen3-TTS-fork260609/
├── README.md              # upstream のまま（変更しない）
├── FORK_CHANGES.md        # このファイル（変更記録）
├── docs/
│   └── api_server.md      # API サーバーの使い方
├── server/                # 追加コード（元コードと分離）
│   ├── tts_server_async.py     # 非同期 TTS + ファインチューニング API
│   ├── tts_client_async.py     # クライアントライブラリ
│   └── requirements-server.txt # 追加依存（fastapi, uvicorn 等）
└── qwen_tts/              # upstream パッケージ（改変は最小限）
```

### 追加した機能

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

#### Setup & Documentation

- `FORK_CHANGES.md` を新規作成。フォークの変更管理方針と復元ポイントを記録。
- Windows ネイティブ実行を主軸に設計。RTX 5090 32GB VRAM で eager attention を標準採用。

#### API Server Implementation

- `server/tts_server_async.py` を追加。CustomVoice / VoiceDesign / VoiceClone の
  生成と、非同期ファインチューニング（バックグラウンドジョブ）を提供する FastAPI サーバー。
  Windows/WSL2 cross-platform 対応（pathlib で path 処理）。
  Eager attention を使用（公式サポート、セキュリティリスク 0）。
- `server/tts_client_async.py` を追加。torch 不要の軽量 HTTP クライアント
  （Windows / WSL2 / 他マシンから利用可能）。
- `server/requirements-server.txt` を追加。API サーバー用の追加依存（fastapi 等）。

#### Documentation

- `docs/windows_setup.md` を新規作成。Windows PowerShell での ステップバイステップセットアップガイド（11 ステップ）。
  Eager attention デフォルト。Flash Attention 2 は推奨しない（非公式ホイール、保守リスク）。
- `docs/api_server.md` を新規作成。API リファレンス・使い方。
  - Windows PowerShell と WSL2 bash の両対応。
  - モデルキャッシュ位置、エンドポイント、クライアント使用法、ファインチューニングワークフロー、トラブルシューティング。
  - Eager attention デフォルト（公式サポート、メモリ効率 12-14GB）。

#### Implementation Notes

- `qwen_tts/` 本体への変更なし。
- 設計方針：Eager attention 標準（Windows・WSL2 共通）
  - RTX 5090 32GB なら eager で十分（全モデルロード可能）
  - Flash Attention 2 非公式ホイールは保守リスク大のため採用しない
