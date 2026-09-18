#!/usr/bin/env python3
"""
Seal a PDF with buyer details without breaking its links.

Ordinary stamping tools push the file through a rendering library that rebuilds
it page by page. That drops annotations and the outline tree, so links from the
table of contents, web links and bookmarks all disappear. For an e-book with a
clickable table of contents the result is several hundred pages you can only
scroll through.

This tool takes a different route: it builds a one-page PDF carrying nothing but
the seal text and lays it over every page with `qpdf --overlay`, which merges
page content streams only and leaves annotations and the outline untouched.

By default the seal is invisible. The text is written in text rendering mode
`3 Tr`, which the PDF specification defines as invisible: nothing shows on screen
or in print, yet the text is in the file and can be extracted with `pdftotext`.
That makes this a forensic marker rather than a deterrent -- someone who does not
know the seal is there will not be discouraged from sharing the file. Pass
--visible to add a small grey footer line that does discourage it.

Requires nothing but `qpdf` on PATH. No Python packages to install.

Usage:
    seal.py book.pdf --text "Jane Doe | jane@example.com | order 71"
    seal.py book.pdf --csv buyers.csv --template "{name} | {email} | order {order}"
    seal.py book.pdf --text "..." --visible --verify

MIT licensed.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path


# Helvetica only speaks WinAnsi, which has no c-caron, r-caron, s-caron and the
# rest of the Czech set. Accents are therefore stripped from the seal text:
# "Sarka Kvasnakova" instead of the accented spelling. The identifiers that
# actually matter for tracing -- the e-mail address and the order number -- are
# plain ASCII anyway.
def strip_accents(text: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)
    )


def pdf_string(text: str) -> bytes:
    text = strip_accents(text)
    for old, new in (('\\', r'\\'), ('(', r'\('), (')', r'\)')):
        text = text.replace(old, new)
    return text.encode('latin-1', 'replace')


def build_seal_pdf(text: str, width: float, height: float, visible: bool) -> bytes:
    """A one-page PDF carrying nothing but the seal text."""
    lines = [b'BT', b'/F1 7 Tf']
    lines += [b'0.6 0.6 0.6 rg'] if visible else [b'3 Tr']
    lines += [b'36 22 Td', b'(' + pdf_string(text) + b') Tj', b'ET']
    content = b'\n'.join(lines) + b'\n'

    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        (
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:g} {height:g}] '
            f'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>'
        ).encode(),
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
        b'<< /Length ' + str(len(content)).encode() + b' >>\nstream\n' + content + b'endstream',
    ]

    out = bytearray(b'%PDF-1.4\n')
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f'{number} 0 obj\n'.encode() + body + b'\nendobj\n'
    xref_at = len(out)
    out += f'xref\n0 {len(objects) + 1}\n'.encode() + b'0000000000 65535 f \n'
    for offset in offsets:
        out += f'{offset:010d} 00000 n \n'.encode()
    out += (
        f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n'
    ).encode()
    return bytes(out)


def to_qdf(pdf: Path, target: Path) -> None:
    """Expand a PDF into qpdf's uncompressed form so it can be inspected."""
    subprocess.run(
        [
            'qpdf',
            '--qdf',
            '--object-streams=disable',
            '--decode-level=none',
            str(pdf),
            str(target),
        ],
        capture_output=True,
    )


def page_size(pdf: Path) -> tuple[float, float]:
    """First page size, via pdfinfo when available, else from /MediaBox."""
    if shutil.which('pdfinfo'):
        output = subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True).stdout
        found = re.search(r'Page size:\s+([\d.]+) x ([\d.]+)', output)
        if found:
            return float(found.group(1)), float(found.group(2))

    with tempfile.TemporaryDirectory() as tmp:
        expanded = Path(tmp) / 'expanded.pdf'
        to_qdf(pdf, expanded)
        found = re.search(
            rb'/MediaBox\s*\[\s*([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)\s+([\d.-]+)',
            expanded.read_bytes(),
        )
    if not found:
        raise SystemExit('Could not determine the page size.')
    x0, y0, x1, y1 = (float(found.group(i)) for i in range(1, 5))
    return x1 - x0, y1 - y0


