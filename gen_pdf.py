#!/usr/bin/env python3
"""Markdownファイルを LaTeX に変換し、tectonic で PDF をビルドする."""

from __future__ import annotations

import argparse
import base64
import os
import platform
import re
import shutil
import subprocess
import sys
import json
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

DEFAULT_MARKDOWN = "./main.md"
DEFAULT_BUILD_DIR = "./build/"


# ---------------------------------------------------------------------------
# Font detection
# ---------------------------------------------------------------------------

def get_cjk_fonts():
    system = platform.system()
    if system == "Darwin":
        return {
            "main": "Hiragino Mincho ProN",
            "sans": "Hiragino Kaku Gothic ProN",
            "mono": "Osaka-Mono",
        }
    return {
        "main": "Noto Serif CJK JP",
        "sans": "Noto Sans CJK JP",
        "mono": "Noto Sans Mono CJK JP",
    }


# ---------------------------------------------------------------------------
# LaTeX escaping
# ---------------------------------------------------------------------------

_LATEX_SPECIAL = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(text: str) -> str:
    return "".join(_LATEX_SPECIAL.get(c, c) for c in text)


def escape_url(url: str) -> str:
    """URL 中に現れる LaTeX 特殊文字だけエスケープする."""
    return url.replace("%", r"\%").replace("#", r"\#").replace("&", r"\&")


# ---------------------------------------------------------------------------
# Inline Markdown → LaTeX
# ---------------------------------------------------------------------------

def process_inline(text: str) -> str:
    # リンクをインラインコードより先に退避する。[`code`](url) のとき、code 用の
    # \x00 プレースホルダがリンク側に取り込まれて復元されず、LaTeX が不正バイトで失敗するのを防ぐ。
    links: list[tuple[str, str]] = []

    def _save_link(m):
        links.append((m.group(1), m.group(2)))
        return f"\x00L{len(links) - 1}\x00"

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _save_link, text)

    codes: list[str] = []

    def _save_code(m):
        codes.append(m.group(1))
        return f"\x00C{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", _save_code, text)

    text = escape_latex(text)

    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\\textit{\1}", text)

    for i, c in enumerate(codes):
        text = text.replace(
            f"\x00C{i}\x00", r"\texttt{" + escape_latex(c) + "}"
        )

    for i, (label, url) in enumerate(links):
        inner = process_inline(label)
        text = text.replace(
            f"\x00L{i}\x00",
            r"\href{" + escape_url(url) + "}{" + inner + "}",
        )

    return text


# ---------------------------------------------------------------------------
# Table conversion
# ---------------------------------------------------------------------------

