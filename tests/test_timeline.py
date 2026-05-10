from video_translator.timeline import Segment, Token


def test_token_duration():
    t = Token(text="hi", start_ms=100, end_ms=400)
    assert t.duration_ms == 300


def test_token_negative_duration_clamps_to_zero():
    t = Token(text="x", start_ms=500, end_ms=400)
    assert t.duration_ms == 0


def test_segment_duration():
    s = Segment(index=0, start_ms=0, end_ms=2500)
    assert s.duration_ms == 2500
