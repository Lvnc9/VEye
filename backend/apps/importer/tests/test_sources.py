"""Where index rows come from, and how files are found: both take untrusted input."""
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from apps.importer import sources
from apps.importer.files import V1Files
from apps.importer.sources import SourceError

ROWS = [{"title": "الف", "code": "PR-01", "_id": {"$oid": "65f0c0ffee0000000000abcd"}}, {"title": "ب", "code": "PR-02"}]


class TempDirCase(SimpleTestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="veye-src-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def write(self, name, text, encoding="utf-8"):
        path = self.dir / name
        path.write_text(text, encoding=encoding)
        return path


class IndexFileTests(TempDirCase):
    def test_a_json_array(self):
        path = self.write("rows.json", json.dumps(ROWS, ensure_ascii=False))
        self.assertEqual(sources.load_index_file(path), ROWS)

    def test_json_lines_as_mongoexport_writes_by_default(self):
        path = self.write("rows.jsonl", "\n".join(json.dumps(r, ensure_ascii=False) for r in ROWS) + "\n\n")
        self.assertEqual(sources.load_index_file(path), ROWS)

    def test_a_single_object_is_one_row(self):
        self.assertEqual(sources.load_index_file(self.write("one.json", '{"title": "الف"}')), [{"title": "الف"}])

    def test_a_byte_order_mark_and_an_empty_file(self):
        self.assertEqual(sources.load_index_file(self.write("bom.json", "﻿" + json.dumps(ROWS, ensure_ascii=False))), ROWS)
        self.assertEqual(sources.load_index_file(self.write("empty.json", "  \n")), [])

    def test_problems_are_persian_source_errors_not_tracebacks(self):
        # (A lone object is a valid one-line mongoexport file — see test_a_single_object_is_one_row.)
        for name, text in (("bad.json", "[{oops"), ("lines.json", '{"a":1}\nnot json'), ("num.json", "[1, 2")):
            with self.assertRaises(SourceError, msg=name):
                sources.load_index_file(self.write(name, text))
        with self.assertRaises(SourceError) as ctx:
            sources.load_index_file(self.dir / "missing.json")
        self.assertIn("یافت نشد", str(ctx.exception))
        latin1 = self.dir / "latin1.json"
        latin1.write_bytes(b"[{\"t\": \"\xe9\"}]")
        with self.assertRaises(SourceError):
            sources.load_index_file(latin1)

    def test_an_absurdly_large_file_is_refused_before_reading(self):
        path = self.write("big.json", "[]")
        with mock.patch.object(sources, "MAX_INDEX_FILE_BYTES", 1):
            with self.assertRaises(SourceError):
                sources.load_index_file(path)


class MongoTests(SimpleTestCase):
    def fake_pymongo(self, rows=None, error=None):
        module = mock.MagicMock()
        if error:
            module.MongoClient.side_effect = error
        else:
            module.MongoClient.return_value.__getitem__.return_value.__getitem__.return_value.find.return_value = rows or []
        return module

    def test_reads_the_named_database_and_collection_and_closes_the_connection(self):
        fake = self.fake_pymongo(ROWS)
        with mock.patch.dict(os.environ, {"V1_TEST_URI": "mongo" + "db://x.invalid/"}), mock.patch.dict("sys.modules", {"pymongo": fake}):
            rows = sources.load_mongo("V1_TEST_URI", "db1", "col1")
        self.assertEqual(rows, ROWS)
        client = fake.MongoClient.return_value
        client.__getitem__.assert_called_with("db1")
        client.__getitem__.return_value.__getitem__.assert_called_with("col1")
        client.close.assert_called_once()
        # A short server-selection timeout, so a wrong host fails fast instead of hanging a worker.
        self.assertEqual(fake.MongoClient.call_args.kwargs["serverSelectionTimeoutMS"], 10_000)

    def test_defaults_are_v1s_own_database_and_collection_names(self):
        self.assertEqual((sources.DEFAULT_MONGO_DB, sources.DEFAULT_MONGO_COLLECTION), ("my_database", "my_collection"))

    def test_a_missing_variable_names_the_variable_not_a_value(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("V1_NOT_SET", None)
            with self.assertRaises(SourceError) as ctx:
                sources.load_mongo("V1_NOT_SET")
        self.assertIn("V1_NOT_SET", str(ctx.exception))

    def test_a_driver_error_never_echoes_the_uri_or_host(self):
        fake = self.fake_pymongo(error=RuntimeError("timed out connecting to mongo" + "db://u:PW123@host.invalid:27017"))
        with mock.patch.dict(os.environ, {"V1_TEST_URI": "mongo" + "db://u:PW123@host.invalid:27017"}), mock.patch.dict("sys.modules", {"pymongo": fake}):
            with self.assertRaises(SourceError) as ctx:
                sources.load_mongo("V1_TEST_URI")
        self.assertNotIn("PW123", str(ctx.exception))
        self.assertNotIn("host.invalid", str(ctx.exception))
        self.assertIn("RuntimeError", str(ctx.exception))

    def test_load_rows_picks_the_source_from_the_options(self):
        with self.assertRaises(SourceError):
            sources.load_rows({})
        fake = self.fake_pymongo(ROWS)
        with mock.patch.dict(os.environ, {"V1_TEST_URI": "mongo" + "db://x.invalid/"}), mock.patch.dict("sys.modules", {"pymongo": fake}):
            self.assertEqual(sources.load_rows({"mongo_uri_env": "V1_TEST_URI"}), ROWS)


class V1FilesTests(TempDirCase):
    def setUp(self):
        super().setUp()
        (self.dir / "saves").mkdir()
        (self.dir / "img").mkdir()

    def test_finds_an_exact_name_and_reads_json_and_images(self):
        (self.dir / "saves" / "a.json").write_text('{"x": 1}', encoding="utf-8")
        (self.dir / "img" / "s.png").write_bytes(b"png")
        files = V1Files(self.dir)
        self.assertTrue(files.usable)
        self.assertEqual(files.read_json("a.json"), ({"x": 1}, None))
        self.assertEqual(files.read_image("s.png"), (b"png", None))

    def test_arabic_and_persian_letters_in_a_file_name_still_match(self):
        # V_1.0's own file names carry Arabic yeh («اجرايي»); a row may carry either spelling.
        (self.dir / "saves" / "روش اجرايي-PR-01-01.json").write_text("{}", encoding="utf-8")
        files = V1Files(self.dir)
        self.assertIsNotNone(files.find("saves", "روش اجرایی-PR-01-01.json"))
        self.assertIsNotNone(files.find("saves", "روش اجرايي-PR-01-01.json"))

    def test_missing_unreadable_and_oversized_files_say_why(self):
        (self.dir / "saves" / "bad.json").write_text("{not json", encoding="utf-8")
        (self.dir / "saves" / "big.json").write_text("{}", encoding="utf-8")
        files = V1Files(self.dir)
        self.assertEqual(files.read_json("nope.json"), (None, "missing"))
        self.assertEqual(files.read_json("bad.json"), (None, "unreadable"))
        with mock.patch("apps.importer.files.MAX_JSON_BYTES", 1):
            self.assertEqual(files.read_json("big.json"), (None, "too_large"))
        self.assertEqual(files.read_image("nope.png"), (None, "missing"))

    def test_names_that_are_not_bare_file_names_are_refused(self):
        (self.dir / "saves" / "a.json").write_text("{}", encoding="utf-8")
        (self.dir / "saves" / "sub").mkdir()
        (self.dir / "saves" / "sub" / "a.json").write_text("{}", encoding="utf-8")  # inside the root, but not a bare name
        outside = self.dir.parent / f"outside-{self.dir.name}.json"
        outside.write_text("{}", encoding="utf-8")
        self.addCleanup(outside.unlink)
        files = V1Files(self.dir)
        for name in ("../" + outside.name, "sub/a.json", "..\\a.json", "/etc/passwd", "..", ".", ""):
            self.assertIsNone(files.find("saves", name), repr(name))

    def test_a_symlink_pointing_outside_the_import_directory_is_refused(self):
        secret = self.dir.parent / f"secret-{self.dir.name}.json"
        secret.write_text('{"secret": true}', encoding="utf-8")
        self.addCleanup(secret.unlink)
        os.symlink(secret, self.dir / "saves" / "link.json")
        self.assertEqual(V1Files(self.dir).read_json("link.json"), (None, "missing"))

    def test_an_empty_or_wrong_directory_is_not_usable(self):
        self.assertFalse(V1Files(self.dir / "nonexistent").usable)
        empty = self.dir / "empty"
        empty.mkdir()
        self.assertFalse(V1Files(empty).usable)