def _is_table_line(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and s.count("|") >= 3


def _is_separator(line: str) -> bool:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return all(re.match(r"^:?-+:?$", c) for c in cells if c)


def _convert_table(lines: list[str]) -> list[str]:
    if len(lines) < 2:
        return []

    headers = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    ncols = len(headers)

    aligns = ["l"] * ncols
    data_start = 1
    if len(lines) > 1 and _is_separator(lines[1]):
        for i, cell in enumerate(
            c.strip() for c in lines[1].strip().strip("|").split("|")
        ):
            if i >= ncols:
                break
            if cell.startswith(":") and cell.endswith(":"):
                aligns[i] = "c"
            elif cell.endswith(":"):
                aligns[i] = "r"
        data_start = 2

    out: list[str] = [""]
    font_cmd = r"\footnotesize" if ncols > 4 else r"\small"
    out.append("{" + font_cmd)

    col_spec = "|".join(aligns)
    out.append(r"\noindent\adjustbox{max width=\textwidth}{%")
    out.append(r"\begin{tabular}{|" + col_spec + "|}")
    out.append(r"\hline")

    hcells = [r"\textbf{" + process_inline(h) + "}" for h in headers]
    out.append(" & ".join(hcells) + r" \\")
    out.append(r"\hline")

    for row in lines[data_start:]:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        while len(cells) < ncols:
            cells.append("")
        out.append(
            " & ".join(process_inline(c) for c in cells[:ncols]) + r" \\"
        )
        out.append(r"\hline")

    out.append(r"\end{tabular}}")
    out.append("}")
    out.append("")
    return out


# ---------------------------------------------------------------------------
# Mermaid rendering
# ---------------------------------------------------------------------------

_mermaid_counter = 0


def _is_png(data: bytes) -> bool:
    return len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n"


def _is_jpeg(data: bytes) -> bool:
    return len(data) >= 3 and data[:3] == b"\xff\xd8\xff"


_HTTP_HEADERS = {
    "User-Agent": "gen_pdf/wiki-markdown-pdf/1.0 (Mermaid diagram render)",
}


def _render_mermaid_kroki(source: str, png_file: Path) -> bool:
    """Kroki に Mermaid を POST して PNG を保存する（ネットワーク必須）."""
    off = os.environ.get("MERMAID_OFFLINE", "").strip().lower()
    if off in ("1", "true", "yes", "on"):
        return False
    base = os.environ.get("MERMAID_KROKI_URL", "https://kroki.io").strip().rstrip("/")
    url = f"{base}/mermaid/png"
    req = urllib.request.Request(
        url,
        data=source.encode("utf-8"),
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            **_HTTP_HEADERS,
        },
        method="POST",
    )
    timeout_s = float(os.environ.get("MERMAID_KROKI_TIMEOUT", "90"))
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"  Kroki 警告 ({png_file.name}): {exc}", file=sys.stderr)
        return False
    if not _is_png(data):
        print(
            f"  Kroki 警告 ({png_file.name}): PNG でない応答を受け取りました",
            file=sys.stderr,
        )
        return False
    png_file.write_bytes(data)
    return True


def _render_mermaid_ink(source: str, jpg_file: Path) -> bool:
    """mermaid.ink に GET して JPEG を保存する（ネットワーク必須・URL 長に制限あり）."""
    off = os.environ.get("MERMAID_OFFLINE", "").strip().lower()
    if off in ("1", "true", "yes", "on"):
        return False
    base = os.environ.get("MERMAID_INK_URL", "https://mermaid.ink").strip().rstrip("/")
    graph = {"code": source, "mermaid": {}}
    compress = zlib.compressobj(9, zlib.DEFLATED, 15, 8, zlib.Z_DEFAULT_STRATEGY)
    blob = compress.compress(bytes(json.dumps(graph), "ascii")) + compress.flush()
    b64 = (
        base64.b64encode(blob).decode("ascii").replace("+", "-").replace("/", "_").rstrip("=")
    )
    enc_path = urllib.parse.quote("pako:" + b64, safe="")
    url = f"{base}/img/{enc_path}"
    timeout_s = float(os.environ.get("MERMAID_INK_TIMEOUT", "90"))
    req = urllib.request.Request(url, headers=dict(_HTTP_HEADERS))
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"  mermaid.ink 警告 ({jpg_file.name}): {exc}", file=sys.stderr)
        return False
    if not _is_jpeg(data):
        print(
            f"  mermaid.ink 警告 ({jpg_file.name}): JPEG でない応答を受け取りました",
            file=sys.stderr,
        )
        return False
    jpg_file.write_bytes(data)
    return True


