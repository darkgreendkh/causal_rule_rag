from app.chunking import chunk_document


def test_chunker_preserves_legal_articles_and_markdown_table() -> None:
    text = """# 数据安全条例

第一条 为了规范数据处理活动，制定本条例。

第二条 数据处理者应当履行下列义务。

| 义务 | 保存期限 |
| --- | --- |
| 审计记录 | 三年 |
| 风险报告 | 五年 |
"""

    chunks = chunk_document(text, max_chars=800, overlap_chars=80)

    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert any(
        chunk.heading == "数据安全条例"
        and chunk.article_no == "第一条"
        and "规范数据处理活动" in chunk.text
        for chunk in chunks
    )
    table_chunks = [chunk for chunk in chunks if "| 义务 | 保存期限 |" in chunk.text]
    assert len(table_chunks) == 1
    assert "| 风险报告 | 五年 |" in table_chunks[0].text


def test_long_text_chunks_overlap_by_requested_characters() -> None:
    text = "第一条 " + "甲" * 1200

    chunks = chunk_document(text, max_chars=500, overlap_chars=80)

    assert len(chunks) == 3
    assert all(len(chunk.text) <= 500 for chunk in chunks)
    assert chunks[1].text[:80] == chunks[0].text[-80:]
    assert chunks[2].text[:80] == chunks[1].text[-80:]


def test_oversized_markdown_table_repeats_header() -> None:
    rows = "\n".join(f"| 第{i}项 | {'内容' * 20} |" for i in range(12))
    text = f"""# 目录

| 项目 | 说明 |
| --- | --- |
{rows}
"""

    chunks = chunk_document(text, max_chars=180, overlap_chars=20)

    assert len(chunks) > 1
    assert all(chunk.text.startswith("| 项目 | 说明 |\n| --- | --- |") for chunk in chunks)
    assert all(len(chunk.text) <= 180 for chunk in chunks)
