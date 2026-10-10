import csv
import tempfile
import unittest
from pathlib import Path

from csv_cleanup import clean_file, normalize_rows


class CsvCleanupTests(unittest.TestCase):
    def test_trim_header_and_values(self):
        rows = normalize_rows([{" Customer Name ": "  Alice  ", "Age": " 20 "}])
        self.assertEqual(rows, [{"customer_name": "Alice", "age": "20"}])

    def test_duplicate_rows_dropped(self):
        rows = [{"First Name": " Alice "}, {"First Name": "Alice"}]
        self.assertEqual(len(normalize_rows(rows)), 1)

    def test_can_keep_duplicates(self):
        rows = [{"X": "1"}, {"X": "1"}]
        self.assertEqual(len(normalize_rows(rows, deduplicate=False)), 2)

    def test_empty_row_dropped(self):
        self.assertEqual(normalize_rows([{"X": " "}, {"X": "valid"}]),
                         [{"x": "valid"}])

    def test_normalization_collision_rejected(self):
        with self.assertRaises(ValueError):
            normalize_rows([{"First Name": "a", "first_name": "b"}])

    def test_roundtrip_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "source.csv"
            dst = Path(temp) / "clean.csv"
            src.write_text(" User Name ,Age\n Ana , 22 \n Ana,22\n\n", encoding="utf-8")
            original = src.read_bytes()
            self.assertEqual(clean_file(src, dst), 1)
            self.assertEqual(src.read_bytes(), original)
            with dst.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows, [{"user_name": "Ana", "age": "22"}])

    def test_same_input_output_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "data.csv"
            file.write_text("x\n1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                clean_file(file, file)


if __name__ == "__main__":
    unittest.main()
