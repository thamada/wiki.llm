# AMD XDNAアーキテクチャ概要

AMDのノートPC・デスクトップPC向けプロセッサに搭載されているAI専用チップ「XDNA」の技術解説ドキュメントです。  
設計思想・タイル構造・世代別の進化・ソフトウェアスタック・競合NPUとの比較・実際の利用シーンまでを1つの文書にまとめています。

## このリポジトリに含まれるもの

```
xdna-overview/
├── main.md        ← 本文（Markdown）
├── main.pdf       ← PDF版（配布・閲覧用のビルド済みコピー）
├── gen_pdf.py     ← Markdown → LaTeX → PDF 変換スクリプト
├── Makefile       ← ビルド用（内部で gen_pdf.py を呼び出す）
└── build/         ← 中間ファイル・再ビルド時の PDF 出力先（git管理外）
```

- **`main.md`** を読めば内容はすべて確認できます。GitHub上でそのまま閲覧可能です。
- **`main.pdf`** はリポジトリに同梱している PDF 版です（`make pdf` で得られる成果物とは別パスに置かれています）。
- PDFを自分でビルドし直す場合は、次節の手順を参照してください。

## PDFのビルド方法

`gen_pdf.py` は **Markdown を LaTeX に変換**し、**tectonic** で PDF を生成します。日本語は **XeLaTeX 系**（`xeCJK` / `fontspec`）で組版し、OS に応じてフォントを切り替えます（macOS: ヒラギノ系、それ以外: Noto CJK）。

### 前提ツール

| ツール | 用途 | インストール例 |
|:--|:--|:--|
| Python 3 | `gen_pdf.py` の実行 | 各OSの標準／配布物 |
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
make pdf
```

デフォルトでは `build/main.tex` と **`build/main.pdf`** が生成されます。PDF を開くには：

```bash
make miru    # macOS の open で build/main.pdf を表示
```

ビルド成果物を削除するには：

```bash
make clean
```

### ビルド手順（スクリプトを直接実行）

```bash
./gen_pdf.py                    # デフォルト: main.md → build/
./gen_pdf.py path/to/other.md   # 第1引数で Markdown を指定（PDF は path/to/other.pdf ではなく build/other.pdf）
```

入力・出力のパスは環境変数でも上書きできます（Makefile と同じ変数名）。

| 環境変数 | 既定 | 説明 |
|:--|:--|:--|
| `PATH_MARKDOWN` | `./main.md` | 入力 Markdown |
| `PATH_BUILD` | `./build/` | `.tex` / `.pdf` / Mermaid 中間ファイルの出力ディレクトリ |

生成される PDF のファイル名は **入力 Markdown のベース名**に合わせます（例: `main.md` → `build/main.pdf`）。

### メタデータ（`main.md` 側）

`gen_pdf.py` は本文の先頭付近から次を読み取り、LaTeX の表紙・日付・作者に反映します。

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

## main.md の主な内容

1. **概要** — XDNAとは何か、3行での要点
2. **技術的起源** — Xilinx AI Engineから AMD XDNAへの経緯
3. **アーキテクチャの基本構造** — 空間データフロー、2Dタイルアレイ、AIE計算タイルの内部
4. **世代別の進化** — XDNA → XDNA 2 → 今後のロードマップ、SKU一覧
5. **データ型と精度** — INT8/INT4/BFP16、GEMM性能の実測値
6. **ソフトウェアスタック** — ONNX Runtime、OGA、Lemonade SDK、Linuxドライバ
7. **競合NPUとの比較** — Intel NPU 4、Qualcomm Hexagonとの対比
8. **実際の利用シーン** — Copilot+ PC、ローカルLLM推論、エッジAI
9. **設計思想まとめ** — 決定論的実行、スケーラビリティ、プログラマビリティ、電力効率
10. **NPU専用時代の終焉？** — RDNA 5 Neural Arraysへの統合可能性、リーク情報の検証と著者の見解
11. **まとめ** — XDNAの現在地と今後の展望

## ライセンス・著者

文責: 濱田 剛（Tsuyoshi Hamada） — hamada@degima.ai
