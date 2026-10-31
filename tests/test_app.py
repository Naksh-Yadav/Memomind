import io
import json
import unittest
from unittest.mock import patch

import pymupdf as fitz
from docx import Document

from app import create_app
from services.document_service import extract_document
from services.validation_service import InputError, parse_and_validate_response, validate_source


SAMPLE = {
    "topic": "Plants", "difficulty": "Beginner", "content_overview": "A source overview.",
    "technique": "Story", "technique_reason": "A sequence works as a journey.",
    "mnemonic": {"title": "Garden trip", "text": "A small memory story.", "breakdown": [
        {"component": "seed", "meaning": "Start", "explanation": "Seeds begin the story."}]},
    "key_facts": [{"fact": "Plants need light.", "explanation": "Light supports growth.", "keywords": ["light"]}],
    "memory_tips": ["Picture the plant in sunlight."], "accuracy_notes": [],
    "recall_test": [
        {"type": "mcq", "question": "What do plants need?", "options": ["Light", "Noise", "Metal", "Salt"], "correct_answer": "Light", "explanation": "The source says plants need light."},
        {"type": "fill_blank", "question": "Plants need ___.", "options": [], "correct_answer": "light", "acceptable_answers": ["sunlight"], "explanation": "Light supports growth."},
        {"type": "short_answer", "question": "Name a need.", "options": [], "correct_answer": "light", "explanation": "The source says plants need light."}
    ]
}


class ValidationTests(unittest.TestCase):
    def test_source_limits(self):
        self.assertEqual(validate_source("  " + "abcde " * 5, 50), ("abcde " * 5).strip())
        with self.assertRaises(InputError):
            validate_source("short", 50)
        with self.assertRaises(InputError):
            validate_source("x" * 51, 50)

    def test_model_json_and_fields(self):
        result = parse_and_validate_response(json.dumps(SAMPLE))
        self.assertEqual(len(result["recall_test"]), 3)
        broken = dict(SAMPLE); broken["recall_test"] = [{"type": "other"}]
        with self.assertRaises(ValueError):
            parse_and_validate_response(json.dumps(broken))


class DocumentTests(unittest.TestCase):
    def test_txt_extraction_and_type_check(self):
        result = extract_document("lesson.txt", b"A plain text lesson about cell division.", 1000)
        self.assertEqual(result["words"], 7)
        with self.assertRaises(InputError):
            extract_document("lesson.pdf", b"not a pdf", 1000)

    def test_pdf_extraction(self):
        doc = fitz.open(); page = doc.new_page(); page.insert_text((72, 72), "Section 1: Cell division\nSelectable text explains a complete process in this example.")
        page = doc.new_page(); page.insert_text((72, 72), "Section 2: Outcome\nTwo new cells are formed.")
        payload = doc.tobytes(); doc.close()
        extracted = extract_document("lesson.pdf", payload, 1000)["text"]
        self.assertIn("complete process", extracted)
        self.assertIn("Section 2: Outcome", extracted)

    def test_scanned_or_empty_pdf_message(self):
        doc = fitz.open(); doc.new_page(); payload = doc.tobytes(); doc.close()
        with self.assertRaisesRegex(InputError, "Scanned or image-only"):
            extract_document("scan.pdf", payload, 1000)

    def test_docx_extraction(self):
        doc = Document(); doc.add_heading("Cell structure", 1); doc.add_paragraph("Cells contain a nucleus."); doc.add_paragraph("Mitochondria release energy.", style="List Bullet")
        stream = io.BytesIO(); doc.save(stream)
        text = extract_document("notes.docx", stream.getvalue(), 1000)["text"]
        self.assertIn("Heading 1: Cell structure", text)
        self.assertIn("Cells contain a nucleus", text)
        self.assertIn("• Mitochondria release energy", text)

    def test_long_text_limit(self):
        with self.assertRaises(InputError):
            extract_document("long.txt", ("Repeated section content. " * 5).encode(), 40)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "GEMINI_API_KEY": "", "MAX_TEXT_CHARS": 1000, "RATE_LIMIT_REQUESTS": 20})
        self.client = self.app.test_client()

    def test_health_does_not_expose_secret(self):
        self.app.config["GEMINI_API_KEY"] = "secret"
        response = self.client.get("/api/health")
        self.assertTrue(response.json["ai_configured"])
        self.assertNotIn("secret", response.get_data(as_text=True))

    def test_landing_page_and_static_assets(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Make it", page.get_data(as_text=True))
        script = self.client.get("/static/js/app.js")
        self.assertEqual(script.status_code, 200)
        script.close()

    def test_extract_api_route(self):
        response = self.client.post("/api/extract", data={"file": (io.BytesIO(b"A text document containing enough content for extraction."), "notes.txt")}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        self.assertIn("enough content", response.json["text"])

    def test_empty_and_unconfigured_generation(self):
        response = self.client.post("/api/generate", json={"text": ""})
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/generate", json={"text": "Useful enough source text for the no key setup check."})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("Traceback", response.get_data(as_text=True))

    @patch("app.generate", return_value=SAMPLE)
    def test_generation_response(self, mocked):
        self.app.config["GEMINI_API_KEY"] = "fake-test-key"
        response = self.client.post("/api/generate", json={"text": "Useful source text about planets and their order around the sun."})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["topic"], "Plants")
        mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
