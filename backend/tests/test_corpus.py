from pathlib import Path

import pytest

from app.corpus import _read_policy, _read_references, build_corpus

DATA = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture(scope="module")
def corpus():
    return build_corpus(DATA)


def test_every_policy_is_loaded_with_complete_coverage(corpus):
    assert len(corpus["documents"]) == 36
    units = {u["id"]: u for u in corpus["units"]}
    assert len(units) == len(corpus["units"])
    assert {c["unit_id"] for c in corpus["coverage"]} == set(units)
    assert all(c["disposition"] in {"mapped", "excluded"} for c in corpus["coverage"])
    assert all(
        c["matter_ids"] if c["disposition"] == "mapped" else c["reason"] for c in corpus["coverage"]
    )


@pytest.mark.skipif(
    not (DATA / "research_papers").exists(), reason="User-provided publications are kept local"
)
def test_all_eight_local_publications_keep_pdf_page_locations(corpus):
    assert len({r["source_path"] for r in corpus["references"]}) == 8
    assert all(r["page"] >= 1 and r["text"].strip() for r in corpus["references"])


@pytest.mark.parametrize("prefix,count", [("13_", 2), ("14_", 2), ("15_", 3), ("24_", 2)])
def test_first_articles_of_multiple_regulations_do_not_collide(corpus, prefix, count):
    units = [
        u
        for u in corpus["units"]
        if Path(u["source_path"]).name.startswith(prefix) and u["article"] == "第一条"
    ]
    assert len(units) == count
    assert len({u["title"] for u in units}) == count
    assert len({u["id"] for u in units}) == count


def test_scope_dates_come_from_body_not_scrape_or_stale_metadata(corpus):
    units = corpus["units"]
    foreign = next(
        u
        for u in units
        if Path(u["source_path"]).name.startswith("25_") and u["article"] == "第七条"
    )
    assert foreign["valid_from"] == "2026-05-15"
    assert foreign["valid_to"] == "2031-05-14"
    assert foreign["validity_known"] is True
    medical = next(
        u
        for u in units
        if Path(u["source_path"]).name.startswith("04_") and u["article"] == "第九条"
    )
    assert medical["valid_to"] == "2030-12-31"
    assert not any(u["valid_from"] in {"2026-06-09", "2026-06-13"} for u in units)
    assert any(not u["validity_known"] for u in units)


def test_evidence_is_exactly_locatable_and_pdf_never_activates_policy(corpus):
    units = {u["id"]: u for u in corpus["units"]}
    for item in corpus["rules"] + corpus["actions"]:
        assert item["evidence"]
        for evidence in item["evidence"]:
            unit = units[evidence["unit_id"]]
            assert evidence["quote"] and evidence["quote"] in unit["text"]
            assert evidence["source_path"] == unit["source_path"]
            raw = (DATA / unit["source_path"]).read_text(encoding="utf-8-sig")
            assert evidence["quote"] in raw
    assert all(
        r["review_source"] == "implementation_source_review"
        for r in corpus["rules"]
        if r["status"] == "active"
    )


def test_build_is_read_only_and_identifiers_reproducible(tmp_path):
    policy = tmp_path / "wuhan_shebao" / "sample.txt"
    policy.parent.mkdir()
    policy.write_text(
        "标题: 测试办法\n类别: 养老保险\n抓取日期: 2026-06-09\n"
        "====\n第一条 条款甲。\n第二条 本办法自2024年1月1日起施行，有效期2年。",
        encoding="utf-8",
    )
    before = policy.read_bytes()
    first = build_corpus(tmp_path)
    assert first == build_corpus(tmp_path)
    assert policy.read_bytes() == before
    assert list(tmp_path.rglob("*.*")) == [policy]


def test_nonbreaking_space_indents_do_not_hide_entire_policy():
    path = DATA / "guojia_shebao/养老保险/国务院关于建立统一的城乡居民基本养老保险制度的意见.txt"
    _, units = _read_policy(path, DATA)
    assert any(u["article"] == "三、参保范围" for u in units)
    assert max(len(u["text"]) for u in units) < 2000


def test_national_injury_amending_decision_is_a_separate_regulation():
    path = DATA / "guojia_shebao/工伤保险/工伤保险条例.txt"
    document, units = _read_policy(path, DATA)
    assert document["regulation_count"] == 2
    assert any("修改" in u["title"] and u["article"].startswith("一、") for u in units)
    assert not any(u["article"] == "发布说明" and len(u["text"]) > 1000 for u in units)


def test_pdf_text_cache_uses_source_hash_and_parser_version(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace

    import pdfplumber

    import app.corpus as parser

    data = tmp_path / "data"
    pdf = data / "research_papers/reference.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"source-version-one")
    opened = []

    @contextmanager
    def open_pdf(path):
        opened.append(path)
        yield SimpleNamespace(
            pages=[SimpleNamespace(extract_text=lambda: "可定位的文本页", close=lambda: None)]
        )

    monkeypatch.setattr(pdfplumber, "open", open_pdf)
    first = _read_references(data)
    assert _read_references(data) == first
    assert len(opened) == 1
    pdf.write_bytes(b"source-version-two")
    changed = _read_references(data)
    assert changed[0]["id"] != first[0]["id"]
    assert len(opened) == 2
    monkeypatch.setattr(parser, "PARSER_VERSION", "new-parser-version")
    assert _read_references(data) == changed
    assert len(opened) == 3


def test_open_ended_scope_is_not_a_claim_of_current_validity(corpus):
    unit = next(
        u
        for u in corpus["units"]
        if u["source_path"].endswith("社会保险经办条例.txt") and u["article"] == "第六条"
    )
    assert unit["valid_from"] == "2023-12-01"
    assert unit["valid_to"] is None and unit["validity_known"] is True
    assert "不代表已核实当前清理状态" in unit["validity_note"]
    for rule in corpus["rules"]:
        assert rule["scope"]["title"] == rule["evidence"][0]["title"]
