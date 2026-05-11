#!/usr/bin/env python3
"""main.md の内容を要約した PowerPoint 互換プレゼンを生成する."""

from __future__ import annotations

import argparse
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


DEFAULT_MARKDOWN = Path("./main.md")
DEFAULT_OUTPUT = Path("./build/main.ppt")

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
) -> str:
    fill_xml = (
        f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
    )
    line_xml = (
        f'<a:ln><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
        if line
        else "<a:ln><a:noFill/></a:ln>"
    )
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
  </p:spPr>
  <p:txBody>
    <a:bodyPr wrap="square" lIns="120000" tIns="70000" rIns="120000" bIns="70000"/>
    <a:lstStyle/>
    {paragraphs_xml}
  </p:txBody>
</p:sp>"""


def slide_xml(slide: Slide, index: int) -> str:
    title = paragraph(slide.title, 3400 if index else 4200, "FFFFFF", True)
    kicker = paragraph(slide.kicker, 1500, "DDE7FF", False) if slide.kicker else ""
    header = textbox(
        2,
        "Title",
        emu(0),
        emu(0),
        int(SLIDE_W),
        emu(1.32),
        kicker + title,
        fill="1D4ED8",
    )

    bullet_xml = "".join(bullet_paragraph(b) for b in slide.bullets)
    content = textbox(
        3,
        "Summary",
        emu(0.85),
        emu(1.75),
        emu(11.65),
        emu(4.65),
        bullet_xml,
        fill="F8FAFC",
        line="DBEAFE",
        radius="roundRect",
    )

    footer_text = slide.note or "AMD XDNA Architecture Overview"
    footer = textbox(
        4,
        "Footer",
        emu(0.75),
        emu(6.88),
        emu(11.8),
        emu(0.35),
        paragraph(footer_text, 950, "64748B"),
    )

    slide_no = textbox(
        5,
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
      {header}
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


def main() -> None:
    parser = argparse.ArgumentParser(description="main.md を要約したプレゼンを生成します。")
    parser.add_argument("markdown", nargs="?", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.markdown.exists():
        raise SystemExit(f"Markdownファイルが見つかりません: {args.markdown}")

    markdown = args.markdown.read_text(encoding="utf-8")
    meta = extract_metadata(markdown)
    slides = build_slides(meta)
    write_presentation(slides, meta, args.output)
    print(f"生成完了: {args.output} ({len(slides)} slides)")


if __name__ == "__main__":
    main()
