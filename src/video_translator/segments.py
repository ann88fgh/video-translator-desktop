"""Gom Soniox tokens thành các Segment có ranh giới câu/khoảng lặng."""

from __future__ import annotations

from .timeline import Segment, Token

_SENTENCE_END = (".", "!", "?", "…", "。", "！", "？")


def _is_translation(t: Token) -> bool:
    return (t.translation_status or "").lower() == "translation"


def _is_original(t: Token) -> bool:
    status = (t.translation_status or "").lower()
    # "original" hoặc không set (token không có translation)
    return status in ("original", "", "none")


def _ends_sentence(text: str) -> bool:
    s = text.strip()
    return bool(s) and s.endswith(_SENTENCE_END)


def build_segments(
    tokens: list[Token],
    *,
    max_segment_ms: int = 8000,
    pause_split_ms: int = 600,
    min_segment_ms: int = 800,
) -> list[Segment]:
    """Tách tokens thành segments.

    Quy tắc cắt segment (theo thứ tự ưu tiên):
    1. Sau token "original" có dấu kết câu (`. ! ? …`) đồng thời đã có ít nhất 1
       translation token trong segment.
    2. Khoảng lặng giữa hai token "original" liền nhau > `pause_split_ms`.
    3. Segment đã dài hơn `max_segment_ms`.

    Translation tokens không có `start_ms`/`end_ms` đáng tin trong response
    Soniox (chúng tham chiếu lại original tokens), nên ranh giới thời gian
    của segment chỉ tính dựa trên original tokens. Translation tokens được
    thu nhặt giữa hai mốc cắt.
    """
    if not tokens:
        return []

    segments: list[Segment] = []
    cur_orig: list[Token] = []
    cur_trans: list[Token] = []
    seg_start_ms: int | None = None
    seg_end_ms: int | None = None
    last_orig_end_ms: int | None = None
    pending_flush = False

    def flush(force: bool = False) -> None:
        nonlocal cur_orig, cur_trans, seg_start_ms, seg_end_ms
        if not cur_orig and not cur_trans:
            return
        if not force and seg_end_ms is not None and seg_start_ms is not None:
            if (seg_end_ms - seg_start_ms) < min_segment_ms and segments:
                # Gộp với segment trước nếu quá ngắn
                prev = segments[-1]
                prev.end_ms = max(prev.end_ms, seg_end_ms)
                prev.source_tokens.extend(cur_orig)
                prev.translation_tokens.extend(cur_trans)
                prev.source_text = _join_tokens(prev.source_tokens)
                prev.translated_text = _join_tokens(prev.translation_tokens)
                cur_orig, cur_trans = [], []
                seg_start_ms = seg_end_ms = None
                return

        seg = Segment(
            index=len(segments),
            start_ms=seg_start_ms or 0,
            end_ms=seg_end_ms or (seg_start_ms or 0),
            source_tokens=cur_orig,
            translation_tokens=cur_trans,
            source_text=_join_tokens(cur_orig),
            translated_text=_join_tokens(cur_trans),
        )
        segments.append(seg)
        cur_orig, cur_trans = [], []
        seg_start_ms = seg_end_ms = None

    for tok in tokens:
        if _is_translation(tok):
            # Translation tokens thường đến SAU dấu kết câu của source.
            # Tích luỹ vào segment hiện tại; flush diễn ra khi token original
            # tiếp theo xuất hiện.
            cur_trans.append(tok)
            continue

        if not _is_original(tok):
            continue

        # Khi có original token mới đến và đang chờ flush từ điều kiện trước
        # (dấu câu hoặc max length), flush ngay bây giờ — translation cho
        # câu trước đã được thu thập đầy đủ.
        if pending_flush:
            flush()
            pending_flush = False

        # Khoảng lặng cũng là tín hiệu cắt segment trước
        if (
            last_orig_end_ms is not None
            and tok.start_ms - last_orig_end_ms > pause_split_ms
            and (cur_orig or cur_trans)
        ):
            flush()

        if seg_start_ms is None:
            seg_start_ms = tok.start_ms
        cur_orig.append(tok)
        seg_end_ms = tok.end_ms
        last_orig_end_ms = tok.end_ms

        # Đánh dấu chờ flush (sẽ flush khi original tiếp theo đến)
        if _ends_sentence(tok.text):
            pending_flush = True
        elif (
            seg_start_ms is not None
            and (tok.end_ms - seg_start_ms) >= max_segment_ms
        ):
            pending_flush = True

    flush(force=True)
    return segments


def _join_tokens(tokens: list[Token]) -> str:
    """Ghép text từ tokens. Soniox tokens thường đã chứa whitespace cần thiết
    (e.g. " hello", "world"). Ghép thẳng và strip ngoài cùng."""
    return "".join(t.text for t in tokens).strip()
