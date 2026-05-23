# LLM推論ランタイムまとめ

作成日時: 2026-02-19 00:00:00
更新日時: 2026-05-23 17:15:00

## 概要

LLMの「推論ランタイム」と一口に言っても、役割が混ざりやすいので、まず分類します。

| 分類 | 代表例 | ざっくり何をしているか |
|:--|:--|:--|
| 推論エンジン / ランタイム | llama.cpp / vLLM / TensorRT-LLM / SGLang / LMDeploy（TurboMind） / ONNX Runtime GenAI / OpenVINO GenAI / MLC LLM / MLX / Petals（協調推論） | モデルを実行してトークン生成（KVキャッシュ、バッチング、量子化など）を最適化 |
| AI infra / FT・推論統合 | Unsloth など | 既存推論エンジン（llama.cpp / HF 等）を下流に使い、独自カーネル・量子化・FT 高速化・UX で性能と体験を引き上げ |
| サービング基盤 / オーケストレーション | Triton / Ray Serve / KServe など | デプロイ、スケール、ルーティング、観測（LLM専用ではない） |
| 推論ルーター / モデルスワップ層 | llama-swap など | OpenAI/Anthropic互換の入口でモデルIDに応じて上流サーバを切替し、運用を簡素化 |
| ローカル実行ツール / UI | Ollama / LM Studio / Unsloth Studio / Open WebUI など | モデル管理・UI・OpenAI互換などをまとめて提供（内部で別ランタイムを使うことが多い） |

この記事では、主に「推論エンジン / ランタイム（＋それを含む推論サーバ）」を中心に、2026年時点の定番と選び方を整理します。Unsloth のように **推論エンジンそのものではなく統合・加速レイヤ** として登場する製品も、後述で扱います。

## 選定でまず見るポイント（実務向け）

- **性能の見方**: 単発tokens/sだけでなく、TTFT（最初のトークンまで）、同時接続時スループット、長文プロンプト時のprefill性能を見る
- **同時リクエスト**: continuous/in-flight batching、chunked prefill、prefix caching / KV cache reuse（プロンプト再利用が多いなら特に重要）
- **マルチテナント**: cache salt等によるKV再利用の隔離、優先度制御、レート制限
- **モデル形式**: HF（safetensors）/ GGUF / ONNX / TensorRT engineなど、入手経路と変換コスト
- **量子化**: 重み（INT4/INT8/FP8、GPTQ/AWQなど）とKVキャッシュ（量子化可否）でメモリ・速度・品質が変わる
- **運用**: OpenAI互換API、メトリクス（Prometheus等）、トレーシング、Docker/K8s、LoRA（Multi-LoRA）運用

## 主要なLLM推論ランタイム（推論エンジン / サーバ）

### 1. llama.cpp（ローカル〜軽量サーバ、GGUF中心）

**概要**: C/C++実装の軽量ランタイム。GGUFモデルを中心に、CPUから各種GPUまで幅広いバックエンドに対応します。`llama-server` でOpenAI互換HTTPサーバも提供されます。

**特徴**:
- **モデル形式**: GGUF
- **対応環境**: CPU最適化＋CUDA/Metal/HIP/Vulkan/SYCL等のバックエンド
- **サーバ**: `llama-server`（OpenAI API互換、簡易Web UI、並列デコード等）
- **周辺ツール**: `llama-bench`（性能計測）、GBNF grammar（出力制約）など
- **structured outputs**: GBNF（GGML BNF）でJSON等の制約生成が可能（JSON用のgrammar同梱）

**向いている用途**:
- ローカル実行（Windows/macOS/Linux）、エッジ/組み込み、オフライン
- 依存関係を増やさずに配布したい、GGUFでサクッと試したい
- 小〜中規模の社内サーバでOpenAI互換APIが欲しい（手軽さ重視に加え、条件次第で高スループットも狙いたい）

**注意点**:
- **OpenAI API 完全互換が最優先ではない**: llama.cpp はローカル推論・GGUF・多様なモデル機能・マルチモデル / マルチモーダル / ツール呼び出しなどを **実用重視で拡張** するプロジェクトであり、OpenAI 仕様との完全互換を第一目標とはしていない。結果として OpenAI SDK や既存クライアントと **挙動がズレるケース** がある
- **マルチモデル対応は OpenAI 互換を犠牲にした設計ではない**: 複数モデルの切り替えは `/v1/models` やリクエストの `model` フィールドを活用して実装されており、互換 API の枠組みの中で提供されている
- 「最高スループットは常に vLLM/SGLang/TensorRT-LLM」とは言い切れない（同一条件で llama.cpp が同等〜上回る実測がある）
- 一方で高並列ワークロードでは vLLM が有利な点もあり、結論は並列度・コンテキスト長・精度・最適化機能（FlashInfer / `LLAMA_SET_ROWS=1` など）に依存
- HFモデルからGGUFへの変換・量子化が必要になるケースがある

