"""PDF -> text -> FAQ-sized chunks (each stored as one Policy row)."""
import io
import re

from pypdf import PdfReader

MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_PAGES = 100
MAX_CHUNKS = 80
CHUNK_CHARS = 900


class PdfIngestError(ValueError):
    pass


def extract_pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise PdfIngestError("Encrypted PDFs are not supported.")
        if len(reader.pages) > MAX_PAGES:
            raise PdfIngestError(f"PDF has more than {MAX_PAGES} pages.")
        pages = [(page.extract_text() or "") for page in reader.pages]
    except PdfIngestError:
        raise
    except Exception as exc:
        raise PdfIngestError("Could not read this PDF.") from exc
    return "\n".join(pages)


def _clean(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_NUMBERED_HEADING = re.compile(r"^\d+(?:\.\d+)*[.)]\s+[A-Za-z]")
_ABBREV = re.compile(r"\b(Rs|No|Mr|Mrs|Ms|Dr|vs|approx|etc|e\.g|i\.e)\.\s", re.IGNORECASE)


def _is_heading(line: str, prev_line: str | None) -> bool:
    if not line or len(line) > 80:
        return False
    if _NUMBERED_HEADING.match(line):
        return line[-1] not in ".,;"  # "1. Items must be unused." is a list item, not a heading
    # Unnumbered heading: short, no sentence punctuation at the end, starts with a capital,
    # and follows a blank line, the start of the text, or a finished sentence.
    if line[-1] in ".,;:" or not line[0].isupper():
        return False
    return prev_line is None or prev_line == "" or prev_line[-1] in ".!?"


def _split_sentences(text: str) -> list[str]:
    protected = _ABBREV.sub(lambda m: m.group(0)[:-1] + "\u00a0", text)  # keep "Rs. 3,000" together
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", protected)
    return [p.replace("\u00a0", " ").strip() for p in parts if p.strip()]


def _pack(text: str, max_chars: int) -> list[str]:
    """Pack sentences into pieces of at most max_chars (never cuts inside a sentence
    unless one sentence alone is longer than max_chars)."""
    pieces: list[str] = []
    current = ""
    for sentence in _split_sentences(text):
        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if not sentence:
            continue
        if current and len(current) + len(sentence) + 1 > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence
    if current:
        pieces.append(current)
    return pieces


def chunk_text(text: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    """Split on headings first, so a chunk never mixes two sections. Every chunk starts
    with its section heading, which helps the assistant's keyword search match it."""
    lines = [ln.strip() for ln in _clean(text).split("\n")]

    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    prev: str | None = None
    for line in lines:
        if _is_heading(line, prev):
            sections.append((line, []))
        elif line:
            sections[-1][1].append(line)
        prev = line

    chunks: list[str] = []
    for heading, body_lines in sections:
        body = " ".join(body_lines).strip()
        if not body:
            continue  # e.g. the document title on its own
        label = re.sub(r"^\d+(?:\.\d+)*[.)]\s+", "", heading) if heading else None
        room = max_chars - (len(label) + 2 if label else 0)
        for piece in _pack(body, max(room, 200)):
            chunks.append(f"{label}: {piece}" if label else piece)
    return chunks