def _render_mermaid_mmdc(mmd_file: Path, png_file: Path) -> bool:
    """@mermaid-js/mermaid-cli（mmdc）で PNG を生成する."""
    if not shutil.which("mmdc"):
        return False
    try:
        result = subprocess.run(
            [
                "mmdc",
                "-i", str(mmd_file),
                "-o", str(png_file),
                "-b", "white",
                "-w", "1600",
                "-s", "3",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return False

    if result.returncode == 0 and png_file.exists() and png_file.stat().st_size > 0:
        return True
    err = (result.stderr or result.stdout or "").strip()
    if len(err) > 400:
        err = err[:400] + "…"
    print(f"  mmdc 警告 ({png_file.stem}): {err}", file=sys.stderr)
    return False


def _render_mermaid(source: str, build_dir: Path) -> str | None:
    """Mermaid を画像化。mmdc → mermaid.ink → Kroki の順で試す."""
    global _mermaid_counter
    idx = _mermaid_counter
    _mermaid_counter += 1

    mmd_file = build_dir / f"mermaid_{idx}.mmd"
    png_file = build_dir / f"mermaid_{idx}.png"
    mmd_file.write_text(source, encoding="utf-8")

    if _render_mermaid_mmdc(mmd_file, png_file):
        return f"mermaid_{idx}.png"

    if png_file.exists():
        try:
            png_file.unlink()
        except OSError:
            pass

    jpg_file = build_dir / f"mermaid_{idx}.jpg"
    if jpg_file.exists():
        try:
            jpg_file.unlink()
        except OSError:
            pass
    if _render_mermaid_ink(source, jpg_file):
        return f"mermaid_{idx}.jpg"

    if _render_mermaid_kroki(source, png_file):
        return f"mermaid_{idx}.png"

    return None


# ---------------------------------------------------------------------------
# Block-level Markdown → LaTeX
# ---------------------------------------------------------------------------

def _close_list(stack: list[str]) -> list[str]:
    return [
        r"\end{itemize}" if t == "ul" else r"\end{enumerate}"
        for t in reversed(stack)
    ]


def markdown_to_latex(md: str, build_dir: Path | None = None) -> str:
    lines = md.split("\n")
    out: list[str] = []

    i = 0
    in_code = False
    code_lang = ""
    code_buf: list[str] = []

    in_list = False
    list_stack: list[str] = []

    in_quote = False
    table_buf: list[str] = []

    def _flush_envs():
        nonlocal in_list, list_stack, in_quote
        if in_list:
            out.extend(_close_list(list_stack))
            in_list = False
            list_stack = []
        if in_quote:
            out.append(r"\end{quote}")
            in_quote = False

    while i < len(lines):
        line = lines[i]

        # ---- code fence ----
        if line.strip().startswith("```"):
            if not in_code:
                _flush_envs()
                if table_buf:
                    out.extend(_convert_table(table_buf))
                    table_buf = []
                in_code = True
                code_lang = line.strip()[3:].strip()
                code_buf = []
                i += 1
                continue
            else:
                in_code = False
                fence_lang = (
                    code_lang.strip().split()[0].lower()
                    if code_lang.strip()
                    else ""
                )
                if fence_lang == "mermaid" and build_dir is not None:
                    mmd_src = "\n".join(code_buf)
                    img = _render_mermaid(mmd_src, build_dir)
                    if img:
                        out.append(r"\begin{center}")
                        out.append(
                            r"\adjustbox{max width=\textwidth}"
                            r"{\includegraphics{" + img + "}}"
                        )
                        out.append(r"\end{center}")
                    else:
                        out.append(r"\begin{quote}")
                        out.append(r"\begin{verbatim}")
                        out.extend(code_buf)
                        out.append(r"\end{verbatim}")
                        out.append(r"\end{quote}")
                else:
                    out.append(r"\begin{quote}")
                    out.append(r"\begin{verbatim}")
                    out.extend(code_buf)
                    out.append(r"\end{verbatim}")
                    out.append(r"\end{quote}")
                code_lang = ""
                code_buf = []
                i += 1
                continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # ---- flush table if current line is not a table row ----
        if table_buf and not _is_table_line(line):
            out.extend(_convert_table(table_buf))
            table_buf = []

        # ---- table row ----
        if _is_table_line(line):
            if not table_buf:
                _flush_envs()
            table_buf.append(line)
            i += 1
            continue

        # ---- blank line ----
        if line.strip() == "":
            if in_quote:
                out.append(r"\end{quote}")
                in_quote = False
            if in_list:
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                if not (
                    re.match(r"^\s*[-*]\s", nxt)
                    or re.match(r"^\s*\d+\.\s", nxt)
                ):
                    out.extend(_close_list(list_stack))
                    in_list = False
                    list_stack = []
            out.append("")
            i += 1
            continue

        # ---- heading ----
        hm = re.match(r"^(#{1,4})\s+(.*)", line)
        if hm:
            _flush_envs()
            level = len(hm.group(1))
            raw_title = hm.group(2)
            # Wiki 閲覧用の ## [ch] … を PDF では番号なしタイトルに正規化（LaTeX の section 番号を使う）
            if level == 2 and raw_title.startswith("[ch] "):
                raw_title = raw_title[5:]
            title = process_inline(raw_title)
            cmd = {1: "section", 2: "section", 3: "subsection", 4: "subsubsection"}
            out.append(f"\\{cmd[level]}{{{title}}}")
            i += 1
            continue

        # ---- blockquote ----
        if line.lstrip().startswith(">"):
            if in_list:
                out.extend(_close_list(list_stack))
                in_list = False
                list_stack = []
            if not in_quote:
                in_quote = True
                out.append(r"\begin{quote}")
            content = re.sub(r"^>\s?", "", line.strip())
            if content:
                out.append(process_inline(content))
            i += 1
            continue

        if in_quote:
            out.append(r"\end{quote}")
            in_quote = False

        # ---- unordered list ----
        ul = re.match(r"^(\s*)[-*]\s+(.*)", line)
        if ul:
            if not in_list:
                in_list = True
                list_stack = ["ul"]
                out.append(r"\begin{itemize}")
            out.append(r"\item " + process_inline(ul.group(2)))
            i += 1
            continue

        # ---- ordered list ----
        ol = re.match(r"^(\s*)\d+\.\s+(.*)", line)
        if ol:
            if not in_list:
                in_list = True
                list_stack = ["ol"]
                out.append(r"\begin{enumerate}")
            out.append(r"\item " + process_inline(ol.group(2)))
            i += 1
            continue

        # ---- paragraph text ----
        out.append(process_inline(line))
        i += 1

    # flush remaining
    if table_buf:
        out.extend(_convert_table(table_buf))
    _flush_envs()

    return "\n".join(out)


# ---------------------------------------------------------------------------
# LaTeX document generation
# ---------------------------------------------------------------------------

def generate_document(
    title: str,
    body: str,
    date_info: str,
    fonts: dict[str, str],
    author_info: str = "",
) -> str:
    return (
        r"\documentclass[a4paper,11pt]{article}"
        "\n"
        r"\usepackage{xeCJK}"
        "\n"
        r"\usepackage{fontspec}"
        "\n"
        rf'\setCJKmainfont{{{fonts["main"]}}}'
        "\n"
        rf'\setCJKsansfont{{{fonts["sans"]}}}'
        "\n"
        rf'\setCJKmonofont{{{fonts["mono"]}}}'
        "\n\n"
        r"\usepackage[margin=25mm]{geometry}"
        "\n"
        r"\usepackage{float}"
        "\n"
        r"\usepackage{xcolor}"
        "\n"
        r"\usepackage{graphicx}"
        "\n"
        r"\usepackage{adjustbox}"
        "\n"
        r"\usepackage{enumitem}"
        "\n"
        r"\usepackage{hyperref}"
        "\n"
        r"\hypersetup{"
        "\n"
        r"  colorlinks=true,"
        "\n"
        r"  linkcolor=blue!70!black,"
        "\n"
        r"  urlcolor=blue!70!black,"
        "\n"
        r"}"
        "\n\n"
        r"\setlength{\parindent}{0pt}"
        "\n"
        r"\setlength{\parskip}{6pt}"
        "\n\n"
        rf"\title{{{escape_latex(title)}}}"
        "\n"
        rf"\author{{{author_info}}}"
        "\n"
        rf"\date{{{escape_latex(date_info)}}}"
        "\n\n"
        r"\begin{document}"
        "\n"
        r"\maketitle"
        "\n"
        r"\tableofcontents"
        "\n"
        r"\newpage"
        "\n\n"
        f"{body}"
        "\n\n"
        r"\end{document}"
        "\n"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Markdown → LaTeX → PDF (tectonic)",
    )
    parser.add_argument("markdown", nargs="?", help="Markdownファイルのパス")
    args = parser.parse_args()

    md_path = Path(
        args.markdown
        or os.environ.get("PATH_MARKDOWN", DEFAULT_MARKDOWN)
    )
    build_dir = Path(os.environ.get("PATH_BUILD", DEFAULT_BUILD_DIR))

    if not md_path.exists():
        print(f"エラー: ファイルが見つかりません: {md_path}", file=sys.stderr)
        sys.exit(1)

    if not shutil.which("tectonic"):
        print(
            "エラー: tectonic がインストールされていません\n"
            "  brew install tectonic  または  cargo install tectonic",
            file=sys.stderr,
        )
        sys.exit(1)

    build_dir.mkdir(parents=True, exist_ok=True)

    print(f"読み込み: {md_path}")
    md_text = md_path.read_text(encoding="utf-8")

    # --- メタデータ抽出 ---
    title_m = re.match(r"^#\s+(.*)", md_text, re.MULTILINE)
    title = title_m.group(1) if title_m else md_path.stem

    parts: list[str] = []
    cd = re.search(r"作成日時:\s*(\S+\s+\S+)", md_text)
    ud = re.search(r"更新日時:\s*(\S+\s+\S+)", md_text)
    if cd:
        parts.append(f"作成: {cd.group(1)}")
    if ud:
        parts.append(f"更新: {ud.group(1)}")
    date_info = "　/　".join(parts)

    # --- 作者欄（文責・Contact）: タイトル用にまとめ、本文では日時と同様に除去 ---
    author_lines: list[str] = []
    am = re.search(r"^(文責:\s*.+)$", md_text, re.MULTILINE)
    if am:
        author_lines.append(am.group(1).strip())
    cm = re.search(r"^(Contact\s*(?:email)?\s*:.+)$", md_text, re.MULTILINE | re.IGNORECASE)
    if cm:
        author_lines.append(cm.group(1).strip())
    author_info = (
        r" \\ ".join(escape_latex(line) for line in author_lines) if author_lines else ""
    )

    # --- 本文からタイトル行と日時行を除去 ---
    body = md_text
    body = re.sub(r"^#\s+.*\n?", "", body, count=1)
    body = re.sub(r"^作成日時:.*\n?", "", body, flags=re.MULTILINE)
    body = re.sub(r"^更新日時:.*\n?", "", body, flags=re.MULTILINE)
    body = re.sub(r"^文責:.*\n?", "", body, flags=re.MULTILINE)
    body = re.sub(
        r"^Contact\s*(?:email)?\s*:.*\n?",
        "",
        body,
        flags=re.MULTILINE | re.IGNORECASE,
    )

    # --- 変換 ---
    print("Markdown → LaTeX 変換中...")
    global _mermaid_counter
    _mermaid_counter = 0
    latex_body = markdown_to_latex(body, build_dir)
    fonts = get_cjk_fonts()
    latex_doc = generate_document(title, latex_body, date_info, fonts, author_info)

    tex_path = build_dir / (md_path.stem + ".tex")
    tex_path.write_text(latex_doc, encoding="utf-8")
    print(f"LaTeX 出力: {tex_path}")

    # --- tectonic ビルド ---
    print("tectonic で PDF ビルド中...")
    result = subprocess.run(
        ["tectonic", str(tex_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("tectonic エラー:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        if result.stdout:
            print(result.stdout)
        sys.exit(result.returncode)

    pdf_path = build_dir / (md_path.stem + ".pdf")
    if pdf_path.exists():
        print(f"PDF 生成完了: {pdf_path}")
    else:
        print(f"PDF が見つかりません: {pdf_path}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
