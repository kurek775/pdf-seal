"""
What these tests are actually guarding.

The whole point of this tool is a negative property: after sealing, the document
still has every link and every bookmark it had before, and looks identical. That
property is easy to break by swapping in a different PDF library, so the tests
assert it directly on a document built to carry exactly those features.

Tests that need an outside binary skip themselves when it is missing, so the suite
still runs somewhere with only qpdf installed. CI installs all of them, so nothing
is silently skipped there.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixtures import pdf_with_navigation, pdf_without_navigation  # noqa: E402

import seal  # noqa: E402

HAS_QPDF = shutil.which('qpdf') is not None
HAS_PDFTOTEXT = shutil.which('pdftotext') is not None
HAS_GS = shutil.which('gs') is not None


class TempPdfCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.source = self.dir / 'source.pdf'
        self.source.write_bytes(pdf_with_navigation())
        self.addCleanup(self._tmp.cleanup)


class TextHandling(unittest.TestCase):
    """Pure functions, no qpdf needed."""

    def test_accents_are_stripped(self) -> None:
        self.assertEqual(seal.strip_accents('Šárka Kvašňáková'), 'Sarka Kvasnakova')
        self.assertEqual(seal.strip_accents('Hájková'), 'Hajkova')

    def test_ascii_is_left_alone(self) -> None:
        self.assertEqual(seal.strip_accents('jane@example.com'), 'jane@example.com')

    def test_parentheses_and_backslashes_are_escaped(self) -> None:
        # Unescaped, these would end the PDF string early and corrupt the file.
        self.assertEqual(seal.pdf_string('a(b)c'), rb'a\(b\)c')
        self.assertEqual(seal.pdf_string('a\\b'), rb'a\\b')

    def test_template_uses_csv_columns(self) -> None:
        row = {'name': 'Jane', 'email': 'jane@example.com'}
        self.assertEqual(
            seal.render_template('{name} <{email}>', row), 'Jane <jane@example.com>'
        )

    def test_unknown_column_fails_loudly(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            seal.render_template('{missing}', {'name': 'Jane'})
        self.assertIn('missing', str(caught.exception))


@unittest.skipUnless(HAS_QPDF, 'qpdf is not installed')
class Sealing(TempPdfCase):
    def test_fixture_really_has_something_to_lose(self) -> None:
        # If this fails the other tests prove nothing: they would be asserting
        # that zero links survived.
        counts = seal.count_navigation(self.source)
        self.assertGreater(counts['links'], 0)
        self.assertGreater(counts['jumps'], 0)
        self.assertGreater(counts['bookmarks'], 0)

    def test_links_and_bookmarks_survive(self) -> None:
        before = seal.count_navigation(self.source)
        target = self.dir / 'sealed.pdf'
        seal.seal(self.source, target, 'Jane Doe | jane@example.com', visible=False)
        self.assertEqual(seal.count_navigation(target), before)

    def test_visible_seal_also_keeps_them(self) -> None:
        before = seal.count_navigation(self.source)
        target = self.dir / 'visible.pdf'
        seal.seal(self.source, target, 'Jane Doe', visible=True)
        self.assertEqual(seal.count_navigation(target), before)

    def test_page_count_is_unchanged(self) -> None:
        target = self.dir / 'sealed.pdf'
        seal.seal(self.source, target, 'Jane Doe', visible=False)
        pages = subprocess.run(
            ['qpdf', '--show-npages', str(target)], capture_output=True, text=True
        ).stdout.strip()
        self.assertEqual(pages, '2')

    def test_document_without_navigation_is_handled(self) -> None:
        plain = self.dir / 'plain.pdf'
        plain.write_bytes(pdf_without_navigation())
        target = self.dir / 'plain-sealed.pdf'
        seal.seal(plain, target, 'Jane Doe', visible=False)
        self.assertTrue(target.is_file())

    def test_page_size_is_read_from_the_source(self) -> None:
        width, height = seal.page_size(self.source)
        self.assertAlmostEqual(width, 200, places=1)
        self.assertAlmostEqual(height, 200, places=1)


@unittest.skipUnless(HAS_QPDF and HAS_PDFTOTEXT, 'needs qpdf and pdftotext')
class SealIsReadable(TempPdfCase):
    def _text_of(self, pdf: Path, page: int) -> str:
        return subprocess.run(
            ['pdftotext', '-f', str(page), '-l', str(page), str(pdf), '-'],
            capture_output=True,
            text=True,
        ).stdout

    def test_seal_lands_on_every_page(self) -> None:
        target = self.dir / 'sealed.pdf'
        seal.seal(self.source, target, 'Jane Doe | jane@example.com', visible=False)
        for page in (1, 2):
            self.assertIn(
                'jane@example.com',
                self._text_of(target, page),
                f'seal missing from page {page}',
            )

    def test_accented_name_is_readable_without_accents(self) -> None:
        target = self.dir / 'accented.pdf'
        seal.seal(self.source, target, 'Šárka Melicharová | s@example.com', visible=False)
        self.assertIn('Sarka Melicharova', self._text_of(target, 1))


@unittest.skipUnless(HAS_QPDF and HAS_GS, 'needs qpdf and ghostscript')
class InvisibleMeansInvisible(TempPdfCase):
    def _render(self, pdf: Path, out: Path) -> bytes:
        subprocess.run(
            [
                'gs',
                '-q',
                '-dNOPAUSE',
                '-dBATCH',
                '-sDEVICE=png16m',
                '-r36',
                '-dFirstPage=1',
                '-dLastPage=1',
                f'-sOutputFile={out}',
                str(pdf),
            ],
            capture_output=True,
        )
        return out.read_bytes()

    def test_invisible_seal_changes_no_pixel(self) -> None:
        target = self.dir / 'sealed.pdf'
        seal.seal(self.source, target, 'Jane Doe | jane@example.com', visible=False)
        self.assertEqual(
            self._render(target, self.dir / 'after.png'),
            self._render(self.source, self.dir / 'before.png'),
        )

    def test_visible_seal_does_change_pixels(self) -> None:
        # The counterpart: proves the comparison above can actually fail.
        target = self.dir / 'visible.pdf'
        seal.seal(self.source, target, 'Jane Doe', visible=True)
        self.assertNotEqual(
            self._render(target, self.dir / 'after.png'),
            self._render(self.source, self.dir / 'before.png'),
        )


@unittest.skipUnless(HAS_QPDF, 'qpdf is not installed')
class CommandLine(TempPdfCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        script = Path(__file__).resolve().parent.parent / 'seal.py'
        return subprocess.run(
            [sys.executable, str(script), *args], capture_output=True, text=True
        )

    def test_single_file_with_verify_succeeds(self) -> None:
        done = self._run(
            str(self.source),
            '--text',
            'Jane Doe',
            '--out',
            str(self.dir / 'out.pdf'),
            '--verify',
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('came through unchanged', done.stdout)

    def test_batch_writes_one_file_per_row(self) -> None:
        csv_path = self.dir / 'buyers.csv'
        csv_path.write_text(
            'name,email,order\n'
            'Jane Doe,jane@example.com,71\n'
            'Šárka Melicharová,sarka@example.com,42\n',
            encoding='utf-8',
        )
        outdir = self.dir / 'sealed'
        done = self._run(
            str(self.source),
            '--csv',
            str(csv_path),
            '--template',
            '{name} | {email} | order {order}',
            '--outdir',
            str(outdir),
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(
            sorted(p.name for p in outdir.glob('*.pdf')),
            ['jane@example.com.pdf', 'sarka@example.com.pdf'],
        )

    def test_text_and_csv_together_are_refused(self) -> None:
        done = self._run(str(self.source), '--text', 'x', '--csv', 'y.csv')
        self.assertNotEqual(done.returncode, 0)
        self.assertIn('either --text', done.stderr)

    def test_missing_input_is_reported(self) -> None:
        done = self._run(str(self.dir / 'nope.pdf'), '--text', 'x')
        self.assertNotEqual(done.returncode, 0)
        self.assertIn('No such file', done.stderr)


if __name__ == '__main__':
    unittest.main()
