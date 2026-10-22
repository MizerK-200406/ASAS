"""SuperMemo SM-2 Spaced Repetition Algorithm Implementation.

Tài liệu tham khảo thuật toán SM-2:
- P. A. Wozniak, 'Optimization of learning', 1990.
- Quality (q) thang 0-5.
- Ease Factor (EF) khởi đầu 2.5, tối thiểu 1.3.
"""

from datetime import datetime, timedelta
from typing import Optional
from asas.modules.memory.schemas import SM2ReviewInput, SM2ReviewResult, utc_now


def calculate_sm2(
    input_data: SM2ReviewInput,
    review_datetime: Optional[datetime] = None,
) -> SM2ReviewResult:
    """Tính toán thời gian ôn tập tiếp theo và hệ số độ dễ (Ease Factor) theo thuật toán SuperMemo SM-2.

    Args:
        input_data: Thông tin đánh giá thẻ (quality, repetition, interval_days, ease_factor).
        review_datetime: Thời điểm đánh giá (mặc định là thời gian UTC hiện tại).

    Returns:
        SM2ReviewResult: Kết quả bao gồm số lần lặp mới, khoảng cách ngày mới, EF mới và thời điểm ôn tập tiếp theo.
    """
    if review_datetime is None:
        review_datetime = utc_now()

    q = input_data.quality
    ef = input_data.ease_factor
    rep = input_data.repetition
    interval = input_data.interval_days

    # 1. Cập nhật Ease Factor (EF)
    # Công thức SM-2: EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    new_ef = ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    if new_ef < 1.3:
        new_ef = 1.3
    new_ef = round(new_ef, 2)

    # 2. Cập nhật Số lần lặp (Repetition) và Khoảng cách ngày (Interval)
    if q < 3:
        # Nếu học sinh không nhớ (quality < 3), reset chuỗi ôn tập về 1 ngày
        new_rep = 0
        new_interval = 1
    else:
        # Nếu nhớ thành công (quality >= 3)
        if rep == 0:
            new_interval = 1
        elif rep == 1:
            new_interval = 6
        else:
            new_interval = round(interval * new_ef)
        new_rep = rep + 1

    next_review = review_datetime + timedelta(days=new_interval)

    return SM2ReviewResult(
        repetition=new_rep,
        interval_days=new_interval,
        ease_factor=new_ef,
        next_review=next_review,
    )