**参考リンク**:
- [llama.cpp（ggml-org）](https://github.com/ggml-org/llama.cpp)
- [GBNF（GGML BNF）: grammars/README.md](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md)
- [JSON grammar（json.gbnf）](https://github.com/ggml-org/llama.cpp/blob/master/grammars/json.gbnf)
- [llama.cpp vs vllm performance comparison（Discussion #15180）](https://github.com/ggml-org/llama.cpp/discussions/15180)
- [llama : add high-throughput mode（PR #14363）](https://github.com/ggml-org/llama.cpp/pull/14363)
- [llama.cppでgpt-ossモデルを動かす方法](./llama.cppでgpt-ossモデルを動かす方法.md)

### 2. vLLM（汎用サービングの定番、OpenAI互換）

**概要**: 高スループット推論/サービングに強いランタイム。PagedAttentionとcontinuous batchingを軸に、OpenAI互換APIサーバを提供します。

**特徴**:
- **OpenAI互換サーバ**: `/v1/chat/completions`、`/v1/completions`、`/v1/embeddings` などをサポート
- **高速化要素**: PagedAttention、continuous batching、chunked prefill、speculative decoding、FlashAttention/FlashInfer統合、各種量子化
- **prefix caching（Automatic Prefix Caching）**: KV-cache blockのハッシュ（v1はhash-based）で自動共有。**マルチテナントでは `cache_salt` による隔離**が可能
- **ハッシュ方式の選択**: `vllm serve` では `--prefix-caching-hash-algo` で `sha256`（既定）/ `sha256_cbor` / `xxhash` / `xxhash_cbor` 等を選べる（再現性やセキュリティ許容度で選定）
- **structured outputs（guided decoding）**: choice / regex / JSON schema / grammar / structural tag など（`xgrammar` / `llguidance` 等のバックエンド）
- **運用機能**: streaming、prefix caching、Multi-LoRA、分散（tensor/pipeline/data/expert parallel）
- **対応ハード**: 主にNVIDIA CUDA。CPU（x86_64/arm64）やAMD ROCm、Intel Gaudi（HPU）、TPU（別ドキュメント階層）なども対象（対応範囲は公式ドキュメント参照）

**向いている用途**:
- 社内/自社のOpenAI互換APIサーバ（多ユーザー・高スループット）
- HFモデルをそのまま運用したい

**注意点**:
- `--generation-config` のデフォルトは `auto`（モデル側のgeneration configを読む）で、vLLMの既定値に寄せたい場合は `--generation-config vllm` を使う（サーバ全体に効く `max_new_tokens` 上限などに注意）
- **prefix cachingのセキュリティ**: vLLMは `sha256` など複数のハッシュ方式を持つ。高速な非暗号学的ハッシュは理論上の衝突リスクがあり、マルチテナントでは情報漏えいリスク（タイミング差など）も考慮して `cache_salt` を検討する

**参考リンク**:
- [vLLM Docs](https://docs.vllm.ai/)
- [OpenAI-Compatible Server（vLLM）](https://docs.vllm.ai/en/stable/serving/openai_compatible_server.html)
- [Engine Arguments（--generation-configの説明）](https://docs.vllm.ai/en/stable/configuration/engine_args/)
- [Automatic Prefix Caching（vLLM）](https://docs.vllm.ai/en/stable/design/prefix_caching/)
- [Structured Outputs（vLLM）](https://docs.vllm.ai/en/stable/features/structured_outputs.html)
- [vLLM TPU](https://docs.vllm.ai/projects/tpu/en/latest/)
- [vLLM公式リポジトリ](https://github.com/vllm-project/vllm)

### 3. SGLang（RadixAttentionによるprefix再利用・高スループット）

**概要**: 大規模サービングから単体GPUまでをカバーする高性能サービングフレームワーク。RadixAttentionでprefix caching（KV再利用）を強く意識しています。

**特徴**:
- **高速化要素**: RadixAttention（prefix caching）、prefill/decode分離、speculative decoding、continuous batching、chunked prefill等
- **API**: OpenAI互換APIに加え、ネイティブAPIも提供
- **運用機能**: structured outputs、Multi-LoRA batching、分散並列（tensor/pipeline/expert/data parallel）などを広くカバー
- **structured outputs**: JSON schema / regex / EBNF をサポート。grammar backendとして `XGrammar`（デフォルト, 推奨）/ `Outlines` / `Llguidance` が選べる

**向いている用途**:
- 多ターン/エージェント/RAGなど「prefix再利用」が多いワークロード
- OpenAI互換で高スループットを狙いたい（vLLMと比較検討枠）

**参考リンク**:
- [SGLang Docs](https://sgl-project.github.io/)
- [Structured Outputs（SGLang）](https://sgl-project.github.io/advanced_features/structured_outputs.html)
- [SGLang公式リポジトリ](https://github.com/sgl-project/sglang)

### 4. TensorRT-LLM（NVIDIA GPUで最大性能を狙う）

**概要**: NVIDIA GPUに特化した高性能推論ランタイム。TensorRTベースでエンジン化（コンパイル）して本番性能を引き出します。

**特徴**:
- **Paged KV cache + cross-request reuse**: KVをブロック管理し、radix treeでprefix一致時に再利用。優先度付きLRUやオフロードもサポート
- **マルチテナント対策**: `cache_salt` によるKV再利用の隔離（salt一致時のみ再利用）など
- **in-flight batching / speculative decoding**: サービング向け最適化を継続的に追加

**向いている用途**:
- NVIDIA GPUで「1台あたり性能」を最大化したい本番推論
- 厳密にチューニングしてレイテンシ/コストを詰めたい

**注意点**:
- NVIDIA GPU前提
- エンジンビルド/最適化パラメータの理解が必要で、運用までの初期コストは高め

**参考リンク**:
- [TensorRT-LLM公式ドキュメント](https://nvidia.github.io/TensorRT-LLM/)
- [KV Cache System（TensorRT-LLM）](https://nvidia.github.io/TensorRT-LLM/features/kvcache.html)
- [KV cache reuse（TensorRT-LLM）](https://nvidia.github.io/TensorRT-LLM/advanced/kv-cache-reuse.html)

### 5. ONNX Runtime GenAI（ONNXで生成ループまで提供）

**概要**: ONNX Runtime上で、生成AIの推論ループ（KV cache、sampling、grammar等）まで含めて扱いやすくするライブラリ。オンデバイス/クロスプラットフォーム寄りです。

**特徴**:
- **対象**: ONNX形式のモデル
- **実装**: 生成ループ（前処理〜logits処理〜sampling〜KV管理〜grammar）をAPI化
- **対応**: Python/C#/C++/Java、Linux/Windows/macOS/Android等
- **アクセラレーション**: CPU/CUDA/DirectML/OpenVINO/QNN/WebGPU/TRT-RTX等（利用可否はOS/配布物/ビルドに依存。WebGPUはブラウザ向けEPの文脈と混同しやすいので注意）

**向いている用途**:
- Windows/Android等を含むオンデバイス推論
- ONNXに統一して推論基盤を作りたい

**参考リンク**:
- [onnxruntime-genai（GitHub）](https://github.com/microsoft/onnxruntime-genai)
- [ONNX Runtime GenAI docs](https://onnxruntime.ai/docs/genai)
- [ONNX Runtime Web: WebGPU EP](https://onnxruntime.ai/docs/tutorials/web/ep-webgpu.html)

### 6. OpenVINO GenAI（Intel CPU/GPU/NPU向けの軽量パイプライン）

**概要**: OpenVINOの生成AI向けライブラリ。LLM/VLM/Whisper/Stable Diffusion等の「パイプライン」を軽量に提供し、Intel向け最適化を活かします。

**特徴**:
- **パイプラインAPI**: `LLMPipeline` 等で推論ループ込み
- **最適化**: speculative decoding、KV-cache最適化、LoRA適用/切替など（公式サイト参照）
- **クロスプラットフォーム**: Linux/Windows/macOS

**向いている用途**:
- Intel CPU/GPU/NPUでの推論（PC/エッジ/オンプレ）
- 依存を抑えつつ、C++/Pythonで運用したい

**参考リンク**:
- [OpenVINO GenAI](https://openvinotoolkit.github.io/openvino.genai/)
- [Install OpenVINO GenAI（対応OSの明記あり）](https://openvinotoolkit.github.io/openvino.genai/docs/getting-started/installation/)

### 7. MLC LLM / WebLLM（iOS/Android/ブラウザへコンパイル配布）

**概要**: TVM系のコンパイラ/デプロイエンジンとして、iOS/Android/WebGPU（ブラウザ）など幅広い環境へLLMを持っていく選択肢です。

**特徴**:
- **方向性**: 対応デバイスで動くことを強く意識（WebLLMなど）
- **注意**: 事前コンパイル/変換のワークフローが前提

**参考リンク**:
- [MLC LLM docs](https://llm.mlc.ai/docs/index.html)
- [MLC LLM公式リポジトリ](https://github.com/mlc-ai/mlc-llm)

### 8. MLX / MLX-LM（Apple Silicon向け）

**概要**: Apple Silicon最適化のMLX上で、LLMの生成や軽いFTまで扱いやすくした `mlx-lm` が便利です。

**特徴**:
- **導入**: `pip install mlx-lm`
- **強み**: HF Hub統合、量子化、prompt caching、rotating KV cache等（Macローカルで扱いやすい）

**参考リンク**:
- [MLX](https://mlx-framework.org/)
- [mlx-lm（GitHub）](https://github.com/ml-explore/mlx-lm)

### 9. LMDeploy / TurboMind（単一ノード・マルチGPUのOpenAI互換サーバ、persistent batch）

**概要**: OpenMMLab/InternLM系の推論サービング。OpenAI互換の `api_server` を提供し、単一ノード内のマルチGPU展開を前提にした運用導線が用意されています。内部エンジンとして **TurboMind**（C++/CUDA）を持ち、persistent batch（continuous batching相当）とKV cache manager（LRU）を組み合わせます。

**特徴**:
- **OpenAI互換サーバ**: `/v1/chat/completions`、`/v1/models`、`/v1/completions`
- **マルチGPU**: `--tp` 等でtensor parallelを指定（単一ノードの複数GPUを主眼）
- **persistent batch**: サービス稼働中に“常駐バッチ”としてスロットを保持し、空きが出たらリクエストを参加させるモデル
- **KV cache manager**: メモリプール + LRUで管理し、cache hit時は履歴の再デコードを省略（ミス時はtoken IDsから再構築）

**向いている用途**:
- 単一ノード（複数GPU）でのOpenAI互換サービングを、比較的シンプルに立ち上げたい
- prefix（会話履歴）再利用が多いチャット/エージェント系ワークロード

**参考リンク**:
- [LMDeploy: OpenAI Compatible Server](https://lmdeploy.readthedocs.io/en/latest/llm/api_server.html)
- [TurboMind Architecture（persistent batch / KV cache manager）](https://lmdeploy.readthedocs.io/en/latest/inference/turbomind.html)

### 10. FlexGen（単一GPUで巨大LLMを回すためのオフロード最適化）

**概要**: FlexGenは、GPUメモリが小さい環境でも巨大LLMを動かすために、**重み・中間テンソル・KVキャッシュ等を GPU/CPU/SSD にオフロード**しつつ、I/Oを意識した実行スケジュールで**スループット（throughput）**を狙う研究系の推論システムです（ICML 2023）。

**詳細**:
- [FlexGen（単一GPUで巨大LLMを回すためのオフロード最適化）](./FlexGen（単一GPUで巨大LLMを回すためのオフロード最適化）.md)

**特徴**:
- **オフロード前提**: モデル重みやKVキャッシュなどをGPUに常駐させず、CPUメモリやSSDを活用して実行
- **圧縮（4-bit）**: 重み・attention cache（KV）などを圧縮して、転送量とメモリ使用量を削減（品質劣化を抑える設計）
- **最適化（探索）**: ハード制約（GPU/CPU/SSD帯域や容量）に合わせて、どのテンソルをどこに置くかのパターンを探索して性能を引き出す
- **レイテンシよりスループット志向**: “単発の応答速度”より、**バッチ処理的に生成を回して総量を稼ぐ**発想と相性が良い

**向いている用途**:
- GPUメモリが小さいが、巨大モデルを使った**バッチ生成・評価・ベンチ・データ処理**をしたい
- 研究/検証で「単一GPU＋オフロード」でどこまで動くか試したい

**注意点**:
- インタラクティブ用途の低レイテンシには向きにくい（SSD I/Oやオフロードの影響を受けやすい）
- 実運用の“汎用OpenAI互換サービング”の主流は vLLM / SGLang / TensorRT-LLM 等になりやすく、FlexGenは**特定目的（単一GPUで巨大モデル）寄り**

**参考リンク**:
- [FlexGen（GitHub）](https://github.com/FMInference/FlexGen)
- [FlexGen: High-Throughput Generative Inference of Large Language Models with a Single GPU（ICML 2023 / PMLR）](https://proceedings.mlr.press/v202/sheng23a.html)

### 11. Unsloth（Fine-tuning特化 + ローカル推論 / API）

**概要**: Unsloth は QLoRA/LoRA fine-tuning を高速・低 VRAM 化する Python ライブラリ（**Unsloth Core**）と、モデルの検索・学習・推論・エクスポートを一括で行う Web UI（**Unsloth Studio**）を提供します。

**位置づけ**: 現時点では vLLM や llama.cpp に相当する **フルスタック LLM 推論ランタイムをゼロから開発しているわけではありません**。一方で、Triton カーネルや独自量子化、トレーニング高速化、推論ラッパー／統合層、Studio UX など **独自最適化の技術資産** を持っています。したがってポジションとしては、

- **ではない**: vLLM / llama.cpp を **代替する推論エンジン企業**
- **に近い**: **既存推論エコシステムを活用しつつ、独自最適化で性能を引き上げる AI infra 企業**

推論実行の下流では llama.cpp や Hugging Face / PyTorch を使い、Unsloth 側は FT〜ローカル API までの **統合・加速レイヤ** として機能します。

**Unsloth 独自の技術資産**:

| 領域 | 内容 |
|:--|:--|
| **独自最適化カーネル** | Triton kernels による演算高速化（FT / 推論の両方で効く） |
| **独自量子化** | 4-bit 等の量子化パイプライン（VRAM 削減と速度向上） |
| **トレーニング高速化** | QLoRA/LoRA を含む FT パスの最適化（公式では最大 2 倍高速・最大 80% VRAM 削減） |
| **推論ラッパー / 統合層** | `FastLanguageModel.for_inference()` 等の API、Studio からの llama-server 管理、エクスポート（GGUF / safetensors） |
| **Studio UX** | モデル検索・比較・FT・推論・API 公開を一つの Web UI に集約 |

**推論バックエンド（2系統）**:

| モデル形式 | 内部エンジン | 概要 |
|:--|:--|:--|
| **GGUF** | llama.cpp の `llama-server` | Studio がサブプロセスで起動し、OpenAI 互換 `/v1/chat/completions` をプロキシ。`--flash-attn on`、`--fit` によるマルチ GPU 自動オフロード、HF Hub からの `-hf "repo:quant"` 直接ロードに対応 |
| **safetensors / HF** | Unsloth Core（PyTorch + 独自カーネル） | `FastLanguageModel.for_inference()` / `FastVisionModel.for_inference()` / `FastModel.for_inference()` で HF 互換の `model.generate()` を最適化。公式では QLoRA/LoRA/非 LoRA いずれも **約 2 倍高速** と謳う |

**特徴**:
- **Unsloth Studio API**: 認証付きの OpenAI 互換（`/v1/chat/completions`、`/v1/responses`）と Anthropic 互換（`/v1/messages`）を同一ポートで提供。Claude Code / Cursor / Open WebUI 等からローカル LLM に接続可能
- **エージェント向け機能**: self-healing tool calling、サーバサイド code execution（Bash + Python）、advanced web search、GGUF 向け自動推論パラメータ調整
- **モデル対応**: GGUF / safetensors / LoRA アダプタ / VLM / 音声（Whisper, TTS 等）を UI から検索・ロード・比較
- **エクスポート**: FT 済みモデルを GGUF（llama.cpp / Ollama 向け）や 16-bit safetensors に書き出し、vLLM 等へのデプロイ前段として使える
- **マルチ GPU**: GGUF パスではモデルサイズと空き VRAM から GPU を自動選択。NVIDIA 向けに強化中（公式ロードマップ参照）

**向いている用途**:
- FT 直後の推論・品質確認（LoRA をそのまま `FastLanguageModel` で試す）
- ローカルでエージェント開発（tool calling / code execution 付き API）
- GGUF 変換 → llama.cpp / Ollama / vLLM への配布前パイプライン

**注意点**:
- **推論エンジンの完全代替ではない**: 本番の高並列サービング（continuous batching、chunked prefill、prefix caching 等）は vLLM / SGLang / llama-server 単体に委ねる構成が一般的
- **Studio の GGUF パスはローカル利用向け**: `--parallel 1`（単一ユーザー想定）など、マルチテナント本番サーバ向けの設計ではない
- **価値は「下流エンジン + 独自最適化」の組み合わせ**: ゼロからの推論ランタイム開発ではなく、既存エコシステム上で FT / 推論 / デプロイまでを一気通貫に速く・軽くする AI infra として理解するのが適切

**参考リンク**:
- [Unsloth（GitHub）](https://github.com/unslothai/unsloth)
- [Unsloth Studio ドキュメント](https://unsloth.ai/docs/new/studio)
- [Unsloth Inference（Core）](https://unsloth.ai/docs/basics/inference-and-deployment/unsloth-inference)
- [Unsloth API エンドポイント](https://unsloth.ai/docs/basics/api)
- [Saving to GGUF](https://unsloth.ai/docs/basics/inference-and-deployment/saving-to-gguf)

### 12. Petals（協調推論：インターネット越しに層を分散実行）

**概要**: Petalsは、巨大LLMのTransformerブロックを複数ピアで分担して実行する協調推論システムです。各参加ノードが一部レイヤをホストし、クライアントが中間活性を順に転送して生成を進めます。単体GPUでは載り切らないモデルでも、分散前提で試しやすいのが特徴です。

**特徴**:
- **協調推論**: モデル全体を1台で保持せず、複数ピアに分散したレイヤを順次呼び出して推論
- **低い手元要件**: 手元GPUメモリが小さくても、大規模モデルの実験を始めやすい
- **研究/実験に強い**: 分散推論・協調実行のプロトタイピングに向く
- **ネットワーク依存**: 利用可能モデルや性能は、接続先ピアの状態・帯域・混雑の影響を受ける

**向いている用途**:
- 単体マシンでは載らない巨大モデルを、まずは低コストで検証したい
- 協調推論の研究やPoCを行いたい

**注意点**:
- **レイテンシの揺れ**: インターネット越し通信のため、TTFTやトークン速度が安定しにくい
- **可用性/機密性**: 公開ネットワーク上のピア利用は、SLAや機密データ要件が厳しい本番用途には不向き
- **汎用サービングとは別軸**: 社内OpenAI互換APIの安定運用なら vLLM / SGLang / TensorRT-LLM などが選ばれやすい

**参考リンク**:
- [Petals（GitHub）](https://github.com/bigscience-workshop/petals)
- [Petals公式サイト](https://petals.dev/)
- [Petals: Collaborative Inference and Fine-tuning of Large Models（arXiv）](https://arxiv.org/abs/2209.01188)

## モデル形式と対応ランタイム（ざっくり）

| モデル形式 | 例 | 主に使われるランタイム |
|:--|:--|:--|
| HF Transformers（safetensors等） | Hugging Faceの `meta-llama/...` など | vLLM / SGLang / Unsloth Core / TGI |
| GGUF | `...-GGUF` | llama.cpp / Ollama / LM Studio / Unsloth Studio など |
| ONNX | `...-onnx` | ONNX Runtime GenAI |
| OpenVINO IR | OpenVINO変換後のIR | OpenVINO GenAI |
| TensorRT engine | TensorRT-LLMでビルドしたエンジン | TensorRT-LLM / Triton |
| MLC LLM artifacts | MLCでコンパイルした成果物 | MLC LLM / WebLLM |
| MLX形式 | MLX向けに変換した重み | MLX-LM |

## 周辺ツール（ランタイムそのものではない）

### ローカル実行ツール / UI（内部で別ランタイムを使うことが多い）

- [Ollama](https://github.com/ollama/ollama): ローカルでモデル管理とAPI提供
- [LM Studio](https://lmstudio.ai/): ローカル実行向けデスクトップアプリ（OpenAI互換APIなど）
- [Unsloth Studio](https://unsloth.ai/docs/new/studio): FT + 推論 + エクスポートの Web UI。vLLM / llama.cpp 代替ではなく、既存エコシステム（llama-server / HF）上に独自最適化を載せた AI infra
- [Open WebUI](https://github.com/open-webui/open-webui): OpenAI互換APIのバックエンドに接続するWeb UI
- [LocalAI](https://github.com/mudler/LocalAI): OpenAI互換APIのローカルサーバ（複数バックエンド）
- [KoboldCpp](https://github.com/LostRuins/koboldcpp): llama.cppベースのローカル実行ツール
- [text-generation-webui](https://github.com/oobabooga/text-generation-webui): Web UI（複数バックエンド）

### モデル切替ルーター / プロキシ（ランタイム本体ではない）

#### llama-swap

**概要**: `llama-swap` は、OpenAI/Anthropic互換APIの前段に置く軽量ルーターです。`model` 指定に応じて上流の推論サーバ（`llama.cpp` / `vLLM` など）を切り替えることで、クライアント側の接続先を固定したままモデルをホットスワップできます。

**特徴**:
- **モデルスワップ**: `model` ごとに上流サーバを切り替え、必要に応じてロード/アンロードを制御
- **互換APIの入口を一本化**: OpenAI互換（`/v1/chat/completions` など）とAnthropic互換（`/v1/messages` など）を同一運用に寄せられる
- **構成がシンプル**: 「1バイナリ + 1設定ファイル」の構成で導入しやすい
- **運用補助機能**: `groups`（同時ロード）、`ttl`（自動アンロード）、`hooks`（起動時処理）、`aliases` などを提供
- **監視/操作API**: `/ui`、`/running`、`/models/unload`、`/health`、`/logs` 系エンドポイントを利用可能

**向いている用途**:
- 既存クライアント（OpenAI/Anthropic SDK）の接続先を変えずに、モデルや上流ランタイムを切り替えたい
- ローカル/オンプレ環境で複数モデルを用途別に運用し、アイドル時は自動で解放したい

**注意点**:
- `llama-swap` 自体は推論エンジンではないため、生成速度や品質の上限は背後のランタイム（vLLM / llama.cpp / TensorRT-LLM など）に依存
- モデル切替時には上流プロセスの起動・ウォームアップ時間が発生するため、レイテンシ要件に応じた設定（`groups` / `ttl` 等）が必要

**参考リンク**:
- [llama-swap（GitHub）](https://github.com/mostlygeek/llama-swap)
- [llama-swapをセットアップする方法](./llama-swapをセットアップする方法.md)

### サービング基盤 / オーケストレーション（LLM専用ではない）

- [NVIDIA Triton Inference Server](https://github.com/triton-inference-server/server): 汎用推論サーバ（各種バックエンドを統合）
- [Ray Serve](https://docs.ray.io/en/latest/serve/index.html): 分散サービング/デプロイ基盤
- [KServe](https://kserve.github.io/website/): Kubernetes上のモデルサービング基盤

### 位置づけ注意（「ランタイム」そのものではなく、配布・運用単位）

#### NVIDIA NIM（Neural Inference Microservices）

**概要**: NVIDIAのマイクロサービス群（NVIDIA AI Enterpriseの一部）。**中身は TensorRT-LLM / vLLM / SGLang などの実ランタイム**をモデルプロファイルとしてパッケージし、Dockerで“本番用ランタイム＋更新（セキュリティ含む）”を提供する位置づけです。

**向いている用途**:
- NVIDIA GPU前提で、運用とセキュリティ更新を含めて「箱」として導入したい
- ランタイム選択やプロファイル（GPU/精度/最適化）を管理して本番導入したい

**参考リンク**:
- [NVIDIA NIM Docs](https://docs.nvidia.com/nim/index.html)

### デバイス向け（OS/フレームワークに依存）

- [Core ML](https://developer.apple.com/documentation/coreml): Appleプラットフォーム向け推論基盤
- [ExecuTorch](https://github.com/pytorch/executorch): PyTorchのエッジ向け推論ランタイム

## 位置づけに注意（メンテナンスモード/移行済み）

### Text Generation Inference（TGI）

Hugging Faceの推論サーバです。公式ドキュメントにて **maintenance mode**（今後は軽微な修正中心）であること、そして推奨エンジンとして vLLM / SGLang / llama.cpp / MLX などを挙げていることが明記されています。

**参考リンク**:
- [TGI docs](https://huggingface.co/docs/text-generation-inference/index)
- [text-generation-inference公式リポジトリ](https://github.com/huggingface/text-generation-inference)

### FasterTransformer

READMEにて、開発はTensorRT-LLMへ移行した旨が明記されています。

**参考リンク**:
- [FasterTransformer（GitHub）](https://github.com/NVIDIA/FasterTransformer)
- [TensorRT-LLM（GitHub）](https://github.com/NVIDIA/TensorRT-LLM)

## ランタイム選定の指針

### 選定チャート

```
GPUあり？
├─ はい → 複数ユーザー同時アクセス？
│   ├─ はい → vLLM / SGLang / llama.cpp（同条件ベンチで比較）
│   └─ いいえ → llama.cpp（手軽） / TensorRT-LLM（NVIDIAで最大性能） / LMDeploy（単一ノード・複数GPUでOpenAI互換）
└─ いいえ → llama.cpp / OpenVINO GenAI / ONNX Runtime GenAI（目的と環境次第）
```

### ユースケース別の推奨

| ユースケース | 推奨ランタイム | 理由 |
|:------------|:--------------|:------|
| 社内OpenAI互換APIサーバ構築（多ユーザー） | vLLM / SGLang / llama.cpp（要実測比較） | 公開比較で差が縮まる/逆転する条件もあり、同条件ベンチが重要 |
| 同一APIエンドポイントでモデルを動的に切り替えたい | llama-swap（+ vLLM / llama.cpp 等） | `model` 指定で上流をホットスワップでき、クライアント設定を固定しやすい |
| 単一ノード複数GPUでOpenAI互換サーバを立てたい | LMDeploy（TurboMind） | `api_server`、persistent batch、KV cache manager（LRU） |
| GPUメモリが小さいが巨大モデルをバッチ生成/評価したい（レイテンシ非重視） | FlexGen（研究寄り） | GPU/CPU/SSDオフロードで単一GPUでも動かす発想 |
| 手元GPUが小さく巨大モデルをまず試したい（研究・PoC） | Petals（協調推論） | ネットワーク上でレイヤを分担実行し、単体では載らない規模を検証しやすい |
| prefix再利用が多い（RAG/エージェント/多ターン） | SGLang（比較でvLLMも） | RadixAttention等のprefix cachingが強い |
| FT 直後の推論・LoRA 検証 | Unsloth Core / Unsloth Studio | `FastLanguageModel.for_inference()` で FT モデルをそのまま試せる。Studio は tool calling 付き API も |
| ローカルPCで軽く試す | llama.cpp / LM Studio / Ollama / Unsloth Studio | 導入が簡単、CPUでも動作しやすい（Unsloth Studio は CPU でも Chat 推論可） |
| エージェント開発（Claude Code / Cursor 等をローカル LLM に接続） | Unsloth Studio API | OpenAI/Anthropic 互換 + self-healing tool calling / code execution |
| Edge/IoT/オフライン | llama.cpp / MLC LLM | 低依存・デバイス向けの選択肢 |
| NVIDIA GPU本番環境で性能を詰める | TensorRT-LLM | NVIDIA最適化、KV再利用/オフロード等 |
| Windows/Android等のオンデバイス | ONNX Runtime GenAI | クロスプラットフォーム、複数アクセラレータ |
| Intel CPU/GPU/NPU中心の推論 | OpenVINO GenAI | Intel最適化、軽量パイプライン |

## 性能比較の目安

### 数字を信じすぎない（見るべき指標）

- **同じ条件で測る**: モデル、量子化、max context、温度等を揃える
- **prefill と decode を分けて見る**: 長いプロンプトほどprefillが支配的になる
- **本番想定の同時接続で測る**: batchingの効き具合が変わる

### ベンチマークに使えるツール（TTFT/ITL/throughput）

- **GenAI-Perf**: 推論サーバに負荷をかけ、TTFT / ITL / output token throughput / request throughput などを集計（CSV/JSON出力、可視化も可能）
  - ただし公式READMEでは **GenAI-Perfは段階的にフェーズアウト**と明記されており、新規のベンチ用途は **AIPerf** が推奨されています

### llama.cpp と vLLM の公開比較（2025-2026時点）

- **同一GPU・同一モデル比較（RTX 4090 / Qwen2.5-3B）**: llama.cpp開発者による公開比較では、単一並列で llama.cpp の実行時間は **vLLM比 93.6〜100.2%**（同等〜一部で高速）。16並列でも **99.2〜125.6%** で、`prompt=24576 / gen=256 / 16並列` では llama.cpp が **約0.8%高速** の点がある（[Discussion #15180](https://github.com/ggml-org/llama.cpp/discussions/15180)）。
- **公開CSV（Argonne LLM-Inference-Bench）にも逆転ケース**: `Intel Max 1550 / Qwen2-7B / input=128 / output=128 / batch=1` で llama.cpp **20.82**、vLLM **13.12**（Throughput列）。`AMD MI300X(4GPU) / Qwen2-7B / 同条件` でも llama.cpp **99.08**、vLLM **85.19**（[All_results.csv](https://raw.githubusercontent.com/argonne-lcf/LLM-Inference-Bench/main/Plots/All_results.csv)）。
- **古い比較だけで固定判断しない**: 2024年の比較（[Discussion #6730](https://github.com/ggml-org/llama.cpp/discussions/6730)）では vLLM 優位が大きかったが、その後 llama.cpp には high-throughput mode（split KV cache）などの最適化が入り、差が縮む条件が増えている（[PR #14363](https://github.com/ggml-org/llama.cpp/pull/14363)）。
- **実務上の結論**: 「最大スループットは常にどれ」と決め打ちせず、同一モデル・同一精度・同一コンテキスト長・同一並列度・同一オプションで測定する。

**参考リンク**:
- [GenAI Performance Analyzer（Triton Docs）](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/perf_benchmark/genai_perf.html)
- [GenAI-Perf README（phased out / AIPerf推奨の明記あり）](https://raw.githubusercontent.com/triton-inference-server/perf_analyzer/main/genai-perf/README.md)
- [AIPerf](https://github.com/ai-dynamo/aiperf)

手元での簡易ベンチ例:

```bash
# llama.cpp
llama-bench -m model.gguf
```

**注意**: 性能はモデルサイズ、量子化、バッチ、コンテキスト長、ハード構成で大きく変動します。実際の環境・想定トラフィックで測るのが確実です。

## まとめ

- **llama.cpp**: 軽量・汎用実行（GGUF）。ローカル/エッジだけでなく、条件次第でサーバ用途でもvLLM系と同等〜上回る実測がある
- **vLLM**: OpenAI互換＋高スループットサービングの有力選択肢（PagedAttention/continuous batching等）
- **SGLang**: prefix再利用が多いワークロードや大規模サービングで強力（RadixAttention等）
- **TensorRT-LLM**: NVIDIA GPUで性能を詰めたい本番向け（エンジン化、KV再利用/オフロード等）
- **LMDeploy / TurboMind**: 単一ノード・マルチGPUのOpenAI互換サービングで選択肢（persistent batch、LRUなKV cache manager）
- **FlexGen**: GPU/CPU/SSDオフロードで単一GPUでも巨大モデルの生成を回す（研究寄り、スループット志向）
- **Unsloth**: vLLM / llama.cpp の代替エンジンではなく、Triton カーネル・独自量子化・FT 高速化・推論統合層・Studio UX を持つ AI infra。下流は llama-server または Core（PyTorch + 独自最適化）
- **Petals**: 協調推論で巨大モデルを分散実行できる（研究・PoC向け、ネットワーク品質の影響が大きい）
- **llama-swap**: ランタイム本体ではなく、OpenAI/Anthropic互換APIの入口で複数モデル/上流サーバを切り替える運用層
- **ONNX Runtime GenAI / OpenVINO GenAI / MLC LLM / MLX-LM**: オンデバイスや特定ハード（Intel/Apple/Web）に寄せる時の有力候補

各ランタイムにはそれぞれ強みがあり、用途・運用（同時接続/プロンプト再利用/デプロイ先）で選ぶのが重要です。まずは「どこで動かすか（ローカル/サーバ/デバイス）」と「OpenAI互換が必要か」を起点に絞り込むと迷いにくいです。

## 参考資料

- [vLLM Docs](https://docs.vllm.ai/)
- [OpenAI-Compatible Server（vLLM）](https://docs.vllm.ai/en/stable/serving/openai_compatible_server.html)
- [Automatic Prefix Caching（vLLM）](https://docs.vllm.ai/en/stable/design/prefix_caching/)
- [Structured Outputs（vLLM）](https://docs.vllm.ai/en/stable/features/structured_outputs.html)
- [llama.cpp（ggml-org）](https://github.com/ggml-org/llama.cpp)
- [GBNF（GGML BNF）: grammars/README.md](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md)
- [llama.cpp vs vllm performance comparison（Discussion #15180）](https://github.com/ggml-org/llama.cpp/discussions/15180)
- [LLM inference server performances comparison llama.cpp / TGI / vLLM（Discussion #6730）](https://github.com/ggml-org/llama.cpp/discussions/6730)
- [llama : add high-throughput mode（PR #14363）](https://github.com/ggml-org/llama.cpp/pull/14363)
- [Optimizing llama.cpp AI Inference with CUDA Graphs（NVIDIA）](https://developer.nvidia.com/blog/optimizing-llama-cpp-ai-inference-with-cuda-graphs/)
- [LLM-Inference-Bench（Argonne）](https://github.com/argonne-lcf/LLM-Inference-Bench)
- [LLM-Inference-Bench All_results.csv](https://raw.githubusercontent.com/argonne-lcf/LLM-Inference-Bench/main/Plots/All_results.csv)
- [SGLang Docs](https://sgl-project.github.io/)
- [Structured Outputs（SGLang）](https://sgl-project.github.io/advanced_features/structured_outputs.html)
- [TensorRT-LLM Docs](https://nvidia.github.io/TensorRT-LLM/)
- [TensorRT-LLM Backend（Triton）](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/tensorrtllm_backend/README.html)
- [TGI docs（maintenance modeの記載あり）](https://huggingface.co/docs/text-generation-inference/index)
- [onnxruntime-genai（GitHub）](https://github.com/microsoft/onnxruntime-genai)
- [OpenVINO GenAI](https://openvinotoolkit.github.io/openvino.genai/)
- [MLC LLM docs](https://llm.mlc.ai/docs/index.html)
- [mlx-lm（GitHub）](https://github.com/ml-explore/mlx-lm)
- [LMDeploy: OpenAI Compatible Server](https://lmdeploy.readthedocs.io/en/latest/llm/api_server.html)
- [TurboMind Architecture](https://lmdeploy.readthedocs.io/en/latest/inference/turbomind.html)
- [FlexGen（GitHub）](https://github.com/FMInference/FlexGen)
- [FlexGen（ICML 2023 / PMLR）](https://proceedings.mlr.press/v202/sheng23a.html)
- [Unsloth（GitHub）](https://github.com/unslothai/unsloth)
- [Unsloth Studio ドキュメント](https://unsloth.ai/docs/new/studio)
- [Unsloth Inference（Core）](https://unsloth.ai/docs/basics/inference-and-deployment/unsloth-inference)
- [Unsloth API エンドポイント](https://unsloth.ai/docs/basics/api)
- [Petals（GitHub）](https://github.com/bigscience-workshop/petals)
- [Petals公式サイト](https://petals.dev/)
- [Petals（arXiv）](https://arxiv.org/abs/2209.01188)
- [llama-swap（GitHub）](https://github.com/mostlygeek/llama-swap)
- [GenAI Performance Analyzer（Triton Docs）](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/perf_benchmark/genai_perf.html)
- [GenAI-Perf README（phased out / AIPerf推奨）](https://raw.githubusercontent.com/triton-inference-server/perf_analyzer/main/genai-perf/README.md)
- [AIPerf](https://github.com/ai-dynamo/aiperf)
- [NVIDIA NIM Docs](https://docs.nvidia.com/nim/index.html)
- [vLLM vs llama.cpp 徹底比較](https://zenn.dev/japan/articles/1b5acd1cee27b8)
- [NVIDIA TensorRT-LLM で大規模言語モデルの推論を最適化](https://developer.nvidia.com/ja-jp/blog/optimizing-inference-on-llms-with-tensorrt-llm-now-publicly-available/)
