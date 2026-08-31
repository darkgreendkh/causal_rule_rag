import re
from dataclasses import dataclass

HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$")
ARTICLE_PATTERN = re.compile(
    r"^(第[零〇一二三四五六七八九十百千万两\d]+条"
    r"(?:之[零〇一二三四五六七八九十百千万两\d]+)?)"
)
MARKDOWN_SEPARATOR_PATTERN = re.compile(r"^\|?\s*:?-{3,}")


@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str
    heading: str | None = None
    article_no: str | None = None


@dataclass(frozen=True)
class _Block:
    text: str
    heading: str | None
    article_no: str | None
    table_kind: str | None = None


def chunk_document(
    text: str,
    *,
    max_chars: int = 800,
    overlap_chars: int = 80,
) -> list[TextChunk]:
    if max_chars <= 0 or overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("max_chars must be positive and overlap_chars must be smaller")

    blocks = _parse_blocks(text)
    pieces: list[tuple[str, str | None, str | None]] = []
    for block in blocks:
        if block.table_kind:
            texts = _split_table(block.text, block.table_kind, max_chars)
        else:
            texts = _split_text(block.text, max_chars, overlap_chars)
        pieces.extend((piece, block.heading, block.article_no) for piece in texts)

    return [
        TextChunk(index=index, text=piece, heading=heading, article_no=article_no)
        for index, (piece, heading, article_no) in enumerate(pieces)
        if piece.strip()
    ]


def _parse_blocks(text: str) -> list[_Block]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[_Block] = []
    heading: str | None = None
    active_article: str | None = None
    paragraph_article: str | None = None
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph, paragraph_article
        content = "\n".join(paragraph).strip()
        if content:
            blocks.append(_Block(content, heading, paragraph_article))
        paragraph = []
        paragraph_article = None

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        heading_match = HEADING_PATTERN.match(stripped)
        article_match = ARTICLE_PATTERN.match(stripped)

        if heading_match:
            flush_paragraph()
            heading = heading_match.group(1).strip()
            active_article = None
            index += 1
            continue

        table_kind = _table_kind(line)
        if table_kind:
            flush_paragraph()
            table_lines: list[str] = []
            while index < len(lines) and _table_kind(lines[index]) == table_kind:
                table_lines.append(lines[index].strip())
                index += 1
            blocks.append(
                _Block("\n".join(table_lines), heading, active_article, table_kind)
            )
            continue

        if article_match:
            flush_paragraph()
            active_article = article_match.group(1)
            paragraph_article = active_article
            paragraph.append(stripped)
        elif not stripped:
            if paragraph_article:
                if paragraph and paragraph[-1] != "":
                    paragraph.append("")
            else:
                flush_paragraph()
        else:
            if not paragraph:
                paragraph_article = active_article
            paragraph.append(stripped)
        index += 1

    flush_paragraph()
    return blocks


def _table_kind(line: str) -> str | None:
    stripped = line.strip()
    if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 3:
        return "markdown"
    if "\t" in stripped:
        return "tsv"
    return None


def _split_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    step = max_chars - overlap_chars
    return [text[start : start + max_chars] for start in range(0, len(text), step)]


def _split_table(text: str, kind: str, max_chars: int) -> list[str]:
    rows = text.splitlines()
    header_count = 1
    if kind == "markdown" and len(rows) > 1 and MARKDOWN_SEPARATOR_PATTERN.match(rows[1]):
        header_count = 2
    header = rows[:header_count]
    data_rows = rows[header_count:]

    if len(text) <= max_chars or not data_rows:
        return [text]

    chunks: list[str] = []
    current = list(header)
    for row in data_rows:
        candidate = "\n".join([*current, row])
        if len(candidate) <= max_chars:
            current.append(row)
            continue
        if len(current) > header_count:
            chunks.append("\n".join(current))
            current = list(header)
        candidate = "\n".join([*current, row])
        if len(candidate) > max_chars:
            available = max_chars - len("\n".join(header)) - 1
            if available <= 0:
                return _split_text(text, max_chars, 0)
            for start in range(0, len(row), available):
                chunks.append("\n".join([*header, row[start : start + available]]))
            current = list(header)
        else:
            current.append(row)

    if len(current) > header_count:
        chunks.append("\n".join(current))
    return chunks
