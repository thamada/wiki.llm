#!/usr/bin/env python3
"""main.md の内容を要約した PPTX プレゼンを生成する."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


DEFAULT_MARKDOWN = Path("./main.md")
DEFAULT_OUTPUT = Path("./build/main.pptx")
DEFAULT_PDF_OUTPUT = Path("./build/main.pdf")

EMU_PER_INCH = 914400
SLIDE_W = 13.333333 * EMU_PER_INCH
SLIDE_H = 7.5 * EMU_PER_INCH

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


@dataclass(frozen=True)
class Slide:
    title: str
    bullets: tuple[str, ...]
    kicker: str = ""
    note: str = ""
    visual: str = "network"


def emu(inches: float) -> int:
    return int(inches * EMU_PER_INCH)


def clean_inline(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("`", "")
    text = re.sub(r"<br\s*/?>", " / ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_metadata(markdown: str) -> dict[str, str]:
    def find(pattern: str) -> str:
        match = re.search(pattern, markdown, re.MULTILINE | re.IGNORECASE)
        return clean_inline(match.group(1)) if match else ""

    return {
        "title": find(r"^#\s+(.+)$") or "AMD XDNAアーキテクチャ概要",
        "created": find(r"^作成日時:\s*(.+)$"),
        "updated": find(r"^更新日時:\s*(.+)$"),
        "author": find(r"^文責:\s*(.+)$"),
        "contact": find(r"^Contact\s*(?:email)?\s*:\s*(.+)$"),
    }


def build_slides(meta: dict[str, str]) -> list[Slide]:
    date_line = " / ".join(
        part for part in (f"作成: {meta['created']}", f"更新: {meta['updated']}") if part
    )
    author_line = " / ".join(part for part in (meta["author"], meta["contact"]) if part)

    return [
        Slide(
            title=meta["title"],
            kicker="技術概要サマリー",
            visual="hero",
            bullets=(
                "Xilinx Versal AI Engineを起源とする、クライアントAPU統合型NPU",
                "空間データフローにより、オンチップメモリとDMAでAI推論を低消費電力化",
                "XDNA 2はCopilot+ PC要件を満たす55 TOPS級へ進化",
            ),
            note=" / ".join(part for part in (date_line, author_line) if part),
        ),
        Slide(
            title="3行で要点",
            kicker="Executive Summary",
            visual="summary",
            bullets=(
                "XDNAは2D配列のAIEタイルが並列にデータを処理する空間データフロー型NPU",
                "世代ごとにタイル数・メモリ・データ型が拡張され、10 TOPSから55 TOPS級へ急伸",
                "NPU上のLLM推論はOnnxRuntime GenAIが担い、AI PC向けの中核技術になっている",
            ),
        ),
        Slide(
            title="技術的ルーツ",
            kicker="Xilinx AI Engine → AMD XDNA",
            visual="timeline",
            bullets=(
                "XilinxはFPGAの発明者で、Versal ACAPにAI Engineを搭載",
                "AMDは2022年にXilinxを約350億ドルで買収し、AIEをクライアントAPU向けに再設計",
                "DeePhi由来技術はVitis AIなどのソフトウェア層で活用され、XDNAハードウェアとは役割が異なる",
            ),
        ),
        Slide(
            title="設計思想: 空間データフロー",
            kicker="CPU/GPUとの違い",
            visual="dataflow",
            bullets=(
                "CPU/GPUはキャッシュ階層から動的にデータをフェッチするため、待ち時間と電力コストが発生",
                "XDNAはコンパイル時にデータ移動経路とタイミングを決め、DMAで決定論的に転送",
                "キャッシュミスを避け、AI推論に必要なデータをオンチップに局所化する",
            ),
        ),
        Slide(
            title="2Dタイルアレイが心臓部",
            kicker="Compute Tile + Memory Tile",
            visual="tile_array",
            bullets=(
                "Strix Point世代では4行×8列、合計32個の計算タイルを配置",
                "各列のメモリタイルがL2として働き、DDRとのステージングを担当",
                "専用DMAがホストメモリとタイルアレイ間のデータ転送を担う",
            ),
        ),
        Slide(
            title="AIE計算タイルの内部",
            kicker="小さな専用プロセッサの集合",
            visual="tile_core",
            bullets=(
                "ベクトルプロセッサはVLIW + SIMDでテンソル演算を並列実行",
                "スカラRISCプロセッサが制御フローやアドレス計算を担当",
                "命令メモリ・ローカルデータメモリ・タイル間インターコネクトを各タイルが持つ",
            ),
        ),
        Slide(
            title="GEMM実行イメージ",
            kicker="AI推論の主要ワークロード",
            visual="gemm",
            bullets=(
                "大きな行列を小さなブロックに分割し、複数タイルへ分散",
                "DMAがDDRからメモリタイル経由で計算タイルへデータを配送",
                "各タイルがFMAを実行し、部分積を受け渡しながら結果を蓄積・書き戻す",
            ),
        ),
        Slide(
            title="世代別の進化",
            kicker="10 TOPS → 55 TOPS",
            visual="bars",
            bullets=(
                "初代XDNA: Ryzen 7040、4×5タイル、最大10 TOPS",
                "Hawk Point: 同系統ハードウェアをファームウェア最適化し16 TOPSへ",
                "XDNA 2: Ryzen AI 300、4×8タイル、L2 60%増、BFP16対応、最大55 TOPS",
            ),
        ),
        Slide(
            title="XDNA 2の意味",
            kicker="Copilot+ PC世代のNPU",
            visual="copilot",
            bullets=(
                "MicrosoftのCopilot+ PC要件である40 TOPS以上を満たす",
                "NPU-only / Hybridモードにより、LLM推論をNPUまたはNPU+iGPUで実行",
                "Ryzen AI 300、Ryzen AI Max、Ryzen AI 400へ展開が広がる",
            ),
        ),
        Slide(
            title="BFP16という妥協点",
            kicker="INT8並の効率 + FP16に近い精度",
            visual="bfp16",
            bullets=(
                "BFP16は8要素で指数を共有し、各要素は符号1ビット + 仮数7ビットで保持",
                "1要素あたりの保存効率はINT8に近く、FP16よりメモリ帯域を抑えやすい",
                "ブロック内の値スケールが近い場合に精度劣化を抑えられる",
            ),
        ),
        Slide(
            title="ソフトウェアスタック",
            kicker="アプリからNPUまで",
            visual="stack",
            bullets=(
                "ONNX Runtime + Vitis AI EPがCNN/Transformer推論の主要経路",
                "OnnxRuntime GenAIがNPU上のLLM推論を担当",
                "AMD QuarkがFP32/FP16モデルをINT8・INT4・BFP16へ量子化",
                "Linuxではamdxdna.koがメインラインカーネルに統合済み",
            ),
        ),
        Slide(
            title="競合NPUとの比較軸",
            kicker="AMD / Intel / Qualcomm",
            visual="radar",
            bullets=(
                "AMD XDNA 2は55〜60 TOPS級で、空間データフロー型AIEタイル配列を採用",
                "Intel NPU 4は48 TOPS級で、ネイティブFP16対応が強み",
                "Qualcomm HexagonはArmプラットフォーム統合と高い総合AI性能を訴求",
            ),
        ),
        Slide(
            title="主な利用シーン",
            kicker="AI PCからエッジまで",
            visual="usecases",
            bullets=(
                "Copilot+ PC: Recall、Cocreator、Live Captions、Studio Effectsなど",
                "ローカルLLM推論: クラウドに接続せず省電力に推論",
                "エッジAI / 組み込み: 画像検査、ロボット、医療画像、小売認識など",
            ),
        ),
        Slide(
            title="専用NPUの将来論",
            kicker="GPU統合の可能性",
            visual="future",
            bullets=(
                "RDNA 5のNeural Arraysにより、GPU側のAI推論能力が強化される見込み",
                "ダイ面積・Copilot+ PC普及遅れ・iGPU性能向上がNPU廃止論の背景",
                "一方で、XDNAの電力効率と決定論的実行はGPUで容易に代替できない",
            ),
        ),
        Slide(
            title="まとめ",
            kicker="Takeaways",
            visual="takeaway",
            bullets=(
                "XDNAはXilinx由来の空間データフロー技術をPC向けに最適化したNPU",
                "2DタイルアレイとDMAベースのデータ移動により、低消費電力なAI推論を実現",
                "将来はGPU統合の可能性があるが、XDNAの技術的優位性は次世代にも残りうる",
            ),
        ),
    ]


def ns_attrs() -> str:
    return " ".join(f'xmlns:{prefix}="{uri}"' for prefix, uri in NS.items())


def text_run(text: str, size: int, color: str = "111827", bold: bool = False) -> str:
    b = ' b="1"' if bold else ""
    return (
        f'<a:r><a:rPr lang="ja-JP" sz="{size}"{b}>'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        '<a:latin typeface="Aptos"/><a:ea typeface="Yu Gothic"/></a:rPr>'
        f"<a:t>{escape(text)}</a:t></a:r>"
    )


def paragraph(text: str, size: int, color: str = "111827", bold: bool = False) -> str:
    return (
        '<a:p><a:pPr><a:buNone/></a:pPr>'
        f"{text_run(text, size, color, bold)}"
        '<a:endParaRPr lang="ja-JP"/></a:p>'
    )


def bullet_paragraph(text: str, size: int = 1700, color: str = "111827") -> str:
    return (
        '<a:p>'
        '<a:pPr marL="342900" indent="-228600">'
        '<a:lnSpc><a:spcPct val="140000"/></a:lnSpc>'
        '<a:spcBef><a:spcPts val="900"/></a:spcBef>'
        '<a:buClr><a:srgbClr val="1D4E89"/></a:buClr>'
        '<a:buFont typeface="Arial"/><a:buChar char="●"/>'
        '</a:pPr>'
        f"{text_run(text, size, color)}"
        '<a:endParaRPr lang="ja-JP"/></a:p>'
    )


def plain_paragraph(text: str, size: int, color: str = "111827", bold: bool = False, align: str = "l") -> str:
    return (
        '<a:p>'
        f'<a:pPr algn="{align}"><a:buNone/></a:pPr>'
        f"{text_run(text, size, color, bold)}"
        '<a:endParaRPr lang="ja-JP"/></a:p>'
    )


def solid_fill(color: str, alpha: int | None = None) -> str:
    alpha_xml = f'<a:alpha val="{alpha}"/>' if alpha is not None else ""
    return f'<a:solidFill><a:srgbClr val="{color}">{alpha_xml}</a:srgbClr></a:solidFill>'


def line_fill(color: str | None, width: int = 12700) -> str:
    if not color:
        return "<a:ln><a:noFill/></a:ln>"
    return f'<a:ln w="{width}">{solid_fill(color)}</a:ln>'


def shadow_xml() -> str:
    return (
        '<a:effectLst>'
        '<a:outerShdw blurRad="38100" dist="12700" dir="5400000" algn="ctr" rotWithShape="0">'
        '<a:srgbClr val="334155"><a:alpha val="14000"/></a:srgbClr>'
        "</a:outerShdw>"
        "</a:effectLst>"
    )


def shape(
    shape_id: int,
    name: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    fill: str,
    line: str | None = None,
    radius: str = "rect",
    alpha: int | None = None,
) -> str:
    return f"""
