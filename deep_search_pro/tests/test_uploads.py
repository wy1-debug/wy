import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from api import server
from utils.upload_storage import session_path


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patcher = patch.object(server, "updated_dir", self.root)
        self.patcher.start()
        self.client = TestClient(server.app)

    def tearDown(self):
        self.client.close()
        self.patcher.stop()
        self.temp.cleanup()

    def upload(self, files, session="test-session"):
        return self.client.post("/api/upload", data={"thread_id": session}, files=files)

    def test_chinese_filename_and_utf8_bytes(self):
        payload = "上传验证：知识库内容".encode()
        response = self.upload([("files", ("资料.txt", payload, "text/plain"))])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["files"], ["资料.txt"])
        self.assertEqual((self.root / "session_test-session" / "资料.txt").read_bytes(), payload)

    def test_duplicate_names_preserve_both_documents(self):
        first = self.upload([("files", ("a.txt", b"first"))])
        second = self.upload([("files", ("a.txt", b"second")), ("files", ("a.txt", b"third"))])
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.json()["files"], ["a (1).txt", "a (2).txt"])
        directory = self.root / "session_test-session"
        self.assertEqual((directory / "a.txt").read_bytes(), b"first")
        self.assertEqual((directory / "a (2).txt").read_bytes(), b"third")

    def test_invalid_session_cannot_escape_upload_directory(self):
        response = self.upload([("files", ("ok.txt", b"hello"))], "x/../../outside")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.root.iterdir()), [])
        response = self.client.post("/api/task", json={"query": "test", "thread_id": "../outside"})
        self.assertEqual(response.status_code, 422)

    def test_oversize_batch_is_rolled_back(self):
        with patch.object(server, "MAX_UPLOAD_BYTES", 4):
            response = self.upload([("files", ("small.txt", b"ok")), ("files", ("large.txt", b"12345"))])
        self.assertEqual(response.status_code, 413)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_empty_file_rolls_back_batch(self):
        response = self.upload([("files", ("ok.txt", b"data")), ("files", ("empty.txt", b""))])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_unsupported_and_windows_reserved_names(self):
        for name in ["payload.exe", "CON.txt", "bad:name.txt", "bad?.txt"]:
            with self.subTest(name=name):
                response = self.upload([("files", (name, b"data"))])
                self.assertEqual(response.status_code, 400)

    def test_client_path_is_stripped(self):
        response = self.upload([("files", ("../../outside.txt", b"safe"))])
        self.assertEqual(response.status_code, 200)
        self.assertTrue((session_path(self.root, "test-session") / "outside.txt").is_file())

    def test_file_count_limit(self):
        with patch.object(server, "MAX_UPLOAD_FILES", 1):
            response = self.upload([("files", ("a.txt", b"a")), ("files", ("b.txt", b"b"))])
        self.assertEqual(response.status_code, 400)

    def test_session_isolation(self):
        self.upload([("files", ("a.txt", b"one"))], "one")
        self.upload([("files", ("a.txt", b"two"))], "two")
        self.assertEqual((session_path(self.root, "one") / "a.txt").read_bytes(), b"one")
        self.assertEqual((session_path(self.root, "two") / "a.txt").read_bytes(), b"two")

    def test_health_is_independent_of_model_initialization(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
