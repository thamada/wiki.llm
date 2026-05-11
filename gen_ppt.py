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
            bullets=(
                "XDNAは2D配列のAIEタイルが並列にデータを処理する空間データフロー型NPU",
                "世代ごとにタイル数・メモリ・データ型が拡張され、10 TOPSから55 TOPS級へ急伸",
                "NPU上のLLM推論はOnnxRuntime GenAIが担い、AI PC向けの中核技術になっている",
            ),
        ),
        Slide(
            title="技術的ルーツ",
            kicker="Xilinx AI Engine → AMD XDNA",
            bullets=(
                "XilinxはFPGAの発明者で、Versal ACAPにAI Engineを搭載",
                "AMDは2022年にXilinxを約350億ドルで買収し、AIEをクライアントAPU向けに再設計",
                "DeePhi由来技術はVitis AIなどのソフトウェア層で活用され、XDNAハードウェアとは役割が異なる",
            ),
        ),
        Slide(
            title="設計思想: 空間データフロー",
            kicker="CPU/GPUとの違い",
            bullets=(
                "CPU/GPUはキャッシュ階層から動的にデータをフェッチするため、待ち時間と電力コストが発生",
                "XDNAはコンパイル時にデータ移動経路とタイミングを決め、DMAで決定論的に転送",
                "キャッシュミスを避け、AI推論に必要なデータをオンチップに局所化する",
            ),
        ),
        Slide(
            title="2Dタイルアレイが心臓部",
            kicker="Compute Tile + Memory Tile",
            bullets=(
                "Strix Point世代では4行×8列、合計32個の計算タイルを配置",
                "各列のメモリタイルがL2として働き、DDRとのステージングを担当",
                "専用DMAがホストメモリとタイルアレイ間のデータ転送を担う",
            ),
        ),
        Slide(
            title="AIE計算タイルの内部",
            kicker="小さな専用プロセッサの集合",
            bullets=(
                "ベクトルプロセッサはVLIW + SIMDでテンソル演算を並列実行",
                "スカラRISCプロセッサが制御フローやアドレス計算を担当",
                "命令メモリ・ローカルデータメモリ・タイル間インターコネクトを各タイルが持つ",
            ),
        ),
        Slide(
            title="GEMM実行イメージ",
            kicker="AI推論の主要ワークロード",
            bullets=(
                "大きな行列を小さなブロックに分割し、複数タイルへ分散",
                "DMAがDDRからメモリタイル経由で計算タイルへデータを配送",
                "各タイルがFMAを実行し、部分積を受け渡しながら結果を蓄積・書き戻す",
            ),
        ),
        Slide(
            title="世代別の進化",
            kicker="10 TOPS → 55 TOPS",
            bullets=(
                "初代XDNA: Ryzen 7040、4×5タイル、最大10 TOPS",
                "Hawk Point: 同系統ハードウェアをファームウェア最適化し16 TOPSへ",
                "XDNA 2: Ryzen AI 300、4×8タイル、L2 60%増、BFP16対応、最大55 TOPS",
            ),
        ),
        Slide(
            title="XDNA 2の意味",
            kicker="Copilot+ PC世代のNPU",
            bullets=(
                "MicrosoftのCopilot+ PC要件である40 TOPS以上を満たす",
                "NPU-only / Hybridモードにより、LLM推論をNPUまたはNPU+iGPUで実行",
                "Ryzen AI 300、Ryzen AI Max、Ryzen AI 400へ展開が広がる",
            ),
        ),
        Slide(
            title="BFP16という妥協点",
            kicker="INT8並の効率 + FP16に近い精度",
            bullets=(
                "BFP16は8要素で指数を共有し、各要素は符号1ビット + 仮数7ビットで保持",
                "1要素あたりの保存効率はINT8に近く、FP16よりメモリ帯域を抑えやすい",
                "ブロック内の値スケールが近い場合に精度劣化を抑えられる",
            ),
        ),
        Slide(
            title="ソフトウェアスタック",
            kicker="アプリからNPUまで",
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
            bullets=(
                "AMD XDNA 2は55〜60 TOPS級で、空間データフロー型AIEタイル配列を採用",
                "Intel NPU 4は48 TOPS級で、ネイティブFP16対応が強み",
                "Qualcomm HexagonはArmプラットフォーム統合と高い総合AI性能を訴求",
            ),
        ),
        Slide(
            title="主な利用シーン",
            kicker="AI PCからエッジまで",
            bullets=(
                "Copilot+ PC: Recall、Cocreator、Live Captions、Studio Effectsなど",
                "ローカルLLM推論: クラウドに接続せず省電力に推論",
                "エッジAI / 組み込み: 画像検査、ロボット、医療画像、小売認識など",
            ),
        ),
        Slide(
            title="専用NPUの将来論",
            kicker="GPU統合の可能性",
            bullets=(
                "RDNA 5のNeural Arraysにより、GPU側のAI推論能力が強化される見込み",
                "ダイ面積・Copilot+ PC普及遅れ・iGPU性能向上がNPU廃止論の背景",
                "一方で、XDNAの電力効率と決定論的実行はGPUで容易に代替できない",
            ),
        ),
        Slide(
            title="まとめ",
            kicker="Takeaways",
            bullets=(
                "XDNAはXilinx由来の空間データフロー技術をPC向けに最適化したNPU",
                "2DタイルアレイとDMAベースのデータ移動により、低消費電力なAI推論を実現",
                "将来はGPU統合の可能性があるが、XDNAの技術的優位性は次世代にも残りうる",
            ),
        ),
    ]


