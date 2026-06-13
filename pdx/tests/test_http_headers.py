import asyncio
import unittest
from io import BytesIO
from unittest.mock import patch

from fastapi import UploadFile

from api import package
from pdx.http_headers import attachment_content_disposition


class AttachmentContentDispositionTests(unittest.TestCase):
    def test_preserves_ascii_filename(self):
        header = attachment_content_disposition("report.pdf")

        self.assertEqual(
            header,
            'attachment; filename="report.pdf"; filename*=UTF-8\'\'report.pdf',
        )

    def test_encodes_unicode_filename_with_ascii_fallback(self):
        header = attachment_content_disposition("रिपोर्ट.pdf")

        self.assertIn('filename="adaptivedocument.pdf"', header)
        self.assertIn("filename*=UTF-8''%E0%A4%B0", header)
        header.encode("latin-1")

    def test_removes_paths_and_control_characters(self):
        header = attachment_content_disposition('../folder\\bad\r\n"name.pdf')

        self.assertNotIn("\r", header)
        self.assertNotIn("\n", header)
        self.assertIn('filename="bad\\"name.pdf"', header)
        self.assertNotIn("folder", header)


class PackageResponseTests(unittest.TestCase):
    def test_unicode_upload_filename_does_not_crash_response(self):
        upload = UploadFile(file=BytesIO(b"%PDF-1.7"), filename="रिपोर्ट.pdf")

        with patch("api.build_off_bytes", return_value=b"%PDF-1.7 packaged"):
            response = asyncio.run(package(file=upload, markdown="# Report"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "filename*=UTF-8''%E0%A4%B0",
            response.headers["content-disposition"],
        )
        response.headers["content-disposition"].encode("latin-1")


if __name__ == "__main__":
    unittest.main()
