# -*- coding: utf-8 -*-
"""`docs/nasil-calisir.md` dosyasını yazdırılabilir HTML ve PDF'e çevirir.

Ek bağımlılık kullanmaz: Markdown'ı kendi içinde dönüştürür ve PDF üretimi için
sistemde zaten kurulu olan Edge/Chrome'un headless yazdırma özelliğini çağırır.

Kullanım:
    python scripts/build_docs_pdf.py
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "nasil-calisir.md"
HTML_OUT = ROOT / "docs" / "HealthScope-Nasil-Calisir.html"
PDF_OUT = ROOT / "docs" / "HealthScope-Nasil-Calisir.pdf"

CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
body {
  font-family: "Segoe UI", "Inter", system-ui, sans-serif;
  font-size: 10.5pt; line-height: 1.6; color: #14181d; margin: 0;
  padding: 18mm 16mm;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1 { font-size: 22pt; margin: 0 0 4pt; letter-spacing: -0.4pt; }
h2 {
  font-size: 14pt; margin: 22pt 0 8pt; padding-bottom: 4pt;
  border-bottom: 1.5px solid #14618f; color: #14618f;
  break-after: avoid;
}
h3 { font-size: 11.5pt; margin: 14pt 0 5pt; color: #223; break-after: avoid; }
p { margin: 0 0 8pt; }
ul, ol { margin: 0 0 8pt; padding-left: 18pt; }
li { margin-bottom: 3pt; }
hr { border: none; border-top: 1px solid #d8dee6; margin: 16pt 0; }
code {
  font-family: Consolas, "Cascadia Mono", monospace; font-size: 9pt;
  background: #f2f5f8; padding: 1pt 3pt; border-radius: 2px;
}
pre {
  background: #f6f8fa; border: 1px solid #dde3ea; border-radius: 4px;
  padding: 9pt 11pt; font-family: Consolas, monospace; font-size: 8.6pt;
  line-height: 1.45; overflow-x: auto; white-space: pre-wrap;
  break-inside: avoid; margin: 0 0 10pt;
}
pre code { background: none; padding: 0; font-size: inherit; }
table {
  width: 100%; border-collapse: collapse; margin: 0 0 12pt;
  font-size: 9.4pt; break-inside: avoid;
}
th, td { border: 1px solid #d8dee6; padding: 4.5pt 7pt; text-align: left; vertical-align: top; }
th { background: #eef2f6; font-weight: 600; }
blockquote {
  margin: 0 0 10pt; padding: 8pt 12pt; background: #fdf6e8;
  border-left: 3px solid #c8952f; break-inside: avoid;
}
blockquote p:last-child { margin-bottom: 0; }
strong { font-weight: 600; }
.cover { margin-bottom: 18pt; }
.cover .sub { color: #5a6472; font-size: 11pt; margin-top: 2pt; }
.meta { color: #7a8492; font-size: 8.5pt; margin-top: 6pt; }
"""


