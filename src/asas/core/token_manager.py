"""Token management and budget-aware truncation utilities for LLM prompts and tools."""

from typing import List


def estimate_tokens(text: str) -> int:
    """Ước lượng số token của một chuỗi văn bản (hỗ trợ cả Tiếng Anh và Tiếng Việt có dấu).

    Quy ước tiêu chuẩn:
    - Tiếng Anh: trung bình ~4 ký tự hoặc 0.75 từ trên 1 token.
    - Tiếng Việt (có dấu): trung bình ~3.2 - 3.6 ký tự trên 1 token do dấu thanh.
    """
    if not text:
        return 0

    cleaned = text.strip()
    if not cleaned:
        return 0

    char_count = len(cleaned)
    # Dùng hệ số an toàn 3.5 ký tự / token cho ngữ cảnh đa ngữ
    estimated = int(char_count / 3.5)
    return max(1, estimated)


def truncate_text_by_tokens(text: str, max_tokens: int) -> str:
    """Cắt tỉa văn bản theo ngân sách token mà không làm đứt giữa chừng từ ngữ.

    Args:
        text: Chuỗi văn bản cần cắt.
        max_tokens: Số token tối đa cho phép.

    Returns:
        str: Chuỗi văn bản đã được cắt gọn (kèm '...' nếu bị cắt).
    """
    if not text or max_tokens <= 0:
        return ""

    if estimate_tokens(text) <= max_tokens:
        return text

    words = text.split()
    accumulated_words: List[str] = []

    for word in words:
        candidate = " ".join(accumulated_words + [word])
        # Dành chỗ cho dấu "..."
        if estimate_tokens(candidate) > max_tokens - 1:
            break
        accumulated_words.append(word)

    if not accumulated_words:
        # Trường hợp 1 từ duy nhất quá dài
        char_limit = max(1, int(max_tokens * 3))
        return text[:char_limit] + "..."

    return " ".join(accumulated_words) + "..."


def truncate_snippets_by_budget(
    snippets: List[str],
    max_snippet_tokens: int = 150,
    total_budget_tokens: int = 600,
) -> List[str]:
    """Cắt tỉa danh sách các đoạn trích (search snippets) tuân thủ ngân sách token tổng.

    Args:
        snippets: Danh sách các đoạn trích thô.
        max_snippet_tokens: Ngân sách token tối đa cho mỗi đoạn trích đơn lẻ.
        total_budget_tokens: Tổng ngân sách token cho toàn bộ các đoạn trích.

    Returns:
        List[str]: Danh sách các đoạn trích đã được tối ưu hóa token.
    """
    trimmed_snippets: List[str] = []
    current_tokens = 0

    for snippet in snippets:
        if not snippet or not snippet.strip():
            continue

        # Cắt ngắn từng snippet nếu vượt quá giới hạn đơn lẻ
        trimmed = truncate_text_by_tokens(snippet.strip(), max_tokens=max_snippet_tokens)
        snippet_tokens = estimate_tokens(trimmed)

        # Kiểm tra nếu thêm vào có vượt tổng ngân sách không
        if current_tokens + snippet_tokens > total_budget_tokens:
            remaining_tokens = total_budget_tokens - current_tokens
            if remaining_tokens > 20:  # Chỉ lấy nếu còn đủ chỗ cho một đoạn có nghĩa
                partial = truncate_text_by_tokens(trimmed, max_tokens=remaining_tokens)
                trimmed_snippets.append(partial)
            break

        trimmed_snippets.append(trimmed)
        current_tokens += snippet_tokens

    return trimmed_snippets