<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{shape_id}" name="{escape(name)}"/>
    <p:cNvSpPr/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
    <a:prstGeom prst="{radius}"><a:avLst/></a:prstGeom>
    {solid_fill(fill, alpha)}
    {line_fill(line)}
  </p:spPr>
</p:sp>"""


def textbox(
    shape_id: int,
    name: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    paragraphs_xml: str,
    fill: str | None = None,
    line: str | None = None,
    radius: str = "rect",
    shadow: bool = False,
) -> str:
    fill_xml = solid_fill(fill) if fill else "<a:noFill/>"
    line_xml = line_fill(line)
    effect_xml = shadow_xml() if shadow else ""
    return f"""
<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{shape_id}" name="{escape(name)}"/>
    <p:cNvSpPr txBox="1"/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
    <a:prstGeom prst="{radius}"><a:avLst/></a:prstGeom>
    {fill_xml}
    {line_xml}
    {effect_xml}
  </p:spPr>
  <p:txBody>
    <a:bodyPr wrap="square" lIns="120000" tIns="70000" rIns="120000" bIns="70000"/>
    <a:lstStyle/>
    {paragraphs_xml}
  </p:txBody>
</p:sp>"""


def academic_palette(index: int) -> tuple[str, str, str, str, str, str]:
    palettes = [
        ("FFFFFF", "F8FAFC", "1D4E89", "6B8E23", "E5E7EB", "111827"),
        ("FFFFFF", "F7F9FC", "2F5597", "8A5A44", "E2E8F0", "111827"),
        ("FFFFFF", "FAFAF7", "3B5B92", "7A6A53", "E7E5DF", "111827"),
        ("FFFFFF", "F8FAF9", "22577A", "4F6F52", "E2E8E5", "111827"),
    ]
    return palettes[index % len(palettes)]


def rule_line(
    shape_id: int,
    name: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    color: str,
    alpha: int = 100000,
) -> str:
    return shape(shape_id, name, x, y, cx, cy, color, alpha=alpha)


def label_box(
    shape_id: int,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    line: str,
    text_color: str = "111827",
    size: int = 1050,
    bold: bool = True,
) -> str:
    return textbox(
        shape_id,
        text,
        emu(x),
        emu(y),
        emu(w),
        emu(h),
        paragraph(text, size, text_color, bold),
        fill=fill,
        line=line,
        radius="roundRect",
        shadow=False,
    )


def metric_card(
    shape_id: int,
    label: str,
    value: str,
    x: float,
    y: float,
    w: float,
    h: float,
    panel: str,
    accent: str,
    text_color: str,
) -> str:
    return textbox(
        shape_id,
        label,
        emu(x),
        emu(y),
        emu(w),
        emu(h),
        paragraph(value, 1900, accent, True) + paragraph(label, 820, text_color),
        fill=panel,
        line=accent,
        radius="roundRect",
        shadow=False,
    )


FIG_X = 7.0
FIG_Y = 2.18
FIG_W = 5.95
FIG_H = 4.55
FIG_CONTENT_TOP = FIG_Y + 0.78
FIG_CONTENT_BOTTOM = FIG_Y + FIG_H - 0.22


def visual_frame(
    shape_id: int,
    title: str,
    panel: str,
    accent: str,
    accent2: str,
    text_color: str,
) -> str:
    return (
        shape(
            shape_id,
            "Figure Container",
            emu(FIG_X),
            emu(FIG_Y),
            emu(FIG_W),
            emu(FIG_H),
            "FFFFFF",
            line="E5E7EB",
            radius="roundRect",
        )
        + shape(
            shape_id + 1,
            "Figure Header",
            emu(FIG_X),
            emu(FIG_Y),
            emu(FIG_W),
            emu(0.52),
            "F8FAFC",
            line=None,
            radius="roundRect",
        )
        + textbox(
            shape_id + 2,
            "Figure Caption",
            emu(FIG_X + 0.22),
            emu(FIG_Y + 0.08),
            emu(FIG_W - 0.44),
            emu(0.4),
            plain_paragraph("図｜" + title, 1000, accent, True),
            fill=None,
            line=None,
        )
        + rule_line(
            shape_id + 3,
            "Figure Divider",
            emu(FIG_X + 0.05),
            emu(FIG_Y + 0.52),
            emu(FIG_W - 0.1),
            emu(0.012),
            accent,
            100000,
        )
    )


def fig_box(
    shape_id: int,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str | None,
    line: str | None,
    text_color: str = "111827",
    size: int = 1050,
    bold: bool = True,
    align: str = "ctr",
    subtitle: str | None = None,
    subtitle_color: str = "475569",
    subtitle_size: int = 850,
) -> str:
    body = plain_paragraph(text, size, text_color, bold, align)
    if subtitle:
        body += plain_paragraph(subtitle, subtitle_size, subtitle_color, False, align)
    return textbox(
        shape_id,
        text[:40] or "Figure Box",
        emu(x),
        emu(y),
        emu(w),
        emu(h),
        body,
        fill=fill,
        line=line,
        radius="roundRect",
        shadow=False,
    )


def fig_text(
    shape_id: int,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    color: str = "111827",
    size: int = 950,
    bold: bool = False,
    align: str = "l",
) -> str:
    return textbox(
        shape_id,
        "Figure Text",
        emu(x),
        emu(y),
        emu(w),
        emu(h),
        plain_paragraph(text, size, color, bold, align),
        fill=None,
        line=None,
    )


def fig_hbar(shape_id: int, x: float, y: float, length: float, color: str, thickness: float = 0.07) -> str:
    return shape(shape_id, "HBar", emu(x), emu(y), emu(length), emu(thickness), color, None, "rect")


def fig_vbar(shape_id: int, x: float, y: float, length: float, color: str, thickness: float = 0.07) -> str:
    return shape(shape_id, "VBar", emu(x), emu(y), emu(thickness), emu(length), color, None, "rect")


def draw_tile_array(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "XDNA 2 タイルアレイ（Strix Point: 4行×8列）", panel, accent, accent2, text_color)]
    sid = start_id + 10

    cell_w, cell_h, gap = 0.36, 0.30, 0.04
    base_x, base_y = 7.20, 2.95

    for row in range(4):
        for col in range(8):
            fill = "EFF6FF" if (row + col) % 2 == 0 else "DBEAFE"
            parts.append(
                shape(
                    sid,
                    "Compute Tile",
                    emu(base_x + col * (cell_w + gap)),
                    emu(base_y + row * (cell_h + gap)),
                    emu(cell_w),
                    emu(cell_h),
                    fill,
                    accent2,
                    "roundRect",
                )
            )
            sid += 1

    mem_y = base_y + 4 * (cell_h + gap) + 0.12
    for col in range(8):
        parts.append(
            shape(
                sid,
                "Memory Tile",
                emu(base_x + col * (cell_w + gap)),
                emu(mem_y),
                emu(cell_w),
                emu(cell_h),
                "DCFCE7",
                accent,
                "roundRect",
            )
        )
        sid += 1

    bus_y = mem_y + cell_h + 0.12
    bus_w = 8 * cell_w + 7 * gap
    parts.append(shape(sid, "DMA Bus", emu(base_x), emu(bus_y), emu(bus_w), emu(0.10), accent, None, "rect"))
    sid += 1

    ddr_y = bus_y + 0.22
    parts.append(
        fig_box(sid, "DDR メインメモリ", base_x, ddr_y, bus_w, 0.4, "F1F5F9", accent, text_color, 1000, True)
    )
    sid += 1

    lx = base_x + bus_w + 0.18
    parts.append(fig_box(sid, "計算タイル ×32", lx, base_y - 0.05, 1.95, 0.4, "EFF6FF", accent2, text_color, 980, True))
    sid += 1
    parts.append(fig_text(sid, "VLIW + SIMD", lx, base_y + 0.4, 1.95, 0.3, "475569", 850, False, "l"))
    sid += 1
    parts.append(fig_box(sid, "メモリタイル ×8", lx, mem_y - 0.05, 1.95, 0.4, "DCFCE7", accent, text_color, 980, True))
    sid += 1
    parts.append(fig_text(sid, "L2 / DDR との橋渡し", lx, mem_y + 0.4, 1.95, 0.3, "475569", 850, False, "l"))
    sid += 1
    parts.append(fig_box(sid, "DMA バス ×8", lx, bus_y - 0.12, 1.95, 0.4, "FFFFFF", accent, accent, 980, True))
    sid += 1
    parts.append(fig_text(sid, "DDR ↔ メモリタイル", lx, bus_y + 0.27, 1.95, 0.3, "475569", 850, False, "l"))
    sid += 1

    return "".join(parts)


def draw_tile_core(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "AIE 計算タイル 1個の内部構成", panel, accent, accent2, text_color)]
    sid = start_id + 10

    parts.append(
        fig_box(
            sid,
            "ベクトルプロセッサ",
            7.2,
            3.0,
            3.55,
            1.0,
            "EFF6FF",
            accent,
            text_color,
            1200,
            True,
            "ctr",
            subtitle="VLIW + SIMD ・1.3 GHz以上",
            subtitle_color="475569",
            subtitle_size=850,
        )
    )
    sid += 1
    parts.append(
        fig_box(
            sid,
            "スカラ RISC",
            10.9,
            3.0,
            2.0,
            1.0,
            "DBEAFE",
            accent2,
            text_color,
            1150,
            True,
            "ctr",
            subtitle="制御フロー・アドレス",
            subtitle_size=820,
        )
    )
    sid += 1
    parts.append(
        fig_box(
            sid,
            "命令メモリ",
            7.2,
            4.2,
            2.6,
            0.85,
            "FFFFFF",
            "94A3B8",
            text_color,
            1050,
            True,
            "ctr",
            subtitle="Program Memory",
            subtitle_size=780,
        )
    )
    sid += 1
    parts.append(
        fig_box(
            sid,
            "ローカルデータメモリ",
            9.95,
            4.2,
            2.95,
            0.85,
            "FFFFFF",
            "94A3B8",
            text_color,
            1050,
            True,
            "ctr",
            subtitle="重み・活性化値・係数",
            subtitle_size=780,
        )
    )
    sid += 1
    parts.append(
        fig_box(
            sid,
            "インターコネクト（隣接タイル ↔ メモリタイル）",
            7.2,
            5.2,
            5.7,
            0.7,
            "DCFCE7",
            accent,
            text_color,
            1050,
            True,
            "ctr",
            subtitle="高帯域・低遅延 / プログラマブル DMA",
            subtitle_size=820,
        )
    )
    sid += 1

    return "".join(parts)


def draw_gemm(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "GEMM（行列積）の実行フロー", panel, accent, accent2, text_color)]
    sid = start_id + 10

    parts.append(fig_box(sid, "行列 A", 7.2, 3.0, 1.05, 0.65, "EFF6FF", accent, text_color, 1100, True))
    sid += 1
    parts.append(fig_box(sid, "行列 B", 7.2, 3.85, 1.05, 0.65, "DBEAFE", accent2, text_color, 1100, True))
    sid += 1
    parts.append(fig_hbar(sid, 8.30, 3.62, 0.45, accent))
    sid += 1
    for i in range(3):
        parts.append(
            fig_box(
                sid,
                f"Tile {i + 1}",
                8.85 + i * 0.78,
                3.18,
                0.72,
                1.1,
                "FFFFFF",
                accent,
                text_color,
                1000,
                True,
                "ctr",
                subtitle="FMA",
                subtitle_size=780,
            )
        )
        sid += 1
    parts.append(fig_hbar(sid, 11.32, 3.62, 0.42, accent))
    sid += 1
    parts.append(fig_box(sid, "行列 C", 11.78, 3.3, 1.05, 0.65, "DCFCE7", accent, text_color, 1100, True))
    sid += 1

    steps = ["1. タイリング", "2. DMA転送", "3. FMA演算", "4. 部分積蓄積", "5. 書き戻し"]
    step_w = 1.13
    base_x = 7.2
    for i, step in enumerate(steps):
        parts.append(
            fig_box(
                sid,
                step,
                base_x + i * (step_w + 0.02),
                5.2,
                step_w,
                0.5,
                "F8FAFC",
                "CBD5E1",
                text_color,
                880,
                True,
            )
        )
        sid += 1

    return "".join(parts)


def draw_dataflow(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "CPU/GPU と XDNA のデータ移動の違い", panel, accent, accent2, text_color)]
    sid = start_id + 10

    parts.append(
        fig_text(sid, "CPU / GPU — キャッシュ階層から要求時フェッチ", 7.2, 3.0, 5.7, 0.32, "475569", 950, True)
    )
    sid += 1

    cpu_labels = ["演算器", "L1$", "L2$", "L3$", "DRAM"]
    box_w = 1.02
    box_h = 0.55
    gap_x = 0.1
    for i, label in enumerate(cpu_labels):
        x = 7.2 + i * (box_w + gap_x)
        parts.append(fig_box(sid, label, x, 3.4, box_w, box_h, "FFFFFF", "CBD5E1", text_color, 980, True))
        sid += 1
        if i < len(cpu_labels) - 1:
            parts.append(fig_hbar(sid, x + box_w + 0.005, 3.4 + box_h / 2 - 0.025, gap_x - 0.01, "94A3B8", 0.05))
            sid += 1

    parts.append(fig_text(sid, "キャッシュミス時に待ち時間とエネルギーを消費", 7.2, 4.05, 5.7, 0.3, "94A3B8", 800, False))
    sid += 1

    parts.append(rule_line(sid, "Section Rule", emu(7.2), emu(4.42), emu(5.7), emu(0.012), "E5E7EB", 100000))
    sid += 1

    parts.append(
        fig_text(sid, "XDNA — コンパイル時スケジュール / DMA で決定論的に転送", 7.2, 4.6, 5.7, 0.32, accent, 950, True)
    )
    sid += 1

    xdna_labels = ["DDR", "DMA", "メモリ\nタイル", "計算\nタイル", "計算\nタイル"]
    for i, label in enumerate(xdna_labels):
        x = 7.2 + i * (box_w + gap_x)
        clean = label.replace("\n", " ")
        parts.append(fig_box(sid, clean, x, 5.0, box_w, box_h, "EFF6FF", accent, text_color, 980, True))
        sid += 1
        if i < len(xdna_labels) - 1:
            parts.append(fig_hbar(sid, x + box_w + 0.005, 5.0 + box_h / 2 - 0.03, gap_x - 0.01, accent, 0.06))
            sid += 1

    parts.append(fig_text(sid, "実行中のキャッシュミスがなく、低消費電力", 7.2, 5.65, 5.7, 0.3, accent, 800, False))
    sid += 1

    return "".join(parts)


def draw_bars(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "世代別ピーク性能（INT8 TOPS）", panel, accent, accent2, text_color)]
    sid = start_id + 10

    data = [
        ("Phoenix", 10, "XDNA 1 / 2023", accent2),
        ("Hawk Point", 16, "XDNA 1 / 2024", accent2),
        ("Strix Point", 55, "XDNA 2 / 2024", accent),
    ]
    max_v = 60
    bar_left = 9.5
    bar_max_w = 2.4

    for i, (label, value, year, color) in enumerate(data):
        y = 3.1 + i * 0.78
        parts.append(fig_text(sid, label, 7.2, y, 2.25, 0.34, text_color, 950, True))
        sid += 1
        parts.append(fig_text(sid, year, 7.2, y + 0.32, 2.25, 0.28, "94A3B8", 780, False))
        sid += 1
        parts.append(shape(sid, "Bar BG", emu(bar_left), emu(y + 0.05), emu(bar_max_w), emu(0.32), "E5E7EB", None, "rect"))
        sid += 1
        parts.append(
            shape(
                sid,
                "Bar Value",
                emu(bar_left),
                emu(y + 0.05),
                emu(bar_max_w * value / max_v),
                emu(0.32),
                color,
                None,
                "rect",
            )
        )
        sid += 1
        parts.append(fig_text(sid, f"{value} TOPS", bar_left + bar_max_w + 0.05, y + 0.04, 0.95, 0.34, color, 1050, True))
        sid += 1

    threshold_x = bar_left + bar_max_w * 40 / max_v
    parts.append(fig_vbar(sid, threshold_x, 3.05, 2.2, "DC2626", 0.022))
    sid += 1
    parts.append(fig_text(sid, "Copilot+ PC 要件 = 40 TOPS", threshold_x - 1.05, 5.35, 2.2, 0.3, "DC2626", 820, True))
    sid += 1

    return "".join(parts)


def draw_copilot(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "OGA による NPU 実行モード", panel, accent, accent2, text_color)]
    sid = start_id + 10

    parts.append(
        fig_box(
            sid,
            "アプリ",
            8.4,
            3.0,
            3.2,
            0.62,
            "F1F5F9",
            "CBD5E1",
            text_color,
            1050,
            True,
            "ctr",
            subtitle="Copilot+ / LM Studio / 独自",
            subtitle_size=800,
        )
    )
    sid += 1
    parts.append(fig_vbar(sid, 9.97, 3.65, 0.3, accent, 0.06))
    sid += 1
    parts.append(
        fig_box(
            sid,
            "OnnxRuntime GenAI (OGA)",
            8.4,
            4.0,
            3.2,
            0.62,
            "EFF6FF",
            accent,
            text_color,
            1050,
            True,
            "ctr",
        )
    )
    sid += 1
    parts.append(fig_hbar(sid, 8.05, 4.78, 3.9, accent, 0.05))
    sid += 1
    parts.append(fig_vbar(sid, 8.05, 4.78, 0.35, accent, 0.05))
    sid += 1
    parts.append(fig_vbar(sid, 11.92, 4.78, 0.35, accent, 0.05))
    sid += 1
    parts.append(
        fig_box(
            sid,
            "NPU-only",
            7.2,
            5.18,
            2.4,
            0.85,
            "DCFCE7",
            accent,
            text_color,
            1100,
            True,
            "ctr",
            subtitle="NPU 専用・iGPU を解放",
            subtitle_size=800,
        )
    )
    sid += 1
    parts.append(
        fig_box(
            sid,
            "Hybrid",
            10.4,
            5.18,
            2.4,
            0.85,
            "FEF3C7",
            accent2,
            text_color,
            1100,
            True,
            "ctr",
            subtitle="NPU + iGPU を動的分担",
            subtitle_size=800,
        )
    )
    sid += 1

    return "".join(parts)


def draw_stack(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "Ryzen AI ソフトウェアスタック", panel, accent, accent2, text_color)]
    sid = start_id + 10

    layers = [
        ("アプリ", "Copilot+ / LM Studio / 独自アプリ", "F1F5F9", "CBD5E1"),
        ("フレームワーク", "ONNX Runtime + Vitis AI EP / OGA / Lemonade", "EFF6FF", accent2),
        ("量子化", "AMD Quark（INT8 / INT4 / BFP16）", "DBEAFE", accent),
        ("ドライバ / ランタイム", "amdxdna.ko / XRT SHIM", "EFF6FF", accent2),
        ("ハードウェア", "AMD XDNA NPU（AIE タイルアレイ）", "DCFCE7", accent),
    ]

    layer_h = 0.6
    layer_y0 = 3.0

    for i, (head, body, fill, line) in enumerate(layers):
        y = layer_y0 + i * (layer_h + 0.07)
        parts.append(
            fig_box(
                sid,
                head,
                7.2,
                y,
                5.7,
                layer_h,
                fill,
                line,
                text_color,
                1050,
                True,
                "l",
                subtitle=body,
                subtitle_size=820,
            )
        )
        sid += 1

    return "".join(parts)


def draw_comparison(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "クライアント向け NPU の比較（2026年）", panel, accent, accent2, text_color)]
    sid = start_id + 10

    headers = [("ベンダー", 1.45), ("TOPS", 1.0), ("アーキ", 1.55), ("精度", 1.7)]
    rows = [
        ("AMD XDNA 2", "55–60", "AIE 配列", "INT8 / BFP16"),
        ("Intel NPU 4", "48", "MAC 配列", "INT8 / FP16"),
        ("Qualcomm Hexagon", "45–85", "Hexagon DSP", "INT8 / INT4"),
    ]

    base_x = 7.2
    base_y = 3.0
    row_h = 0.55

    x = base_x
    for i, (h, w) in enumerate(headers):
        parts.append(fig_box(sid, h, x, base_y, w, 0.46, "F1F5F9", "CBD5E1", "475569", 950, True, "ctr"))
        sid += 1
        x += w

    for r, row in enumerate(rows):
        x = base_x
        y = base_y + 0.46 + r * row_h
        emphasis = r == 0
        for c, value in enumerate(row):
            w = headers[c][1]
            fill = "EFF6FF" if emphasis else "FFFFFF"
            line = accent if emphasis else "CBD5E1"
            color = accent if emphasis and c == 0 else text_color
            size = 1000 if c == 0 else 920
            parts.append(fig_box(sid, value, x, y, w, row_h, fill, line, color, size, c == 0, "ctr"))
            sid += 1
            x += w

    return "".join(parts)


def draw_cards(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "XDNA を 4 つのキーワードで掴む", panel, accent, accent2, text_color)]
    sid = start_id + 10

    items = [
        ("起源", "Xilinx Versal AI Engine", accent),
        ("設計", "空間データフロー (AIE + DMA)", accent2),
        ("到達", "XDNA 2 で 55 TOPS", accent),
        ("用途", "Copilot+ PC / ローカル LLM", accent2),
    ]

    base_y = 3.0
    card_h = 0.78
    card_w = 5.7

    for i, (head, body, color) in enumerate(items):
        y = base_y + i * (card_h + 0.1)
        parts.append(
            textbox(
                sid,
                head,
                emu(7.2),
                emu(y),
                emu(card_w),
                emu(card_h),
                plain_paragraph(head, 1050, color, True)
                + plain_paragraph(body, 1000, text_color, False),
                fill="F8FAFC",
                line="CBD5E1",
                radius="roundRect",
                shadow=False,
            )
        )
        sid += 1

    return "".join(parts)


def draw_summary(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "本資料の論点（3行で要点）", panel, accent, accent2, text_color)]
    sid = start_id + 10

    items = [
        ("01", "空間データフロー型 NPU", "AIE タイルが並列にデータ処理"),
        ("02", "10 → 55 TOPS の急進化", "世代ごとにタイル数とデータ型を拡張"),
        ("03", "AI PC の中核技術", "OGA でローカル LLM 推論を実用化"),
    ]

    base_y = 3.0
    card_h = 1.0

    for i, (num, head, body) in enumerate(items):
        y = base_y + i * (card_h + 0.18)
        parts.append(
            textbox(
                sid,
                f"Num {i}",
                emu(7.2),
                emu(y + 0.1),
                emu(0.85),
                emu(0.8),
                plain_paragraph(num, 1800, "FFFFFF", True, "ctr"),
                fill=accent if i == 0 else accent2,
                line=None,
                radius="ellipse",
                shadow=False,
            )
        )
        sid += 1
        parts.append(
            textbox(
                sid,
                f"Card {i}",
                emu(8.2),
                emu(y),
                emu(4.65),
                emu(card_h),
                plain_paragraph(head, 1150, text_color, True)
                + plain_paragraph(body, 900, "475569", False),
                fill="F8FAFC",
                line="CBD5E1",
                radius="roundRect",
                shadow=False,
            )
        )
        sid += 1

    return "".join(parts)


def draw_timeline(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "Xilinx から AMD XDNA への系譜", panel, accent, accent2, text_color)]
    sid = start_id + 10

    events = [
        ("1984", "Xilinx 創業", "FPGA を発明"),
        ("2019", "Versal ACAP", "AI Engine 搭載"),
        ("2022", "AMD が買収", "約 350 億ドル"),
        ("2023", "XDNA 初代", "Ryzen 7040"),
    ]

    line_y = 4.5
    xs = [7.55, 9.13, 10.7, 12.28]

    parts.append(shape(sid, "Timeline", emu(7.4), emu(line_y), emu(5.05), emu(0.045), accent, None, "rect"))
    sid += 1

    for i, (year, head, body) in enumerate(events):
        x = xs[i]
        parts.append(
            shape(
                sid,
                f"Node {i}",
                emu(x - 0.12),
                emu(line_y - 0.09),
                emu(0.24),
                emu(0.24),
                accent if i == 3 else accent2,
                radius="ellipse",
            )
        )
        sid += 1
        parts.append(
            fig_text(sid, year, x - 0.55, line_y - 0.7, 1.1, 0.34, accent if i == 3 else text_color, 1100, True, "ctr")
        )
        sid += 1
        parts.append(fig_text(sid, head, x - 0.85, line_y + 0.18, 1.7, 0.34, text_color, 920, True, "ctr"))
        sid += 1
        parts.append(fig_text(sid, body, x - 0.85, line_y + 0.5, 1.7, 0.3, "475569", 800, False, "ctr"))
        sid += 1

    return "".join(parts)


def draw_bfp16(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "BFP16 — ブロック共有指数の仕組み", panel, accent, accent2, text_color)]
    sid = start_id + 10

    parts.append(fig_text(sid, "通常の FP16（要素ごと独立、各 16 bit）", 7.2, 3.0, 5.7, 0.32, "475569", 920, True))
    sid += 1
    fp16_y = 3.4
    for i in range(3):
        x = 7.25 + i * 1.85
        parts.append(shape(sid, "FP16 Sign", emu(x), emu(fp16_y), emu(0.18), emu(0.45), "F1F5F9", "CBD5E1", "rect"))
        sid += 1
        parts.append(shape(sid, "FP16 Exp", emu(x + 0.18), emu(fp16_y), emu(0.55), emu(0.45), "FED7AA", accent2, "rect"))
        sid += 1
        parts.append(shape(sid, "FP16 Mant", emu(x + 0.73), emu(fp16_y), emu(0.95), emu(0.45), "DBEAFE", accent, "rect"))
        sid += 1
        if i == 0:
            parts.append(fig_text(sid, "符号", x, fp16_y + 0.5, 0.18, 0.24, "475569", 700, False, "ctr"))
            sid += 1
            parts.append(fig_text(sid, "指数 5b", x + 0.18, fp16_y + 0.5, 0.55, 0.24, accent2, 720, True, "ctr"))
            sid += 1
            parts.append(fig_text(sid, "仮数 10b", x + 0.73, fp16_y + 0.5, 0.95, 0.24, accent, 720, True, "ctr"))
            sid += 1

    parts.append(rule_line(sid, "Section", emu(7.2), emu(4.45), emu(5.7), emu(0.012), "E5E7EB", 100000))
    sid += 1

    parts.append(fig_text(sid, "BFP16（8 要素で指数を共有、72 bit / 8 要素 = 9 bit / 要素）", 7.2, 4.6, 5.7, 0.32, accent, 920, True))
    sid += 1

    bfp_y = 5.0
    parts.append(shape(sid, "Shared Exp", emu(7.2), emu(bfp_y), emu(0.95), emu(0.6), "FED7AA", accent2, "roundRect"))
    sid += 1
    parts.append(fig_text(sid, "共有指数", 7.2, bfp_y + 0.08, 0.95, 0.24, text_color, 780, True, "ctr"))
    sid += 1
    parts.append(fig_text(sid, "8 bit", 7.2, bfp_y + 0.3, 0.95, 0.22, "475569", 720, False, "ctr"))
    sid += 1

    for i in range(8):
        x = 8.25 + i * 0.43
        parts.append(shape(sid, f"BFP Mant {i}", emu(x), emu(bfp_y), emu(0.4), emu(0.6), "DBEAFE", accent, "roundRect"))
        sid += 1
        parts.append(fig_text(sid, f"E{i + 1}", x, bfp_y + 0.18, 0.4, 0.28, text_color, 720, True, "ctr"))
        sid += 1

    parts.append(fig_text(sid, "各要素 = 符号 1 + 仮数 7 bit（INT8 並のメモリ効率）", 7.2, 5.7, 5.7, 0.3, "475569", 820, False))
    sid += 1

    return "".join(parts)


def draw_usecases(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "AMD XDNA の主な利用シーン", panel, accent, accent2, text_color)]
    sid = start_id + 10

    cases = [
        ("Copilot+ PC", ("Windows Recall", "Cocreator", "Live Captions", "Studio Effects"), accent, "FFFFFF"),
        ("ローカル LLM", ("OGA NPU-only", "Hybrid モード", "LM Studio 連携", "省電力推論"), accent2, "FFFFFF"),
        ("エッジ AI", ("産業画像検査", "ロボット推論", "医療画像前処理", "小売認識"), "8A5A44", "FFFFFF"),
    ]

    base_y = 3.0
    card_w = 1.84
    gap = 0.08
    card_h = 2.55

    for i, (head, body_lines, color, head_text_color) in enumerate(cases):
        x = 7.2 + i * (card_w + gap)
        parts.append(
            textbox(
                sid,
                f"Head {i}",
                emu(x),
                emu(base_y),
                emu(card_w),
                emu(0.5),
                plain_paragraph(head, 1100, head_text_color, True, "ctr"),
                fill=color,
                line=None,
                radius="roundRect",
                shadow=False,
            )
        )
        sid += 1
        body_xml = "".join(plain_paragraph("・ " + line, 900, text_color, False) for line in body_lines)
        parts.append(
            textbox(
                sid,
                f"Body {i}",
                emu(x),
                emu(base_y + 0.55),
                emu(card_w),
                emu(card_h - 0.55),
                body_xml,
                fill="F8FAFC",
                line="CBD5E1",
                radius="roundRect",
                shadow=False,
            )
        )
        sid += 1

    return "".join(parts)


def draw_future(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "NPU 専用 vs GPU 統合 — 将来の分岐点", panel, accent, accent2, text_color)]
    sid = start_id + 10

    parts.append(
        fig_box(
            sid,
            "クライアントAI推論",
            8.7,
            3.0,
            2.55,
            0.7,
            "F1F5F9",
            "CBD5E1",
            text_color,
            1150,
            True,
            "ctr",
            subtitle="Copilot+ / ローカル LLM 等",
            subtitle_size=800,
        )
    )
    sid += 1

    parts.append(fig_vbar(sid, 9.96, 3.7, 0.3, accent, 0.06))
    sid += 1
    parts.append(fig_hbar(sid, 8.1, 3.98, 3.85, accent, 0.06))
    sid += 1
    parts.append(fig_vbar(sid, 8.1, 3.98, 0.32, accent, 0.06))
    sid += 1
    parts.append(fig_vbar(sid, 11.9, 3.98, 0.32, accent, 0.06))
    sid += 1

    parts.append(
        textbox(
            sid,
            "NPU",
            emu(7.2),
            emu(4.35),
            emu(2.78),
            emu(0.55),
            plain_paragraph("専用 NPU 継続", 1050, "FFFFFF", True, "ctr"),
            fill=accent2,
            line=None,
            radius="roundRect",
            shadow=False,
        )
    )
    sid += 1
    parts.append(
        textbox(
            sid,
            "NPU body",
            emu(7.2),
            emu(4.95),
            emu(2.78),
            emu(1.3),
            plain_paragraph("◯ 高い perf / watt", 920, text_color, False)
            + plain_paragraph("◯ 決定論的レイテンシ", 920, text_color, False)
            + plain_paragraph("× 専用ダイ面積を要求", 920, "475569", False),
            fill="F8FAFC",
            line=accent2,
            radius="roundRect",
            shadow=False,
        )
    )
    sid += 1

    parts.append(
        textbox(
            sid,
            "GPU",
            emu(10.05),
            emu(4.35),
            emu(2.85),
            emu(0.55),
            plain_paragraph("GPU 統合", 1050, "FFFFFF", True, "ctr"),
            fill=accent,
            line=None,
            radius="roundRect",
            shadow=False,
        )
    )
    sid += 1
    parts.append(
        textbox(
            sid,
            "GPU body",
            emu(10.05),
            emu(4.95),
            emu(2.85),
            emu(1.3),
            plain_paragraph("◯ ダイ面積を共用可", 920, text_color, False)
            + plain_paragraph("◯ RDNA 5 Neural Arrays", 920, text_color, False)
            + plain_paragraph("× AI 専用の電力効率↓", 920, "475569", False),
            fill="F8FAFC",
            line=accent,
            radius="roundRect",
            shadow=False,
        )
    )
    sid += 1

    return "".join(parts)


def draw_takeaway(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    parts = [visual_frame(start_id, "本資料の Takeaway", panel, accent, accent2, text_color)]
    sid = start_id + 10

    items = [
        ("空間データフロー", "AIE タイルが DMA で協調する低消費電力 NPU", accent),
        ("急速な世代進化", "10 → 16 → 55 TOPS / BFP16 / 32 タイル", accent2),
        ("将来は不透明", "GPU 統合に伴う NPU 単独運用の存続性が論点", accent),
    ]

    base_y = 3.0
    card_h = 1.0

    for i, (head, body, color) in enumerate(items):
        y = base_y + i * (card_h + 0.15)
        parts.append(
            textbox(
                sid,
                f"Card {i}",
                emu(7.2),
                emu(y),
                emu(5.7),
                emu(card_h),
                plain_paragraph(head, 1200, color, True)
                + plain_paragraph(body, 950, text_color, False),
                fill="F8FAFC",
                line="CBD5E1",
                radius="roundRect",
                shadow=False,
            )
        )
        sid += 1

    return "".join(parts)


def draw_network(start_id: int, accent: str, accent2: str, panel: str, text_color: str) -> str:
    return draw_cards(start_id, accent, accent2, panel, text_color)


def draw_visual(slide: Slide, index: int, panel: str, accent: str, accent2: str, text_color: str) -> str:
    if slide.visual == "tile_array":
        return draw_tile_array(40, accent, accent2, panel, text_color)
    if slide.visual == "tile_core":
        return draw_tile_core(40, accent, accent2, panel, text_color)
    if slide.visual == "gemm":
        return draw_gemm(40, accent, accent2, panel, text_color)
    if slide.visual == "dataflow":
        return draw_dataflow(40, accent, accent2, panel, text_color)
    if slide.visual == "copilot":
        return draw_copilot(40, accent, accent2, panel, text_color)
    if slide.visual == "future":
        return draw_future(40, accent, accent2, panel, text_color)
    if slide.visual == "takeaway":
        return draw_takeaway(40, accent, accent2, panel, text_color)
    if slide.visual == "bars":
        return draw_bars(40, accent, accent2, panel, text_color)
    if slide.visual == "stack":
        return draw_stack(40, accent, accent2, panel, text_color)
    if slide.visual == "radar":
        return draw_comparison(40, accent, accent2, panel, text_color)
    if slide.visual == "timeline":
        return draw_timeline(40, accent, accent2, panel, text_color)
    if slide.visual == "bfp16":
        return draw_bfp16(40, accent, accent2, panel, text_color)
    if slide.visual == "summary":
        return draw_summary(40, accent, accent2, panel, text_color)
    if slide.visual == "usecases":
        return draw_usecases(40, accent, accent2, panel, text_color)
    if slide.visual == "hero":
        return draw_cards(40, accent, accent2, panel, text_color)
    return draw_network(40, accent, accent2, panel, text_color)


SLIDE_COUNT_PLACEHOLDER = "{slide_count}"


def slide_xml(slide: Slide, index: int, slide_count: int) -> str:
    _, _, accent_color, accent2_color, _, text_color = academic_palette(index)

    background = shape(2, "Background", 0, 0, int(SLIDE_W), int(SLIDE_H), "FFFFFF")
    top_bar = shape(3, "Top Bar", 0, 0, int(SLIDE_W), emu(0.16), accent_color)

    title_size = 4000 if not index else 3200
    kicker_xml = plain_paragraph(slide.kicker, 1250, accent_color, True) if slide.kicker else ""
    title_xml = plain_paragraph(slide.title, title_size, text_color, True)
    header = textbox(
        6,
        "Title",
        emu(0.6),
        emu(0.45),
        emu(10.5),
        emu(1.45),
        kicker_xml + title_xml,
        fill=None,
        line=None,
    )

    index_chip = textbox(
        8,
        "Section Chip",
        emu(11.75),
        emu(0.65),
        emu(1.0),
        emu(0.6),
        plain_paragraph(f"{index + 1:02d}", 1900, accent_color, True, "ctr"),
        fill="FFFFFF",
        line=accent_color,
        radius="roundRect",
        shadow=False,
    )

    divider = rule_line(11, "Header Divider", emu(0.6), emu(1.96), emu(12.15), emu(0.014), accent_color, 100000)

    bullet_xml = "".join(bullet_paragraph(b, color=text_color) for b in slide.bullets)
    content = textbox(
        7,
        "Bullets",
        emu(0.6),
        emu(2.18),
        emu(6.2),
        emu(4.6),
        bullet_xml,
        fill=None,
        line=None,
    )

    visual = draw_visual(slide, index, "FFFFFF", accent_color, accent2_color, text_color)

    footer_rule = rule_line(13, "Footer Rule", emu(0.6), emu(6.92), emu(12.15), emu(0.01), "E5E7EB", 100000)
    footer_text = slide.note or "AMD XDNA アーキテクチャ概要"
    footer = textbox(
        9,
        "Footer",
        emu(0.6),
        emu(7.0),
        emu(10.4),
        emu(0.3),
        plain_paragraph(footer_text, 820, "64748B"),
        fill=None,
        line=None,
    )

    slide_no = textbox(
        10,
        "Slide Number",
        emu(11.4),
        emu(7.0),
        emu(1.35),
        emu(0.3),
        plain_paragraph(f"{index + 1} / {slide_count}", 820, "94A3B8", False, "r"),
        fill=None,
        line=None,
    )

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld {ns_attrs()}>
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm>
          <a:off x="0" y="0"/><a:ext cx="0" cy="0"/>
          <a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/>
        </a:xfrm>
      </p:grpSpPr>
      {background}
      {top_bar}
      {header}
      {index_chip}
      {divider}
      {content}
      {visual}
      {footer_rule}
      {footer}
      {slide_no}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def content_types(slide_count: int) -> str:
    slide_overrides = "\n".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>
  <Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>
  <Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  {slide_overrides}
</Types>"""