def count_navigation(pdf: Path) -> dict[str, int]:
    """Links, in-document jumps and bookmarks, for before/after comparison."""
    with tempfile.TemporaryDirectory() as tmp:
        expanded = Path(tmp) / 'expanded.pdf'
        to_qdf(pdf, expanded)
        data = expanded.read_bytes()
    return {
        'links': data.count(b'/Subtype /Link'),
        'jumps': data.count(b'/S /GoTo'),
        'web': data.count(b'/S /URI'),
        'bookmarks': data.count(b'/Title'),
    }


def seal(source: Path, target: Path, text: str, visible: bool) -> None:
    width, height = page_size(source)
    with tempfile.TemporaryDirectory() as tmp:
        stamp = Path(tmp) / 'stamp.pdf'
        stamp.write_bytes(build_seal_pdf(text, width, height, visible))
        done = subprocess.run(
            ['qpdf', str(source), '--overlay', str(stamp), '--repeat=1', '--', str(target)],
            capture_output=True,
            text=True,
        )
    # qpdf exits 3 on warnings that are not failures; a real failure is 2.
    if done.returncode not in (0, 3):
        raise SystemExit(f'qpdf failed: {done.stderr.strip()}')


def render_template(template: str, row: dict[str, str]) -> str:
    try:
        return template.format(**row)
    except KeyError as missing:
        raise SystemExit(
            f'Template uses column {missing}, which the CSV does not have. '
            f'Columns: {", ".join(row)}'
        ) from None


def describe(label: str, counts: dict[str, int]) -> str:
    return (
        f'{label:6} links {counts["links"]}, jumps {counts["jumps"]}, '
        f'web {counts["web"]}, bookmarks {counts["bookmarks"]}'
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Seal a PDF with buyer details without breaking links or bookmarks.'
    )
    parser.add_argument('pdf', type=Path, help='the PDF to seal')
    parser.add_argument('--text', help='seal text, for a single file')
    parser.add_argument('--csv', type=Path, help='CSV of buyers; one sealed file per row')
    parser.add_argument(
        '--template',
        default='{name} | {email}',
        help='how to build the seal text from CSV columns',
    )
    parser.add_argument(
        '--filename', default='{email}.pdf', help='how to name each file of a batch'
    )
    parser.add_argument('--out', type=Path, help='output file, for a single PDF')
    parser.add_argument(
        '--outdir', type=Path, default=Path('sealed'), help='where a batch is written'
    )
    parser.add_argument(
        '--visible', action='store_true', help='also seal visibly, as a small grey footer line'
    )
    parser.add_argument(
        '--verify', action='store_true', help='count links and bookmarks before and after'
    )
    args = parser.parse_args()

    if not shutil.which('qpdf'):
        raise SystemExit('qpdf is missing. Install it: apt install qpdf / brew install qpdf')
    if not args.pdf.is_file():
        raise SystemExit(f'No such file: {args.pdf}')
    if bool(args.text) == bool(args.csv):
        raise SystemExit('Pass either --text (one file) or --csv (a batch).')

    before = count_navigation(args.pdf) if args.verify else None
    if before:
        print(describe('before', before))

    if args.text:
        target = args.out or args.pdf.with_name(args.pdf.stem + '-sealed.pdf')
        seal(args.pdf, target, args.text, args.visible)
        print(f'✓ {target}')
        written = [target]
    else:
        args.outdir.mkdir(parents=True, exist_ok=True)
        written = []
        with args.csv.open(encoding='utf-8-sig', newline='') as handle:
            for row in csv.DictReader(handle):
                row = {k: (v or '').strip() for k, v in row.items() if k}
                name = strip_accents(render_template(args.filename, row))
                target = args.outdir / re.sub(r'[^A-Za-z0-9._@-]', '_', name)
                seal(args.pdf, target, render_template(args.template, row), args.visible)
                print(f'✓ {target}')
                written.append(target)
        print(f'\n{len(written)} files written to {args.outdir}')

    if before:
        after = count_navigation(written[0])
        print(describe('after', after))
        if after == before:
            print('✓ links and bookmarks came through unchanged')
        else:
            print('✗ counts differ, something was lost along the way')
            sys.exit(1)


if __name__ == '__main__':
    main()
