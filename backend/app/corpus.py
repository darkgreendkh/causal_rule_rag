"""Read-only, provenance-preserving policy and research corpus construction."""

import json
import re
import unicodedata
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path

from app.policy_catalog import make_catalog

PARSER_VERSION = "policy-units-v3-pdf-text-v1"


MULTI_REGULATIONS = {
    "13_": ["武汉住房公积金缴存管理办法", "武汉住房公积金缴存管理实施细则"],
    "14_": ["武汉住房公积金提取管理办法", "武汉住房公积金提取管理实施细则"],
    "15_": [
        "武汉市灵活就业人员住房公积金缴存使用管理办法（试行）",
        "武汉市灵活就业人员住房公积金缴存提取管理实施细则（试行）",
        "武汉市灵活就业人员住房公积金个人住房贷款实施细则（试行）",
    ],
    "24_": [
        "武汉新建商品房住房公积金个人住房贷款实施细则",
        "武汉存量房住房公积金个人住房贷款实施细则",
    ],
}
NUM = "一二三四五六七八九十百零〇两"
ARTICLE = re.compile(rf"^[^\S\n]*(第[{NUM}0-9]+条)")
CHAPTER = re.compile(rf"^[^\S\n]*(第[{NUM}0-9]+章[^\n]*)$")
SECTION = re.compile(rf"^[^\S\n]*([{NUM}]+、[^\n]*)")
SUBSECTION = re.compile(rf"^[^\S\n]*([（(][{NUM}]+[）)][^\n]*)")


def stable_id(prefix: str, *parts: str) -> str:
    return prefix + "_" + sha256("\x1f".join(parts).encode()).hexdigest()[:20]