def package_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def presentation_xml(slide_count: int) -> str:
    slide_ids = "\n".join(
        f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, slide_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation {ns_attrs()}>
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="{int(SLIDE_W)}" cy="{int(SLIDE_H)}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
  <p:defaultTextStyle>
    <a:defPPr><a:defRPr lang="ja-JP"><a:latin typeface="Aptos"/><a:ea typeface="Yu Gothic"/></a:defRPr></a:defPPr>
  </p:defaultTextStyle>
</p:presentation>"""


def presentation_rels(slide_count: int) -> str:
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    ]
    rels.extend(
        f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, slide_count + 1)
    )
    base = slide_count + 2
    rels.extend(
        [
            f'<Relationship Id="rId{base}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps" Target="presProps.xml"/>',
            f'<Relationship Id="rId{base + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps" Target="viewProps.xml"/>',
            f'<Relationship Id="rId{base + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles" Target="tableStyles.xml"/>',
        ]
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        + "\n".join(f"  {rel}" for rel in rels)
        + "\n</Relationships>"
    )


def slide_master_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster {ns_attrs()}>
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm>
      </p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles>
    <p:titleStyle/><p:bodyStyle/><p:otherStyle/>
  </p:txStyles>
</p:sldMaster>"""


def slide_master_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""


def slide_layout_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout {ns_attrs()} type="blank" preserve="1">
  <p:cSld name="Blank">
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm>
      </p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""


def slide_layout_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""


def theme_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="XDNA Academic">
  <a:themeElements>
    <a:clrScheme name="XDNA Academic">
      <a:dk1><a:srgbClr val="111827"/></a:dk1>
      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="1D4E89"/></a:dk2>
      <a:lt2><a:srgbClr val="F8FAFC"/></a:lt2>
      <a:accent1><a:srgbClr val="1D4E89"/></a:accent1>
      <a:accent2><a:srgbClr val="6B8E23"/></a:accent2>
      <a:accent3><a:srgbClr val="8A5A44"/></a:accent3>
      <a:accent4><a:srgbClr val="64748B"/></a:accent4>
      <a:accent5><a:srgbClr val="CBD5E1"/></a:accent5>
      <a:accent6><a:srgbClr val="334155"/></a:accent6>
      <a:hlink><a:srgbClr val="1D4E89"/></a:hlink>
      <a:folHlink><a:srgbClr val="6B8E23"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="XDNA Fonts">
      <a:majorFont><a:latin typeface="Aptos Display"/><a:ea typeface="Yu Gothic"/></a:majorFont>
      <a:minorFont><a:latin typeface="Aptos"/><a:ea typeface="Yu Gothic"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="XDNA Format">
      <a:fillStyleLst><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:fillStyleLst>
      <a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:ln></a:lnStyleLst>
      <a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
      <a:bgFillStyleLst><a:solidFill><a:schemeClr val="lt1"/></a:solidFill></a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
</a:theme>"""


def app_xml(slide_count: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Python</Application>
  <PresentationFormat>ワイド画面</PresentationFormat>
  <Slides>{slide_count}</Slides>
  <Company></Company>
</Properties>"""


def core_xml(meta: dict[str, str]) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    creator = meta["author"] or "gen_ppt.py"
    title = meta["title"]
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{escape(title)}</dc:title>
  <dc:creator>{escape(creator)}</dc:creator>
  <cp:lastModifiedBy>gen_ppt.py</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>"""


def static_part(name: str) -> str:
    if name == "presProps":
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentationPr {ns_attrs()}/>'
    if name == "viewProps":
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:viewPr {ns_attrs()}/>'
    if name == "tableStyles":
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<a:tblStyleLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" def="{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"/>'
        )
    raise ValueError(name)


def write_presentation(slides: list[Slide], meta: dict[str, str], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists():
        output.unlink()

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types(len(slides)))
        zf.writestr("_rels/.rels", package_rels())
        zf.writestr("docProps/app.xml", app_xml(len(slides)))
        zf.writestr("docProps/core.xml", core_xml(meta))
        zf.writestr("ppt/presentation.xml", presentation_xml(len(slides)))
        zf.writestr("ppt/_rels/presentation.xml.rels", presentation_rels(len(slides)))
        zf.writestr("ppt/presProps.xml", static_part("presProps"))
        zf.writestr("ppt/viewProps.xml", static_part("viewProps"))
        zf.writestr("ppt/tableStyles.xml", static_part("tableStyles"))
        zf.writestr("ppt/theme/theme1.xml", theme_xml())
        zf.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels())
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
        zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels())
        for i, slide in enumerate(slides, start=1):
            zf.writestr(f"ppt/slides/slide{i}.xml", slide_xml(slide, i - 1, len(slides)))


def find_soffice() -> str | None:
    for command in ("soffice", "libreoffice"):
        path = shutil.which(command)
        if path:
            return path

    mac_app = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    if mac_app.exists():
        return str(mac_app)

    return None


def convert_pptx_with_libreoffice(pptx_path: Path, pdf_path: Path) -> bool:
    soffice = find_soffice()
    if not soffice:
        return False

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(pdf_path.parent),
            str(pptx_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        print(f"LibreOffice PDF変換に失敗しました。簡易PDF生成に切り替えます: {stderr}")
        return False

    converted = pdf_path.parent / f"{pptx_path.stem}.pdf"
    if converted.exists() and converted != pdf_path:
        if pdf_path.exists():
            pdf_path.unlink()
        converted.rename(pdf_path)

    return pdf_path.exists()


def pdf_text(text: str) -> str:
    return "<FEFF" + text.encode("utf-16-be").hex().upper() + ">"


def pdf_escape_name(name: str) -> str:
    return name.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_color(hex_color: str) -> str:
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255
    return f"{r:.4f} {g:.4f} {b:.4f}"


def text_width_units(text: str) -> float:
    # PDF 内蔵 CIDFont (HeiseiKakuGo-W5) は ASCII もほぼ全角幅で描画されるため、
    # ASCII を 0.95、CJK を 1.0 として概算する。
    width = 0.0
    for ch in text:
        width += 0.95 if ord(ch) < 128 else 1.0
    return width


def wrap_text(text: str, max_units: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for token in re.split(r"(\s+)", text):
        if not token:
            continue
        if token.isspace():
            candidate = current + token
        else:
            candidate = current + token
        if current and text_width_units(candidate) > max_units:
            lines.append(current.strip())
            current = token.strip()
        else:
            current = candidate

    if current.strip():
        lines.append(current.strip())

    out: list[str] = []
    for line in lines:
        current = ""
        for ch in line:
            if current and text_width_units(current + ch) > max_units:
                out.append(current)
                current = ch
            else:
                current += ch
        if current:
            out.append(current)
    return out


def pdf_rect(x: float, y: float, w: float, h: float, color: str) -> str:
    return f"{pdf_color(color)} rg {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f\n"


def pdf_circle(cx: float, cy: float, r: float, color: str) -> str:
    # Bezier近似の円。PPTX側の装飾円に対応する軽量なPDF表現。
    k = 0.5522847498
    c = r * k
    return (
        f"{pdf_color(color)} rg "
        f"{cx + r:.2f} {cy:.2f} m "
        f"{cx + r:.2f} {cy + c:.2f} {cx + c:.2f} {cy + r:.2f} {cx:.2f} {cy + r:.2f} c "
        f"{cx - c:.2f} {cy + r:.2f} {cx - r:.2f} {cy + c:.2f} {cx - r:.2f} {cy:.2f} c "
        f"{cx - r:.2f} {cy - c:.2f} {cx - c:.2f} {cy - r:.2f} {cx:.2f} {cy - r:.2f} c "
        f"{cx + c:.2f} {cy - r:.2f} {cx + r:.2f} {cy - c:.2f} {cx + r:.2f} {cy:.2f} c f\n"
    )


def pdf_show_text(x: float, y: float, text: str, size: float, color: str) -> str:
    return (
        "BT "
        f"/F1 {size:.1f} Tf {pdf_color(color)} rg "
        f"1 0 0 1 {x:.2f} {y:.2f} Tm "
        f"{pdf_text(text)} Tj ET\n"
    )


def pdf_rendered_width(text: str, size: float) -> float:
    # PDF 内蔵 HeiseiKakuGo-W5 (UniJIS-UTF16-H) は ASCII/CJK ともほぼ全角幅で描画される。
    w = 0.0
    for ch in text:
        if ord(ch) < 128:
            w += size * 0.95
        else:
            w += size * 1.0
    return w


def pdf_label(x: float, y: float, w: float, h: float, text: str, fill: str | None, line: str | None, color: str, size: float = 9.0) -> str:
    parts: list[str] = []
    if fill:
        parts.append(pdf_rect(x, y, w, h, fill))
    if line:
        parts.append(pdf_rect(x, y, w, 0.6, line))
        parts.append(pdf_rect(x, y + h - 0.6, w, 0.6, line))
        parts.append(pdf_rect(x, y, 0.6, h, line))
        parts.append(pdf_rect(x + w - 0.6, y, 0.6, h, line))
    text_w = pdf_rendered_width(text, size)
    parts.append(pdf_show_text(x + (w - text_w) / 2, y + h / 2 - size / 3, text, size, color))
    return "".join(parts)


def pdf_text_centered(x: float, y: float, w: float, text: str, size: float, color: str) -> str:
    text_w = pdf_rendered_width(text, size)
    return pdf_show_text(x + (w - text_w) / 2, y, text, size, color)


FIGURE_CAPTIONS = {
    "tile_array": "図｜XDNA 2 タイルアレイ (4×8 = 32 計算タイル)",
    "tile_core": "図｜AIE 計算タイル 1個の内部構成",
    "gemm": "図｜GEMM (行列積) の実行フロー",
    "dataflow": "図｜CPU/GPU と XDNA のデータ移動の違い",
    "bars": "図｜世代別ピーク性能 (INT8 TOPS)",
    "copilot": "図｜OGA による NPU 実行モード",
    "stack": "図｜Ryzen AI ソフトウェアスタック",
    "radar": "図｜クライアント向け NPU の比較",
    "timeline": "図｜Xilinx から AMD XDNA への系譜",
    "bfp16": "図｜BFP16 ブロック共有指数の仕組み",
    "summary": "図｜本資料の論点 (3行で要点)",
    "hero": "図｜XDNA の 4 つのキーワード",
    "usecases": "図｜AMD XDNA の主な利用シーン",
    "future": "図｜NPU 専用 vs GPU 統合",
    "takeaway": "図｜本資料の Takeaway",
}


def pdf_diagram(slide: Slide, accent: str, accent2: str, text: str) -> str:
    out: list[str] = []
    # 図のコンテンツ領域 (キャプション下から下端まで): x=500..920, y=90..362
    if slide.visual == "tile_array":
        cell_w, cell_h, gap = 22, 18, 3
        base_x, base_y = 508, 280
        for row in range(4):
            for col in range(8):
                color = "EFF6FF" if (row + col) % 2 == 0 else "DBEAFE"
                out.append(pdf_rect(base_x + col * (cell_w + gap), base_y - row * (cell_h + gap), cell_w, cell_h, color))
        bus_w = 8 * (cell_w + gap) - gap
        mem_y = base_y - 4 * (cell_h + gap) - 4
        for col in range(8):
            out.append(pdf_rect(base_x + col * (cell_w + gap), mem_y, cell_w, cell_h, "DCFCE7"))
        bus_y = mem_y - 12
        out.append(pdf_rect(base_x, bus_y, bus_w, 5, accent))
        ddr_y = bus_y - 26
        out.append(pdf_rect(base_x, ddr_y, bus_w, 22, "F1F5F9"))
        out.append(pdf_text_centered(base_x, ddr_y + 8, bus_w, "DDR メインメモリ", 10, text))
        lx = base_x + bus_w + 14
        out.append(pdf_rect(lx, base_y - 4, 90, 22, "EFF6FF"))
        out.append(pdf_show_text(lx + 6, base_y + 4, "計算タイル×32", 9.5, text))
        out.append(pdf_show_text(lx + 6, base_y - 14, "VLIW + SIMD", 7.5, "475569"))
        out.append(pdf_rect(lx, mem_y - 2, 90, 22, "DCFCE7"))
        out.append(pdf_show_text(lx + 6, mem_y + 6, "メモリタイル×8", 9.5, text))
        out.append(pdf_show_text(lx + 6, mem_y - 12, "L2 / DDR橋渡し", 7.5, "475569"))
    elif slide.visual == "tile_core":
        out.append(pdf_rect(508, 282, 195, 56, "EFF6FF"))
        out.append(pdf_rect(508, 332, 195, 6, accent))
        out.append(pdf_text_centered(508, 313, 195, "ベクトルプロセッサ", 13, text))
        out.append(pdf_text_centered(508, 295, 195, "VLIW + SIMD", 9, "475569"))
        out.append(pdf_rect(708, 282, 124, 56, "DBEAFE"))
        out.append(pdf_rect(708, 332, 124, 6, accent2))
        out.append(pdf_text_centered(708, 313, 124, "スカラ RISC", 12, text))
        out.append(pdf_text_centered(708, 295, 124, "制御フロー", 9, "475569"))
        out.append(pdf_rect(508, 212, 145, 50, "FFFFFF"))
        out.append(pdf_rect(508, 256, 145, 6, "94A3B8"))
        out.append(pdf_text_centered(508, 237, 145, "命令メモリ", 11, text))
        out.append(pdf_text_centered(508, 220, 145, "Program Memory", 8, "475569"))
        out.append(pdf_rect(658, 212, 174, 50, "FFFFFF"))
        out.append(pdf_rect(658, 256, 174, 6, "94A3B8"))
        out.append(pdf_text_centered(658, 237, 174, "ローカルデータメモリ", 11, text))
        out.append(pdf_text_centered(658, 220, 174, "重み・活性化値", 8, "475569"))
        out.append(pdf_rect(508, 142, 324, 50, "DCFCE7"))
        out.append(pdf_rect(508, 186, 324, 6, accent))
        out.append(pdf_text_centered(508, 167, 324, "インターコネクト", 12, text))
        out.append(pdf_text_centered(508, 150, 324, "隣接タイル ↔ メモリタイル / DMA", 9, "475569"))
    elif slide.visual == "gemm":
        out.append(pdf_rect(508, 260, 64, 32, "EFF6FF"))
        out.append(pdf_text_centered(508, 270, 64, "行列 A", 11, text))
        out.append(pdf_rect(508, 215, 64, 32, "DBEAFE"))
        out.append(pdf_text_centered(508, 225, 64, "行列 B", 11, text))
        out.append(pdf_rect(574, 250, 24, 4, accent))
        for i in range(3):
            x = 600 + i * 62
            out.append(pdf_rect(x, 215, 56, 68, "FFFFFF"))
            out.append(pdf_rect(x, 277, 56, 6, accent))
            out.append(pdf_text_centered(x, 256, 56, f"Tile {i+1}", 10, text))
            out.append(pdf_text_centered(x, 238, 56, "FMA", 8, "475569"))
        out.append(pdf_rect(786, 250, 24, 4, accent))
        out.append(pdf_rect(812, 233, 64, 36, "DCFCE7"))
        out.append(pdf_text_centered(812, 244, 64, "行列 C", 12, text))
        steps = ["1. タイリング", "2. DMA転送", "3. FMA演算", "4. 部分積蓄", "5. 書き戻し"]
        for i, step in enumerate(steps):
            x = 510 + i * 82
            out.append(pdf_rect(x, 130, 78, 30, "F8FAFC"))
            out.append(pdf_text_centered(x, 143, 78, step, 8.5, text))
    elif slide.visual == "dataflow":
        out.append(pdf_show_text(508, 318, "CPU / GPU — キャッシュ階層から要求時フェッチ", 9.5, "475569"))
        cpu_labels = ["演算器", "L1$", "L2$", "L3$", "DRAM"]
        box_w = 64
        for i, label in enumerate(cpu_labels):
            x = 508 + i * (box_w + 8)
            out.append(pdf_rect(x, 268, box_w, 32, "FFFFFF"))
            out.append(pdf_rect(x, 295, box_w, 5, "CBD5E1"))
            out.append(pdf_text_centered(x, 277, box_w, label, 9.5, text))
            if i < len(cpu_labels) - 1:
                out.append(pdf_rect(x + box_w + 1, 281, 6, 4, "94A3B8"))
        out.append(pdf_show_text(508, 252, "キャッシュミス時に待ち時間とエネルギーを消費", 8.5, "94A3B8"))
        out.append(pdf_rect(508, 234, 412, 0.8, "E5E7EB"))
        out.append(pdf_show_text(508, 215, "XDNA — コンパイル時スケジュール / DMA で決定論的に転送", 9.5, accent))
        xdna_labels = ["DDR", "DMA", "メモリ", "計算", "計算"]
        for i, label in enumerate(xdna_labels):
            x = 508 + i * (box_w + 8)
            out.append(pdf_rect(x, 168, box_w, 32, "EFF6FF"))
            out.append(pdf_rect(x, 195, box_w, 5, accent))
            out.append(pdf_text_centered(x, 178, box_w, label, 9.5, text))
            if i < len(xdna_labels) - 1:
                out.append(pdf_rect(x + box_w + 1, 181, 6, 4, accent))
        out.append(pdf_show_text(508, 152, "実行中のキャッシュミスがなく、低消費電力", 8.5, accent))
    elif slide.visual == "bars":
        data = [
            ("Phoenix", 10, "XDNA 1 / 2023", accent2),
            ("Hawk Point", 16, "XDNA 1 / 2024", accent2),
            ("Strix Point", 55, "XDNA 2 / 2024", accent),
        ]
        max_v = 60
        bar_left = 670
        bar_max = 180
        for i, (label, value, year, color) in enumerate(data):
            y = 300 - i * 55
            out.append(pdf_show_text(508, y + 8, label, 9.5, text))
            out.append(pdf_show_text(508, y - 6, year, 8, "94A3B8"))
            out.append(pdf_rect(bar_left, y - 2, bar_max, 16, "E5E7EB"))
            out.append(pdf_rect(bar_left, y - 2, bar_max * value / max_v, 16, color))
            out.append(pdf_show_text(bar_left + bar_max + 6, y + 2, f"{value}", 11, color))
        threshold_x = bar_left + bar_max * 40 / max_v
        out.append(pdf_rect(threshold_x, 195, 1.4, 130, "DC2626"))
        out.append(pdf_show_text(threshold_x - 60, 168, "Copilot+ PC 要件 = 40 TOPS", 8.5, "DC2626"))
    elif slide.visual == "copilot":
        out.append(pdf_rect(595, 320, 240, 30, "F1F5F9"))
        out.append(pdf_text_centered(595, 330, 240, "アプリ (Copilot+ / LM Studio)", 10, text))
        out.append(pdf_rect(710, 297, 6, 22, accent))
        out.append(pdf_rect(595, 262, 240, 30, "EFF6FF"))
        out.append(pdf_rect(595, 290, 240, 4, accent))
        out.append(pdf_text_centered(595, 272, 240, "OnnxRuntime GenAI (OGA)", 10, text))
        out.append(pdf_rect(545, 250, 280, 5, accent))
        out.append(pdf_rect(545, 220, 5, 32, accent))
        out.append(pdf_rect(821, 220, 5, 32, accent))
        out.append(pdf_rect(510, 180, 168, 38, "DCFCE7"))
        out.append(pdf_rect(510, 214, 168, 4, accent))
        out.append(pdf_text_centered(510, 197, 168, "NPU-only", 11, text))
        out.append(pdf_text_centered(510, 184, 168, "NPU 専用・iGPU解放", 8, "475569"))
        out.append(pdf_rect(692, 180, 168, 38, "FEF3C7"))
        out.append(pdf_rect(692, 214, 168, 4, accent2))
        out.append(pdf_text_centered(692, 197, 168, "Hybrid", 11, text))
        out.append(pdf_text_centered(692, 184, 168, "NPU + iGPU 分担", 8, "475569"))
    elif slide.visual == "stack":
        layers = [
            ("アプリ", "Copilot+ / LM Studio", "F1F5F9", "CBD5E1"),
            ("フレームワーク", "ONNX Runtime + Vitis AI EP / OGA", "EFF6FF", accent2),
            ("量子化", "AMD Quark (INT8 / INT4 / BFP16)", "DBEAFE", accent),
            ("ドライバ / ランタイム", "amdxdna.ko / XRT SHIM", "EFF6FF", accent2),
            ("ハードウェア", "AMD XDNA NPU (AIE タイルアレイ)", "DCFCE7", accent),
        ]
        for i, (head, body, fill, line) in enumerate(layers):
            y = 310 - i * 42
            out.append(pdf_rect(508, y, 412, 36, fill))
            out.append(pdf_rect(508, y + 32, 412, 4, line))
            out.append(pdf_show_text(522, y + 19, head, 11, text))
            out.append(pdf_show_text(522, y + 5, body, 8.5, "475569"))
    elif slide.visual == "timeline":
        out.append(pdf_rect(540, 240, 360, 4, accent))
        events = [("1984", "Xilinx 創業", "FPGA を発明"), ("2019", "Versal ACAP", "AI Engine 搭載"), ("2022", "AMD が買収", "約350億ドル"), ("2023", "XDNA 初代", "Ryzen 7040")]
        for i, (year, head, body) in enumerate(events):
            x = 560 + i * 112
            out.append(pdf_circle(x, 242, 9, accent if i == 3 else accent2))
            out.append(pdf_text_centered(x - 40, 275, 80, year, 12, accent if i == 3 else text))
            out.append(pdf_text_centered(x - 60, 220, 120, head, 10, text))
            out.append(pdf_text_centered(x - 60, 205, 120, body, 8.5, "475569"))
    elif slide.visual == "bfp16":
        out.append(pdf_show_text(508, 320, "通常の FP16 (要素ごと独立)", 10, "475569"))
        for i in range(3):
            x = 510 + i * 135
            out.append(pdf_rect(x, 270, 14, 38, "F1F5F9"))
            out.append(pdf_rect(x + 14, 270, 40, 38, "FED7AA"))
            out.append(pdf_rect(x + 54, 270, 65, 38, "DBEAFE"))
            if i == 0:
                out.append(pdf_text_centered(x, 256, 14, "符", 7, "475569"))
                out.append(pdf_text_centered(x + 14, 256, 40, "指数 5b", 7.5, accent2))
                out.append(pdf_text_centered(x + 54, 256, 65, "仮数 10b", 7.5, accent))
        out.append(pdf_rect(508, 232, 412, 0.8, "E5E7EB"))
        out.append(pdf_show_text(508, 218, "BFP16 (8 要素で指数を共有)", 10, accent))
        bfp_y = 168
        out.append(pdf_rect(510, bfp_y, 64, 44, "FED7AA"))
        out.append(pdf_text_centered(510, bfp_y + 26, 64, "共有指数", 9, text))
        out.append(pdf_text_centered(510, bfp_y + 12, 64, "8 bit", 8, "475569"))
        for i in range(8):
            x = 580 + i * 32
            out.append(pdf_rect(x, bfp_y, 28, 44, "DBEAFE"))
            out.append(pdf_text_centered(x, bfp_y + 18, 28, f"E{i+1}", 8.5, text))
        out.append(pdf_show_text(508, bfp_y - 14, "各要素 = 符号1 + 仮数7 bit", 8.5, "475569"))
    elif slide.visual == "radar":
        headers = [("ベンダー", 110), ("TOPS", 76), ("アーキ", 100), ("精度", 124)]
        rows = [
            ("AMD", "55–60", "AIE 配列", "INT8/BFP16"),
            ("Intel", "48", "MAC 配列", "INT8/FP16"),
            ("Qualcomm", "45–85", "Hexagon", "INT8/INT4"),
        ]
        base_x = 508
        base_y = 290
        x = base_x
        for h, w in headers:
            out.append(pdf_rect(x, base_y, w, 30, "F1F5F9"))
            out.append(pdf_text_centered(x, base_y + 10, w, h, 9.5, "475569"))
            x += w
        for r, row in enumerate(rows):
            x = base_x
            y = base_y - 38 - r * 38
            emphasis = r == 0
            for c, value in enumerate(row):
                w = headers[c][1]
                out.append(pdf_rect(x, y, w, 34, "EFF6FF" if emphasis else "FFFFFF"))
                if emphasis:
                    out.append(pdf_rect(x, y, w, 4, accent))
                color = accent if emphasis and c == 0 else text
                out.append(pdf_text_centered(x, y + 12, w, value, 10 if c == 0 else 8.8, color))
                x += w
    elif slide.visual == "usecases":
        cases = [
            ("Copilot+ PC", ["Recall", "Cocreator", "Live Captions", "Studio Effects"], accent),
            ("ローカル LLM", ["NPU-only", "Hybrid モード", "LM Studio", "省電力推論"], accent2),
            ("エッジ AI", ["産業画像検査", "ロボット推論", "医療画像処理", "小売認識"], "8A5A44"),
        ]
        base_y = 130
        card_h = 180
        for i, (head, lines, color) in enumerate(cases):
            x = 510 + i * 138
            out.append(pdf_rect(x, base_y + card_h - 32, 130, 32, color))
            out.append(pdf_text_centered(x, base_y + card_h - 22, 130, head, 11, "FFFFFF"))
            out.append(pdf_rect(x, base_y, 130, card_h - 36, "F8FAFC"))
            for j, line in enumerate(lines):
                out.append(pdf_show_text(x + 10, base_y + card_h - 60 - j * 22, line, 8.5, text))
    elif slide.visual == "future":
        out.append(pdf_rect(620, 318, 180, 38, "F1F5F9"))
        out.append(pdf_text_centered(620, 336, 180, "クライアントAI推論", 11, text))
        out.append(pdf_text_centered(620, 322, 180, "Copilot+ / ローカル LLM", 8, "475569"))
        out.append(pdf_rect(708, 296, 5, 22, accent))
        out.append(pdf_rect(540, 290, 340, 5, accent))
        out.append(pdf_rect(540, 268, 5, 22, accent))
        out.append(pdf_rect(875, 268, 5, 22, accent))
        out.append(pdf_rect(510, 232, 200, 32, accent2))
        out.append(pdf_text_centered(510, 244, 200, "専用 NPU 継続", 11, "FFFFFF"))
        out.append(pdf_rect(510, 152, 200, 78, "F8FAFC"))
        out.append(pdf_show_text(522, 210, "◯ 高い perf / watt", 9, text))
        out.append(pdf_show_text(522, 190, "◯ 決定論的レイテンシ", 9, text))
        out.append(pdf_show_text(522, 170, "× 専用ダイ面積", 9, "475569"))
        out.append(pdf_rect(715, 232, 205, 32, accent))
        out.append(pdf_text_centered(715, 244, 205, "GPU 統合", 11, "FFFFFF"))
        out.append(pdf_rect(715, 152, 205, 78, "F8FAFC"))
        out.append(pdf_show_text(727, 210, "◯ ダイ面積を共用可", 9, text))
        out.append(pdf_show_text(727, 190, "◯ RDNA 5 Neural Arrays", 9, text))
        out.append(pdf_show_text(727, 170, "× AI特化の電力効率↓", 9, "475569"))
    elif slide.visual == "takeaway":
        items = [
            ("空間データフロー", "AIE タイルが DMA で協調する低消費電力 NPU", accent),
            ("急速な世代進化", "10 → 16 → 55 TOPS / BFP16 / 32 タイル", accent2),
            ("将来は不透明", "GPU 統合に伴う NPU 単独運用の存続性が論点", accent),
        ]
        for i, (head, body, color) in enumerate(items):
            y = 300 - i * 80
            out.append(pdf_rect(508, y, 412, 64, "F8FAFC"))
            out.append(pdf_rect(508, y + 60, 412, 4, color))
            out.append(pdf_show_text(522, y + 40, head, 12, color))
            out.append(pdf_show_text(522, y + 18, body, 9.5, text))
    elif slide.visual == "summary":
        items = [
            ("01", "空間データフロー型 NPU", "AIE タイルが並列にデータ処理", accent),
            ("02", "10 → 55 TOPS の急進化", "世代ごとにタイル数とデータ型を拡張", accent2),
            ("03", "AI PC の中核技術", "OGA でローカル LLM 推論を実用化", accent),
        ]
        for i, (num, head, body, color) in enumerate(items):
            y = 280 - i * 80
            out.append(pdf_circle(528, y + 30, 22, color))
            out.append(pdf_text_centered(508, y + 24, 40, num, 16, "FFFFFF"))
            out.append(pdf_rect(564, y, 356, 60, "F8FAFC"))
            out.append(pdf_show_text(578, y + 36, head, 12, text))
            out.append(pdf_show_text(578, y + 14, body, 9.5, "475569"))
    else:
        items = [
            ("起源", "Xilinx Versal AI Engine", accent),
            ("設計", "空間データフロー (AIE + DMA)", accent2),
            ("到達", "XDNA 2 で 55 TOPS", accent),
            ("用途", "Copilot+ PC / ローカル LLM", accent2),
        ]
        for i, (head, body, color) in enumerate(items):
            y = 300 - i * 56
            out.append(pdf_rect(508, y, 412, 48, "F8FAFC"))
            out.append(pdf_show_text(522, y + 28, head, 11, color))
            out.append(pdf_show_text(522, y + 10, body, 10, text))
    return "".join(out)


def pdf_slide_stream(slide: Slide, index: int, width: float, height: float, slide_count: int) -> str:
    _, _, accent_color, accent2_color, _, text_color = academic_palette(index)

    stream: list[str] = []
    stream.append(pdf_rect(0, 0, width, height, "FFFFFF"))
    stream.append(pdf_rect(0, height - 11, width, 11, accent_color))

    if slide.kicker:
        stream.append(pdf_show_text(45, height - 38, slide.kicker, 11, accent_color))
        stream.append(pdf_show_text(45, height - 70, slide.title, 22 if index else 28, text_color))
    else:
        stream.append(pdf_show_text(45, height - 60, slide.title, 28, text_color))

    chip_w, chip_h = 64, 40
    chip_x = width - 78
    chip_y = height - 60
    stream.append(pdf_rect(chip_x, chip_y, chip_w, chip_h, "FFFFFF"))
    stream.append(pdf_rect(chip_x, chip_y, chip_w, 1.6, accent_color))
    stream.append(pdf_rect(chip_x, chip_y + chip_h - 1.6, chip_w, 1.6, accent_color))
    stream.append(pdf_rect(chip_x, chip_y, 1.6, chip_h, accent_color))
    stream.append(pdf_rect(chip_x + chip_w - 1.6, chip_y, 1.6, chip_h, accent_color))
    stream.append(pdf_text_centered(chip_x, chip_y + 12, chip_w, f"{index + 1:02d}", 18, accent_color))

    stream.append(pdf_rect(45, height - 102, width - 90, 1.4, accent_color))

    bullet_x = 50
    bullet_y = height - 134
    for bullet in slide.bullets:
        lines = wrap_text(bullet, 23)
        stream.append(pdf_show_text(bullet_x, bullet_y, "●", 9, accent_color))
        for i, line in enumerate(lines):
            stream.append(pdf_show_text(bullet_x + 20, bullet_y - i * 22, line, 13, text_color))
        bullet_y -= max(1, len(lines)) * 22 + 14

    fig_x = 498
    fig_w = 424
    fig_y_top = height - 102 - 6
    fig_h = 332
    fig_y_bottom = fig_y_top - fig_h
    stream.append(pdf_rect(fig_x, fig_y_bottom, fig_w, fig_h, "FFFFFF"))
    stream.append(pdf_rect(fig_x, fig_y_bottom, fig_w, 0.8, "E5E7EB"))
    stream.append(pdf_rect(fig_x, fig_y_top - 0.8, fig_w, 0.8, "E5E7EB"))
    stream.append(pdf_rect(fig_x, fig_y_bottom, 0.8, fig_h, "E5E7EB"))
    stream.append(pdf_rect(fig_x + fig_w - 0.8, fig_y_bottom, 0.8, fig_h, "E5E7EB"))
    stream.append(pdf_rect(fig_x, fig_y_top - 32, fig_w, 32, "F8FAFC"))
    caption = FIGURE_CAPTIONS.get(slide.visual, "図｜詳細")
    stream.append(pdf_show_text(fig_x + 16, fig_y_top - 21, caption, 10.5, accent_color))
    stream.append(pdf_rect(fig_x, fig_y_top - 33, fig_w, 0.8, accent_color))

    stream.append(pdf_diagram(slide, accent_color, accent2_color, text_color))

    stream.append(pdf_rect(45, 32, width - 90, 0.6, "E5E7EB"))
    footer_text = slide.note or "AMD XDNA アーキテクチャ概要"
    stream.append(pdf_show_text(45, 18, footer_text[:70], 8.5, "64748B"))
    stream.append(pdf_show_text(width - 100, 18, f"{index + 1} / {slide_count}", 8.5, "94A3B8"))
    return "".join(stream)


def render_pdf(slides: list[Slide], meta: dict[str, str], pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    width = 960.0
    height = 540.0

    objects: list[bytes] = []

    def add_object(body: str | bytes) -> int:
        data = body.encode("utf-8") if isinstance(body, str) else body
        objects.append(data)
        return len(objects)

    font_obj = add_object(
        "<< /Type /Font /Subtype /Type0 /BaseFont /HeiseiKakuGo-W5 "
        "/Encoding /UniJIS-UTF16-H /DescendantFonts [ << /Type /Font "
        "/Subtype /CIDFontType0 /BaseFont /HeiseiKakuGo-W5 "
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (Japan1) /Supplement 5 >> "
        "/FontDescriptor << /Type /FontDescriptor /FontName /HeiseiKakuGo-W5 "
        "/Flags 6 /FontBBox [0 -200 1000 900] /ItalicAngle 0 "
        "/Ascent 880 /Descent -120 /CapHeight 700 /StemV 80 >> >> ] >>"
    )

    page_objects: list[int] = []
    pages_obj = 0
    for index, slide in enumerate(slides):
        stream = pdf_slide_stream(slide, index, width, height, len(slides)).encode("utf-8")
        content_obj = add_object(
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
            + stream
            + b"endstream"
        )
        page_obj = add_object(
            f"<< /Type /Page /Parent PAGES_REF 0 R /MediaBox [0 0 {width:.0f} {height:.0f}] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {content_obj} 0 R >>"
        )
        page_objects.append(page_obj)

    pages_obj = add_object(
        "<< /Type /Pages /Kids ["
        + " ".join(f"{obj} 0 R" for obj in page_objects)
        + f"] /Count {len(page_objects)} >>"
    )
    catalog_obj = add_object(f"<< /Type /Catalog /Pages {pages_obj} 0 R >>")
    info_obj = add_object(
        f"<< /Title ({pdf_escape_name(meta['title'])}) /Producer (gen_ppt.py) >>"
    )

    for page_obj in page_objects:
        objects[page_obj - 1] = objects[page_obj - 1].replace(
            b"PAGES_REF", str(pages_obj).encode("ascii")
        )

    output = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{i} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_pos = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        output.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root {catalog_obj} 0 R /Info {info_obj} 0 R >>\n"
            "startxref\n"
            f"{xref_pos}\n"
            "%%EOF\n"
        ).encode("ascii")
    )
    pdf_path.write_bytes(output)


def write_pdf(slides: list[Slide], meta: dict[str, str], pptx_path: Path, pdf_path: Path) -> None:
    if convert_pptx_with_libreoffice(pptx_path, pdf_path):
        return

    render_pdf(slides, meta, pdf_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="main.md を要約したPPTXとPDFを生成します。")
    parser.add_argument("markdown", nargs="?", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pdf-output", type=Path, default=DEFAULT_PDF_OUTPUT)
    parser.add_argument("--no-pdf", action="store_true", help="PDF生成をスキップする")
    args = parser.parse_args()

    if not args.markdown.exists():
        raise SystemExit(f"Markdownファイルが見つかりません: {args.markdown}")

    markdown = args.markdown.read_text(encoding="utf-8")
    meta = extract_metadata(markdown)
    slides = build_slides(meta)
    write_presentation(slides, meta, args.output)
    print(f"生成完了: {args.output} ({len(slides)} slides)")
    if not args.no_pdf:
        write_pdf(slides, meta, args.output, args.pdf_output)
        print(f"PDF生成完了: {args.pdf_output}")


if __name__ == "__main__":
    main()
