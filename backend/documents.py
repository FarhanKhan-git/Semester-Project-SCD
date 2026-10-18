"""
documents.py
Step 1 of RAG: read the uploaded file and split it into small chunks.

Each chunk is around 120 words. Every exam question is made from ONE chunk,
which is how VivaVoice makes sure no question comes from outside the document.
"""

import io
import re

import docx       # python-docx, reads .docx files
import pymupdf    # PyMuPDF, reads .pdf files

CHUNK_WORDS = 120


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        pdf = pymupdf.open(stream=data, filetype="pdf")
        return "\n".join(page.get_text() for page in pdf)
    if name.endswith(".docx"):
        document = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs)
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")
    raise ValueError("Only PDF, DOCX or TXT files are allowed.")


def split_into_chunks(text: str):
    """Split the text into sentences, then group sentences until a chunk
    reaches about CHUNK_WORDS words."""
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks, current = [], []
    for sentence in sentences:
        current.append(sentence)
        if len(" ".join(current).split()) >= CHUNK_WORDS:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))

    # Ignore tiny chunks (headings, page numbers) that cannot make a good question
    return [c for c in chunks if len(c.split()) >= 25]
