# wiki.llm — LLM 技術 Wiki

大規模言語モデル（LLM）に関する技術知識を、**記事単位の Markdown** として集約・公開するリポジトリです。

推論ランタイムの選定、Prefill / Decode の仕組み、サービング最適化など、実務で迷いやすいテーマを **調査メモ兼リファレンス** として整理しています。GitHub 上では `wiki/` 内の Markdown をそのまま閲覧でき、必要に応じて PDF も生成できます。

## このリポジトリに含まれるもの

```
wiki.llm/
├── wiki/          ← 記事本体（Markdown、1ファイル = 1記事）
├── gen_pdf.py     ← Markdown → LaTeX → PDF 変換スクリプト
├── Makefile       ← ビルド用（wiki/ 内の全 .md を PDF 化）
└── build/         ← 中間ファイル・PDF 出力先（git 管理外）
```

- **`wiki/`** に記事を追加・更新していきます。記事同士は Markdown リンクで相互参照できます。
- PDF が必要なときは `make pdf` で `wiki/` 内の全 `.md` を一括ビルドします（出力先: `build/`）。

## 掲載記事（wiki/）

| 記事 | 概要 |
|:--|:--|
| [LLM推論ランタイムまとめ](wiki/LLM推論ランタイムまとめ.md) | llama.cpp / vLLM / SGLang / TensorRT-LLM など主要ランタイムの分類・特徴・選定指針（2026年時点） |
| [LLM推論のPrefill詳説 ― トークン並列・Chunked Prefill・PD分離](wiki/LLM推論のPrefill詳説%20―%20トークン並列・Chunked%20Prefill・PD分離.md) | Prefill / Decode、トークン並列、Chunked Prefill、PD 分離 |

記事は今後も追加・更新していく想定です。

## PDF のビルド方法

`gen_pdf.py` は **Markdown を LaTeX に変換**し、**tectonic** で PDF を生成します。日本語は **XeLaTeX 系**（`xeCJK` / `fontspec`）で組版し、OS に応じてフォントを切り替えます（macOS: ヒラギノ系、それ以外: Noto CJK）。

### 前提ツール

| ツール | 用途 | インストール例 |
|:--|:--|:--|
| Python 3 | `gen_pdf.py` の実行 | 各 OS の標準／配布物 |
| [tectonic](https://tectonic-typesetting.github.io/) | LaTeX → PDF ビルド（**必須**） | `brew install tectonic` または `cargo install tectonic` |
| [mermaid-cli](https://github.com/mermaid-js/mermaid-cli)（`mmdc`） | Mermaid 図のローカル画像化（**任意**） | `npm install -g @mermaid-js/mermaid-cli` |

### Mermaid 図の扱い

` ```mermaid ` フェンス内の図は、次の **順に** 画像化を試みます。

1. **`mmdc` が利用可能なとき** — ローカルで PNG を生成（ネットワーク不要）。
2. **失敗時** — [mermaid.ink](https://mermaid.ink) へリクエスト（JPEG、**ネットワーク必須**。URL 長に制限あり）。
3. **それでも失敗時** — [Kroki](https://kroki.io) へ POST（PNG、**ネットワーク必須**）。

いずれも失敗した場合は、図のソースを **verbatim（引用ブロック内）** として PDF に落とします。

オフライン・プライバシー重視でオンライン経路を使わない場合は、環境変数 `MERMAID_OFFLINE` を `1` / `true` / `yes` / `on` のいずれかに設定してください（このとき `mmdc` が無いと図はテキスト出力になります）。

| 環境変数 | 意味（省略時のデフォルト） |
|:--|:--|
| `MERMAID_OFFLINE` | オンライン（mermaid.ink / Kroki）を使わない |
| `MERMAID_KROKI_URL` | Kroki のベース URL（`https://kroki.io`） |
| `MERMAID_KROKI_TIMEOUT` | Kroki 呼び出しのタイムアウト秒（`90`） |
| `MERMAID_INK_URL` | mermaid.ink のベース URL（`https://mermaid.ink`） |
| `MERMAID_INK_TIMEOUT` | mermaid.ink 呼び出しのタイムアウト秒（`90`） |

### ビルド手順（Makefile）

```bash
make pdf     # wiki/*.md → build/*.pdf
make miru    # macOS の open で build/*.pdf を表示
make clean   # build/ を削除
```

### ビルド手順（スクリプトを直接実行）

単一記事だけ PDF 化する場合:

```bash
./gen_pdf.py wiki/LLM推論ランタイムまとめ.md
```

入力・出力のパスは環境変数でも上書きできます。

| 環境変数 | 既定 | 説明 |
|:--|:--|:--|
| `PATH_MARKDOWN` | — | 入力 Markdown のパス（`make pdf` では各記事ごとに自動設定） |
| `PATH_BUILD` | `./build/` | `.tex` / `.pdf` / Mermaid 中間ファイルの出力ディレクトリ |
| `WIKI_DIR` | `./wiki` | `make pdf` が走査する記事ディレクトリ |

生成される PDF のファイル名は **入力 Markdown のベース名**に合わせます（例: `wiki/LLM推論ランタイムまとめ.md` → `build/LLM推論ランタイムまとめ.pdf`）。

### 記事のメタデータ

`gen_pdf.py` は各記事の先頭付近から次を読み取り、LaTeX の表紙・日付・作者に反映します。

- 先頭の `# タイトル` — ドキュメントタイトル
- `作成日時:` / `更新日時:` の行 — `\date` 用の文字列（該当行は本文から除く）
- `文責:` および `Contact` / `Contact email:` 行 — `\author` 用（該当行は本文から除く）

見出し `## [ch] …` は Wiki 向けプレフィックスとして扱われ、`[ch]` を除いた見出しで PDF に出力されます。

### 変換機能の概要（参考）

Markdown 側で対応している主な要素は次のとおりです。

- **見出し**（`#`〜`####`）、**段落**、**太字／斜体／インラインコード／リンク**
- **箇条書き・番号付きリスト**、**引用（`>`）**
- **テーブル**（`|` 形式。列が多い場合は `\footnotesize` で縮小）
- **コードフェンス**（` ``` `。`mermaid` 以外は quote + verbatim）

## 記事の追加・更新

1. `wiki/` に `.md` ファイルを追加または編集する
2. 先頭に `# タイトル` と日時メタデータを書く（既存記事を参考にしてください）
3. 他記事へのリンクは相対パス（例: `[Prefill 詳説](LLM推論のPrefill詳説 ― トークン並列・Chunked Prefill・PD分離.md)`）
4. `make pdf` で PDF を確認する

## ライセンス・著者

文責: 濱田 剛（Tsuyoshi Hamada） — hamada@degima.ai

### ライセンス

このリポジトリは **ドキュメント** と **コード** でライセンスが分かれています。

| 対象 | ライセンス | 該当ファイルの例 |
|:--|:--|:--|
| ドキュメント | [CC BY 4.0](LICENSE-DOCUMENTATION) | `wiki/` 内の Markdown、`README.md` |
| コードサンプル | [Apache License 2.0](LICENSE) | `gen_pdf.py`、`gen_ppt.py`、`Makefile`、記事内のコードフェンス |

- **Documentation is licensed under CC BY 4.0.**
- **Code samples are licensed under the Apache License 2.0.**
