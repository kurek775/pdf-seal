"""
The server is thin on purpose -- the sealing itself is already covered in
test_seal.py -- so these tests aim at what a browser can throw at it: a file that
is not a PDF, an upload id that has gone, an id crafted to walk out of the upload
directory, and a batch that has to come back as a zip.
"""

from __future__ import annotations

import json
import shutil
import sys
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixtures import pdf_with_navigation  # noqa: E402

import server  # noqa: E402

HAS_QPDF = shutil.which('qpdf') is not None


def post(url: str, body: bytes, content_type: str) -> tuple[int, bytes, str]:
    request = urllib.request.Request(url, data=body, method='POST')
    request.add_header('Content-Type', content_type)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read(), response.headers.get('Content-Type', '')
    except urllib.error.HTTPError as err:
        return err.code, err.read(), err.headers.get('Content-Type', '')


@unittest.skipUnless(HAS_QPDF, 'qpdf is not installed')
class ServerApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # The handler narrates every request; during a test run that buries the
        # result the suite is actually reporting.
        cls._logger = server.Handler.log_message
        server.Handler.log_message = lambda *args, **kwargs: None
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.base = f'http://127.0.0.1:{cls.httpd.server_address[1]}'
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        server.Handler.log_message = cls._logger

    def upload(self) -> dict:
        status, body, _ = post(
            f'{self.base}/api/upload', pdf_with_navigation(), 'application/pdf'
        )
        self.assertEqual(status, 200, body)
        return json.loads(body)

    def test_upload_reports_what_is_at_stake(self) -> None:
        answer = self.upload()
        self.assertEqual(answer['pages'], 2)
        self.assertGreater(answer['counts']['links'], 0)
        self.assertGreater(answer['counts']['bookmarks'], 0)

    def test_a_non_pdf_is_refused(self) -> None:
        status, body, _ = post(f'{self.base}/api/upload', b'hello', 'application/pdf')
        self.assertEqual(status, 400)
        self.assertIn('not look like a PDF', json.loads(body)['error'])

    def test_one_row_comes_back_as_a_pdf(self) -> None:
        job = {
            'id': self.upload()['id'],
            'rows': [{'text': 'Jane Doe | jane@example.com', 'filename': 'jane.pdf'}],
        }
        status, body, content_type = post(
            f'{self.base}/api/seal', json.dumps(job).encode(), 'application/json'
        )
        self.assertEqual(status, 200, body)
        self.assertEqual(content_type, 'application/pdf')
        self.assertTrue(body.startswith(b'%PDF'))

    def test_several_rows_come_back_as_a_zip(self) -> None:
        job = {
            'id': self.upload()['id'],
            'rows': [
                {'text': 'A | a@example.com', 'filename': 'a.pdf'},
                {'text': 'Šárka | b@example.com', 'filename': 'b.pdf'},
            ],
        }
        status, body, content_type = post(
            f'{self.base}/api/seal', json.dumps(job).encode(), 'application/json'
        )
        self.assertEqual(status, 200, body)
        self.assertEqual(content_type, 'application/zip')
        with zipfile.ZipFile(BytesIO(body)) as archive:
            self.assertEqual(sorted(archive.namelist()), ['a.pdf', 'b.pdf'])

    def test_clashing_filenames_do_not_overwrite_each_other(self) -> None:
        job = {
            'id': self.upload()['id'],
            'rows': [
                {'text': 'A', 'filename': 'same.pdf'},
                {'text': 'B', 'filename': 'same.pdf'},
            ],
        }
        _, body, _ = post(f'{self.base}/api/seal', json.dumps(job).encode(), 'application/json')
        with zipfile.ZipFile(BytesIO(body)) as archive:
            self.assertEqual(len(archive.namelist()), 2)

    def test_an_id_that_tries_to_escape_is_refused(self) -> None:
        job = {'id': '../../etc/passwd', 'rows': [{'text': 'x'}]}
        status, body, _ = post(
            f'{self.base}/api/seal', json.dumps(job).encode(), 'application/json'
        )
        self.assertEqual(status, 400)
        self.assertIn('Unknown upload id', json.loads(body)['error'])

    def test_an_unknown_id_is_a_404(self) -> None:
        job = {'id': '0' * 32, 'rows': [{'text': 'x'}]}
        status, _, _ = post(
            f'{self.base}/api/seal', json.dumps(job).encode(), 'application/json'
        )
        self.assertEqual(status, 404)

    def test_a_row_without_text_is_refused(self) -> None:
        job = {'id': self.upload()['id'], 'rows': [{'text': '  '}]}
        status, body, _ = post(
            f'{self.base}/api/seal', json.dumps(job).encode(), 'application/json'
        )
        self.assertEqual(status, 400)
        self.assertIn('no seal text', json.loads(body)['error'])

    def test_no_rows_is_refused(self) -> None:
        job = {'id': self.upload()['id'], 'rows': []}
        status, _, _ = post(
            f'{self.base}/api/seal', json.dumps(job).encode(), 'application/json'
        )
        self.assertEqual(status, 400)

    def test_broken_json_does_not_crash_the_server(self) -> None:
        status, _, _ = post(f'{self.base}/api/seal', b'{not json', 'application/json')
        self.assertEqual(status, 400)
        # and the server is still answering
        with urllib.request.urlopen(f'{self.base}/api/health') as response:
            self.assertEqual(response.status, 200)

    def test_health_reports_qpdf(self) -> None:
        with urllib.request.urlopen(f'{self.base}/api/health') as response:
            self.assertIn('qpdf', json.loads(response.read())['qpdf'])


if __name__ == '__main__':
    unittest.main()