def convert(markdown: str) -> str:
    """Bu belge için yeterli, küçük bir Markdown dönüştürücü."""
    lines = markdown.split("\n")
    out: list[str] = []
    in_code = False
    in_table = False
    in_quote = False
    list_stack: list[str] = []
    #: Ardışık metin satırları tek paragrafta birleştirilir (Markdown davranışı).
    para: list[str] = []
    quote: list[str] = []

    def close_list() -> None:
        while list_stack:
            out.append(f"</{list_stack.pop()}>")

    def flush_para() -> None:
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    def close_quote() -> None:
        nonlocal in_quote
        if quote:
            out.append(f"<p>{inline(' '.join(quote))}</p>")
            quote.clear()
        if in_quote:
            out.append("</blockquote>")
            in_quote = False

    def close_table() -> None:
        nonlocal in_table
        if in_table:
            out.append("</tbody></table>")
            in_table = False

    def inline(text: str) -> str:
        text = html.escape(text)
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
        return text

    for raw in lines:
        line = raw.rstrip()

        if line.startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                flush_para(); close_list(); close_quote(); close_table()
                out.append("<pre><code>")
                in_code = True
            continue

        if in_code:
            out.append(html.escape(raw))
            continue

        if not line.strip():
            flush_para(); close_list(); close_quote(); close_table()
            continue

        # Tablo
        if line.lstrip().startswith("|"):
            flush_para()
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") and c for c in cells):
                continue  # hizalama satırı
            if not in_table:
                close_list(); close_quote()
                out.append("<table><thead><tr>")
                out.extend(f"<th>{inline(c)}</th>" for c in cells)
                out.append("</tr></thead><tbody>")
                in_table = True
            else:
                out.append("<tr>")
                out.extend(f"<td>{inline(c)}</td>" for c in cells)
                out.append("</tr>")
            continue
        close_table()

        if line.startswith("> "):
            if not in_quote:
                flush_para(); close_list()
                out.append("<blockquote>")
                in_quote = True
            quote.append(line[2:])
            continue
        if line.strip() == ">":
            if quote:
                out.append(f"<p>{inline(' '.join(quote))}</p>")
                quote.clear()
            continue
        close_quote()

        if line.startswith("### "):
            flush_para(); close_list(); out.append(f"<h3>{inline(line[4:])}</h3>"); continue
        if line.startswith("## "):
            flush_para(); close_list(); out.append(f"<h2>{inline(line[3:])}</h2>"); continue
        if line.startswith("# "):
            flush_para(); close_list(); out.append(f"<h1>{inline(line[2:])}</h1>"); continue
        if line.startswith("---"):
            flush_para(); close_list(); out.append("<hr>"); continue

        bullet = re.match(r"^(\s*)-\s+(.*)$", line)
        if bullet:
            flush_para()
            if not list_stack:
                out.append("<ul>"); list_stack.append("ul")
            out.append(f"<li>{inline(bullet.group(2))}</li>")
            continue

        numbered = re.match(r"^(\s*)\d+\.\s+(.*)$", line)
        if numbered:
            flush_para()
            if not list_stack:
                out.append("<ol>"); list_stack.append("ol")
            out.append(f"<li>{inline(numbered.group(2))}</li>")
            continue

        close_list()
        para.append(line)

    flush_para(); close_list(); close_quote(); close_table()
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def find_browser() -> str | None:
    """Headless yazdırma için Edge veya Chrome arar."""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    for name in ("msedge", "chrome", "chromium"):
        found = shutil.which(name)
        if found:
            return found
    return None


def main() -> int:
    if not SOURCE.exists():
        print(f"HATA: {SOURCE} bulunamadı.")
        return 1

    body = convert(SOURCE.read_text(encoding="utf-8"))
    document = (
        "<!doctype html><html lang='tr'><head><meta charset='utf-8'>"
        "<title>HealthScope — Sistem Dokümantasyonu</title>"
        f"<style>{CSS}</style></head><body>{body}</body></html>"
    )
    HTML_OUT.write_text(document, encoding="utf-8")
    print(f"HTML  : {HTML_OUT.name}  ({HTML_OUT.stat().st_size // 1024} KB)")

    browser = find_browser()
    if not browser:
        print("UYARI: Edge/Chrome bulunamadı; PDF üretilemedi.")
        print(f"       {HTML_OUT.name} dosyasını tarayıcıda açıp Ctrl+P ile PDF'e yazdırabilirsiniz.")
        return 0

    result = subprocess.run(
        [
            browser, "--headless=new", "--disable-gpu", "--no-sandbox",
            f"--print-to-pdf={PDF_OUT}", "--print-to-pdf-no-header",
            HTML_OUT.as_uri(),
        ],
        capture_output=True, timeout=180,
    )
    if PDF_OUT.exists() and PDF_OUT.stat().st_size > 0:
        print(f"PDF   : {PDF_OUT.name}  ({PDF_OUT.stat().st_size // 1024} KB)")
        return 0

    print("HATA: PDF üretilemedi.")
    print((result.stderr or b"").decode("utf-8", "replace")[:400])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
