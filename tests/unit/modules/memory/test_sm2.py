"""Unit tests for the SuperMemo SM-2 Spaced Repetition Algorithm."""

from datetime import datetime, timedelta, timezone
from asas.modules.memory.schemas import SM2ReviewInput
from asas.modules.memory.sm2 import calculate_sm2


def test_sm2_failed_review_resets_repetition_and_interval():
    """Khi học sinh đánh giá quality < 3 (quên hoặc sai), interval reset về 1 ngày và repetition về 0."""
    now = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
    # Thẻ đã qua 3 lần lặp, interval 15 ngày, nhưng lần này quality = 2
    input_data = SM2ReviewInput(quality=2, repetition=3, interval_days=15, ease_factor=2.5)

    result = calculate_sm2(input_data, review_datetime=now)

    assert result.repetition == 0
    assert result.interval_days == 1
    assert result.next_review == now + timedelta(days=1)
    # EF giảm khi quality thấp, nhưng không đổi interval về 0
    assert result.ease_factor < 2.5


def test_sm2_first_successful_repetition():
    """Lần ôn tập đầu tiên thành công (quality >= 3, repetition = 0) -> interval = 1 ngày, repetition = 1."""
    now = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
    input_data = SM2ReviewInput(quality=4, repetition=0, interval_days=1, ease_factor=2.5)

    result = calculate_sm2(input_data, review_datetime=now)

    assert result.repetition == 1
    assert result.interval_days == 1
    assert result.next_review == now + timedelta(days=1)


def test_sm2_second_successful_repetition():
    """Lần ôn tập thứ 2 thành công (repetition = 1) -> interval = 6 ngày, repetition = 2."""
    now = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
    input_data = SM2ReviewInput(quality=5, repetition=1, interval_days=1, ease_factor=2.5)

    result = calculate_sm2(input_data, review_datetime=now)

    assert result.repetition == 2
    assert result.interval_days == 6
    assert result.next_review == now + timedelta(days=6)
    # Quality 5 làm tăng Ease Factor
    assert result.ease_factor > 2.5


def test_sm2_third_successful_repetition():
    """Lần ôn tập thứ 3+ thành công -> interval = round(prev_interval * EF)."""
    now = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
    # prev interval = 6, EF = 2.5, quality = 4
    input_data = SM2ReviewInput(quality=4, repetition=2, interval_days=6, ease_factor=2.5)

    result = calculate_sm2(input_data, review_datetime=now)

    assert result.repetition == 3
    # 6 * 2.5 = 15
    assert result.interval_days == 15
    assert result.next_review == now + timedelta(days=15)


def test_sm2_ease_factor_minimum_bound():
    """Ease factor không bao giờ được giảm xuống dưới 1.3."""
    now = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
    # EF đang ở 1.3, gặp quality = 0 (giảm mạnh nhất)
    input_data = SM2ReviewInput(quality=0, repetition=0, interval_days=1, ease_factor=1.3)

    result = calculate_sm2(input_data, review_datetime=now)

    assert result.ease_factor >= 1.3
    assert result.ease_factor == 1.3