def ns_attrs() -> str:
    return " ".join(f'xmlns:{prefix}="{uri}"' for prefix, uri in NS.items())


def text_run(text: str, size: int, color: str = "1F2937", bold: bool = False) -> str:
    b = ' b="1"' if bold else ""
    return (
        f'<a:r><a:rPr lang="ja-JP" sz="{size}"{b}>'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        '<a:latin typeface="Aptos"/><a:ea typeface="Yu Gothic"/></a:rPr>'
        f"<a:t>{escape(text)}</a:t></a:r>"
    )


def paragraph(text: str, size: int, color: str = "1F2937", bold: bool = False) -> str:
    return (
        '<a:p><a:pPr><a:buNone/></a:pPr>'
        f"{text_run(text, size, color, bold)}"
        '<a:endParaRPr lang="ja-JP"/></a:p>'
    )


def bullet_paragraph(text: str, size: int = 2150) -> str:
    return (
        '<a:p><a:pPr marL="342900" indent="-228600">'
        '<a:buFont typeface="Arial"/><a:buChar char="•"/></a:pPr>'
        f"{text_run(text, size, '263238')}"
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
        '<a:outerShdw blurRad="50800" dist="25400" dir="5400000" algn="ctr" rotWithShape="0">'
        '<a:srgbClr val="0F172A"><a:alpha val="18000"/></a:srgbClr>'
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


def slide_xml(slide: Slide, index: int) -> str:
    palette = [
        ("0F172A", "2563EB", "DBEAFE"),
        ("111827", "0891B2", "CFFAFE"),
        ("111827", "7C3AED", "EDE9FE"),
        ("111827", "EA580C", "FFEDD5"),
    ]
    header_color, accent_color, pale_color = palette[index % len(palette)]

    background = shape(2, "Background", 0, 0, int(SLIDE_W), int(SLIDE_H), "F8FAFC")
    accent_bar = shape(3, "Accent Bar", 0, 0, emu(0.18), int(SLIDE_H), accent_color)
    orb = shape(
        4,
        "Accent Orb",
        emu(10.55),
        emu(-0.55),
        emu(3.45),
        emu(3.45),
        pale_color,
        radius="ellipse",
        alpha=62000,
    )
    small_orb = shape(
        5,
        "Accent Orb Small",
        emu(11.85),
        emu(4.95),
        emu(1.55),
        emu(1.55),
        accent_color,
        radius="ellipse",
        alpha=15000,
    )

    title = paragraph(slide.title, 3350 if index else 4300, "FFFFFF", True)
    kicker = paragraph(slide.kicker, 1450, pale_color, False) if slide.kicker else ""
    header = textbox(
        6,
        "Title",
        emu(0.68),
        emu(0.42),
        emu(9.65),
        emu(1.34),
        kicker + title,
        fill=header_color,
        radius="roundRect",
        shadow=True,
    )

    bullet_xml = "".join(bullet_paragraph(b) for b in slide.bullets)
    content = textbox(
        7,
        "Summary",
        emu(0.85),
        emu(2.02),
        emu(10.8),
        emu(4.35),
        bullet_xml,
        fill="FFFFFF",
        line=pale_color,
        radius="roundRect",
        shadow=True,
    )

    index_chip = textbox(
        8,
        "Section Chip",
        emu(10.75),
        emu(0.58),
        emu(1.55),
        emu(0.56),
        paragraph(f"{index + 1:02d}", 1600, "FFFFFF", True),
        fill=accent_color,
        radius="roundRect",
        shadow=True,
    )

    footer_text = slide.note or "AMD XDNA Architecture Overview"
    footer = textbox(
        9,
        "Footer",
        emu(0.75),
        emu(6.88),
        emu(11.8),
        emu(0.35),
        paragraph(footer_text, 950, "64748B"),
    )

    slide_no = textbox(
        10,
        "Slide Number",
        emu(12.25),
        emu(6.86),
        emu(0.45),
        emu(0.35),
        paragraph(str(index + 1), 900, "94A3B8"),
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
      {orb}
      {small_orb}
      {accent_bar}
      {header}
      {index_chip}
      {content}
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
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="XDNA Overview">
  <a:themeElements>
    <a:clrScheme name="XDNA">
      <a:dk1><a:srgbClr val="111827"/></a:dk1>
      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="1E3A8A"/></a:dk2>
      <a:lt2><a:srgbClr val="EFF6FF"/></a:lt2>
      <a:accent1><a:srgbClr val="2563EB"/></a:accent1>
      <a:accent2><a:srgbClr val="06B6D4"/></a:accent2>
      <a:accent3><a:srgbClr val="22C55E"/></a:accent3>
      <a:accent4><a:srgbClr val="F97316"/></a:accent4>
      <a:accent5><a:srgbClr val="8B5CF6"/></a:accent5>
      <a:accent6><a:srgbClr val="64748B"/></a:accent6>
      <a:hlink><a:srgbClr val="2563EB"/></a:hlink>
      <a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink>
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
            zf.writestr(f"ppt/slides/slide{i}.xml", slide_xml(slide, i - 1))


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
    width = 0.0
    for ch in text:
        width += 0.55 if ord(ch) < 128 else 1.0
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


def pdf_slide_stream(slide: Slide, index: int, width: float, height: float) -> str:
    palette = [
        ("0F172A", "2563EB", "DBEAFE"),
        ("111827", "0891B2", "CFFAFE"),
        ("111827", "7C3AED", "EDE9FE"),
        ("111827", "EA580C", "FFEDD5"),
    ]
    header_color, accent_color, pale_color = palette[index % len(palette)]

    stream = []
    stream.append(pdf_rect(0, 0, width, height, "F8FAFC"))
    stream.append(pdf_circle(width - 80, height - 20, 125, pale_color))
    stream.append(pdf_circle(width - 15, 110, 55, pale_color))
    stream.append(pdf_rect(0, 0, 13, height, accent_color))

    stream.append(pdf_rect(49, height - 130, 695, 96, header_color))
    stream.append(pdf_show_text(67, height - 67, slide.kicker, 13, pale_color))
    stream.append(pdf_show_text(67, height - 105, slide.title, 26 if index else 31, "FFFFFF"))

    stream.append(pdf_rect(width - 187, height - 85, 112, 40, accent_color))
    stream.append(pdf_show_text(width - 151, height - 72, f"{index + 1:02d}", 18, "FFFFFF"))

    stream.append(pdf_rect(61, 94, 778, 313, "FFFFFF"))
    stream.append(pdf_rect(61, 94, 778, 4, pale_color))

    y = 360
    for bullet in slide.bullets:
        lines = wrap_text(bullet, 48)
        stream.append(pdf_show_text(92, y, "•", 17, accent_color))
        for i, line in enumerate(lines):
            stream.append(pdf_show_text(116, y - (i * 22), line, 15.5, "263238"))
        y -= max(1, len(lines)) * 22 + 18

    footer = slide.note or "AMD XDNA Architecture Overview"
    stream.append(pdf_show_text(54, 29, footer[:96], 8.5, "64748B"))
    stream.append(pdf_show_text(width - 65, 29, str(index + 1), 8.5, "94A3B8"))
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
        stream = pdf_slide_stream(slide, index, width, height).encode("utf-8")
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