def _normal(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def _scope(text: str, preamble: str) -> dict:
    """Only explicit enactment language establishes dates, never capture timestamps."""
    compact = _normal(text)
    dates = re.findall(
        r"(?:本(?:办法|实施细则|细则|意见|通知|条例|法|决定)|现予公布|现将[^。]{0,60})"
        r"[^。]{0,30}?(?:自|从)(\d{4})年(\d{1,2})月(\d{1,2})日起(?:施行|实施|执行)",
        compact,
    )
    start = date(*map(int, dates[-1])) if dates else None
    end = None
    terms = re.findall(r"有效期(?:为)?([0-9一二三四五六七八九十]+)年", compact)
    if start and terms:
        number = terms[-1]
        years = int(number) if number.isdigit() else "一二三四五六七八九十".index(number) + 1
        end = date(start.year + years, start.month, start.day) - timedelta(days=1)
    # Maintenance notes explicitly extend/replace a previous term. Last published note wins.
    explicit = re.findall(
        r"有效期(?:届满日期为|截止|截至|至)(\d{4})年(\d{1,2})月(\d{1,2})日", _normal(preamble)
    )
    if explicit:
        end = date(*map(int, explicit[-1]))
    return {
        "valid_from": start.isoformat() if start else None,
        "valid_to": end.isoformat() if end else None,
        "validity_known": bool(start),
        "validity_note": (
            "正文明确起止日期"
            if end
            else "正文明确施行日期且未规定终止日；仅表示库内文本范围，不代表已核实当前清理状态"
        )
        if start
        else "正文未明确可定位的施行日期",
    }


def _regulations(body: str, filename: str, title: str) -> list[tuple[str, str]]:
    titles = next((v for k, v in MULTI_REGULATIONS.items() if filename.startswith(k)), [])
    if "延迟法定退休年龄" in filename:
        titles = ["国务院关于渐进式延迟法定退休年龄的办法"]
    if filename == "工伤保险条例.txt":
        titles = ["国务院关于修改《工伤保险条例》的决定", "工伤保险条例"]
    boundaries = []
    for name in titles:
        pattern = r"(?m)^[ \t\u3000]*" + r"\s*".join(map(re.escape, name)) + r"[ \t\u3000]*$"
        matches = list(re.finditer(pattern, body))
        if len(matches) != 1:
            raise ValueError(f"无法唯一定位独立规范标题: {filename}: {name}")
        boundaries.append((matches[0].start(), name))
    if not boundaries:
        return [(title, body)]
    boundaries.sort()
    if boundaries[0][0]:
        boundaries.insert(0, (0, title + "（发布说明）"))
    return [
        (name, body[start : boundaries[i + 1][0] if i + 1 < len(boundaries) else len(body)])
        for i, (start, name) in enumerate(boundaries)
    ]


def _units(body: str, title: str) -> list[tuple[str, str, str]]:
    """Keep entire source spans, including headings and tables, without rewriting quotes."""
    lines = body.splitlines(keepends=True)
    has_articles = any(ARTICLE.match(line) for line in lines)
    output, collected = [], []
    article, chapter = "发布说明", ""
    for line in lines:
        article_match, chapter_match = ARTICLE.match(line), CHAPTER.match(line)
        marker = (
            article_match
            or chapter_match
            or SECTION.match(line)
            or (
                not has_articles
                and (SUBSECTION.match(line) or re.match(r"^[ \t]*([1-9]\d*[.．][^\n]*)", line))
            )
        )
        if marker:
            if "".join(collected).strip():
                output.append((article, "".join(collected).strip(), chapter))
            if chapter_match:
                chapter = chapter_match[1]
            article = marker[1].strip()
            if not article_match and not chapter_match:
                article = re.split(r"[。；]", article)[0][:80]
            collected = []
        collected.append(line)
    if "".join(collected).strip():
        output.append((article, "".join(collected).strip(), chapter))
    return output


def _read_policy(path: Path, data_dir: Path) -> tuple[dict, list[dict]]:
    raw_bytes = path.read_bytes()
    raw = raw_bytes.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    pieces = re.split(r"(?m)^={4,}\s*$", raw, maxsplit=1)
    header, body = (pieces[0], pieces[1]) if len(pieces) == 2 else ("", raw)
    metadata = dict(re.findall(r"(?m)^([^:\n]+):[ \t]*(.*)$", header))
    relative = path.relative_to(data_dir).as_posix()
    title = metadata.get("标题", path.stem)
    publisher = metadata.get("发布机构", "")
    region = "武汉" if "武汉" in publisher else "湖北" if "湖北" in publisher else "全国"
    category = metadata.get("类别", "共享经办")
    if category in {"基本法律（最高效力层级）", "综合性文件"}:
        category = "养老保险" if "退休年龄" in title else "共享经办"
    digest = sha256(raw_bytes).hexdigest()
    document_id = stable_id("doc", relative, digest)
    regulations = _regulations(body, path.name, title)
    units = []
    for regulation_index, (regulation_title, regulation_text) in enumerate(regulations):
        scope = _scope(regulation_text, body.split("第一条")[0])
        for unit_index, (article, text, chapter) in enumerate(
            _units(regulation_text, regulation_title)
        ):
            unit_category = category
            if category == "共享经办":
                unit_category = next(
                    (
                        c
                        for c in ["养老保险", "医疗保险", "工伤保险", "失业保险", "生育保险"]
                        if c in chapter
                    ),
                    category,
                )
            units.append(
                {
                    "id": stable_id(
                        "unit",
                        relative,
                        digest,
                        str(regulation_index),
                        regulation_title,
                        str(unit_index),
                        text,
                    ),
                    "document_id": document_id,
                    "source_sha256": digest,
                    "source_path": relative,
                    "title": regulation_title,
                    "article": article,
                    "text": text,
                    "category": unit_category,
                    "region": region,
                    "chapter": chapter,
                    "version": metadata.get("文号"),
                    **scope,
                }
            )
    document = {
        "id": document_id,
        "source_path": relative,
        "filename": path.name,
        "title": title,
        "sha256": digest,
        "category": category,
        "region": region,
        "source_url": metadata.get("来源URL"),
        "published_at": metadata.get("发布日期"),
        "unit_count": len(units),
        "regulation_count": sum(not name.endswith("（发布说明）") for name, _ in regulations),
    }
    return document, units


def _read_references(data_dir: Path) -> list[dict]:
    paths = sorted((data_dir / "research_papers").glob("*.pdf"))
    if not paths:
        return []
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("读取研究文献需要 pdfplumber；请安装后重新构建，文献未被跳过") from exc
    references = []
    cache_dir = data_dir.parent / ".runtime/research/source-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    for path in paths:
        relative = path.relative_to(data_dir).as_posix()
        digest = sha256(path.read_bytes()).hexdigest()
        cache_path = cache_dir / (stable_id("pdf", relative, digest, PARSER_VERSION) + ".json")
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if (
                cached.get("sha256") != digest
                or cached.get("parser_version") != PARSER_VERSION
                or cached.get("source_path") != relative
            ):
                raise ValueError(f"PDF来源缓存校验失败: {cache_path}")
            references.extend(cached["pages"])
            continue
        pages = []
        with pdfplumber.open(path) as pdf:
            for page_number, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                pages.append(
                    {
                        "id": stable_id("reference", relative, digest, str(page_number)),
                        "source_path": relative,
                        "filename": path.name,
                        "title": path.stem,
                        "sha256": digest,
                        "page": page_number,
                        "text": text,
                        "extraction": "pdf_text_layer",
                        "gaps": [] if text.strip() else ["本页无可提取文本层，需要人工核对"],
                    }
                )
                page.close()
        cache_path.write_text(
            json.dumps(
                {
                    "parser_version": PARSER_VERSION,
                    "sha256": digest,
                    "source_path": relative,
                    "pages": pages,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        references.extend(pages)
    return references


def build_corpus(data_dir: Path) -> dict:
    data_dir = Path(data_dir)
    documents, units = [], []
    for directory in ("guojia_shebao", "wuhan_shebao"):
        for path in sorted((data_dir / directory).rglob("*.txt")):
            document, parsed = _read_policy(path, data_dir)
            documents.append(document)
            units.extend(parsed)
    matters, rules, actions, coverage = make_catalog(units)
    return {
        "documents": documents,
        "units": units,
        "matters": matters,
        "rules": rules,
        "actions": actions,
        "coverage": coverage,
        "references": _read_references(data_dir),
    }
