"""
A minimal PDF built by hand, carrying exactly the things a seal must not destroy:
a link annotation with an in-document jump, and one outline entry.

It is generated rather than committed as a binary so the fixture can be read,
reviewed in a diff, and adjusted without a PDF editor.
"""

from __future__ import annotations


def _assemble(objects: list[bytes]) -> bytes:
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


def pdf_with_navigation(width: int = 200, height: int = 200) -> bytes:
    """Two pages; page one links to page two, and one bookmark points there too."""
    content = b'BT /F1 12 Tf 20 100 Td (page) Tj ET\n'
    return _assemble(
        [
            b'<< /Type /Catalog /Pages 2 0 R /Outlines 6 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>',
            (
                f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] '
                f'/Resources << /Font << /F1 9 0 R >> >> /Contents 5 0 R '
                f'/Annots [8 0 R] >>'
            ).encode(),
            (
                f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] '
                f'/Resources << /Font << /F1 9 0 R >> >> /Contents 5 0 R >>'
            ).encode(),
            b'<< /Length '
            + str(len(content)).encode()
            + b' >>\nstream\n'
            + content
            + b'endstream',
            b'<< /Type /Outlines /First 7 0 R /Last 7 0 R /Count 1 >>',
            b'<< /Title (Chapter one) /Parent 6 0 R /Dest [4 0 R /Fit] >>',
            b'<< /Type /Annot /Subtype /Link /Rect [10 10 100 30] /Border [0 0 0] '
            b'/A << /S /GoTo /D [4 0 R /Fit] >> >>',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        ]
    )


def pdf_without_navigation(width: int = 200, height: int = 200) -> bytes:
    """One plain page. Nothing to preserve, nothing to lose."""
    content = b'BT /F1 12 Tf 20 100 Td (plain) Tj ET\n'
    return _assemble(
        [
            b'<< /Type /Catalog /Pages 2 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            (
                f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] '
                f'/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>'
            ).encode(),
            b'<< /Length '
            + str(len(content)).encode()
            + b' >>\nstream\n'
            + content
            + b'endstream',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        ]
    )
