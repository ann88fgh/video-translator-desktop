"""Test build_segments — tách tokens thành câu/segment đúng."""

from __future__ import annotations

from video_translator.segments import build_segments
from video_translator.timeline import Token


def _o(text: str, start: int, end: int) -> Token:
    return Token(text=text, start_ms=start, end_ms=end, translation_status="original")


def _t(text: str) -> Token:
    return Token(text=text, start_ms=0, end_ms=0, translation_status="translation")


def test_empty_returns_empty():
    assert build_segments([]) == []


def test_single_sentence_split_by_period():
    tokens = [
        _o("Hello", 0, 300),
        _o(" world", 300, 700),
        _o(".", 700, 800),
        _t("Xin"),
        _t(" chào"),
        _t(" thế"),
        _t(" giới."),
        _o(" How", 1100, 1500),
        _o(" are", 1500, 1700),
        _o(" you", 1700, 1900),
        _o("?", 1900, 2000),
        _t(" Bạn"),
        _t(" khỏe"),
        _t(" không?"),
    ]
    segs = build_segments(tokens)
    assert len(segs) == 2
    assert "Hello" in segs[0].source_text
    assert "Xin chào" in segs[0].translated_text
    assert "How" in segs[1].source_text
    assert "Bạn khỏe" in segs[1].translated_text
    assert segs[0].start_ms == 0
    assert segs[0].end_ms == 800
    assert segs[1].start_ms == 1100
    assert segs[1].end_ms == 2000


def test_split_by_long_pause():
    tokens = [
        _o("Hi", 0, 200),
        _t(" Chào"),
        # khoảng lặng 1500ms (lớn hơn pause_split_ms=600)
        _o("Yes", 2000, 2300),
        _t(" Vâng"),
    ]
    segs = build_segments(tokens, pause_split_ms=600, min_segment_ms=0)
    assert len(segs) == 2


def test_max_length_split():
    # Một dòng dài không có dấu câu → nên cắt theo max_segment_ms
    tokens = []
    for i in range(20):
        tokens.append(_o(f" w{i}", i * 500, i * 500 + 400))
    tokens.append(_t(" bản dịch dài"))
    segs = build_segments(tokens, max_segment_ms=3000, min_segment_ms=0)
    assert len(segs) >= 2
    for s in segs:
        assert s.duration_ms <= 5000  # mỗi đoạn không quá dài
