"""Safe text extraction for supported document types."""
from io import BytesIO
from pathlib import Path
import zipfile

import pymupdf as fitz
from docx import Document

from .validation_service import InputError

ALLOWED = {".pdf", ".docx", ".txt"}


def extract_document(filename: str, payload: bytes, max_chars: int) -> dict:
    extension = Path(filename or "").suffix.lower()
    if extension not in ALLOWED:
        raise InputError("Choose a PDF, DOCX, or TXT file.")
    if not payload:
        raise InputError("The selected file is empty.")
    try:
        if extension == ".pdf":
            if not payload.startswith(b"%PDF-"):
                raise InputError("This file does not appear to be a valid PDF.")
            with fitz.open(stream=payload, filetype="pdf") as pdf:
                text = "\n\n".join(page.get_text("text", sort=True).strip() for page in pdf if page.get_text("text", sort=True).strip())
            if len(text.strip()) < 30:
                raise InputError("This PDF contains little or no selectable text. Scanned or image-only PDFs are not supported yet; try an OCR text export.")
        elif extension == ".docx":
            if not zipfile.is_zipfile(BytesIO(payload)):
                raise InputError("This file does not appear to be a valid DOCX document.")
            doc = Document(BytesIO(payload))
            blocks = []
            for p in doc.paragraphs:
                content = p.text.strip()
                if content:
                    style = p.style.name.lower() if p.style else ""
                    if style.startswith("heading"):
                        content = f"{p.style.name}: {content}"
                    elif "list bullet" in style:
                        content = f"• {content}"
                    elif "list number" in style:
                        content = f"1. {content}"
                    blocks.append(content)
            for table in doc.tables:
                for row in table.rows:
                    blocks.append(" | ".join(cell.text.strip().replace("\n", "; ") for cell in row.cells))
            text = "\n".join(blocks)
        else:
            text = payload.decode("utf-8-sig")
        text = text.strip()
    except InputError:
        raise
    except (fitz.FileDataError, zipfile.BadZipFile, UnicodeDecodeError, ValueError, OSError) as exc:
        raise InputError("We could not read this file. Check that it is not damaged and try again.") from exc
    if not text:
        raise InputError("No readable text was found in this document.")
    if len(text) > max_chars:
        raise InputError(f"The extracted text is {len(text):,} characters, above the {max_chars:,} character limit. Split the document into smaller sections.", 413)
    return {"text": text, "filename": Path(filename).name, "characters": len(text), "words": len(text.split())}
