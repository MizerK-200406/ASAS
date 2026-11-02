# ASAS - AI Assessment System

Nền tảng Đánh giá & Hỗ trợ Học tập Cá nhân hóa sử dụng kiến trúc AI Engineering hiện đại:
- **Tạo đề trắc nghiệm AI (Quiz Generation)**: Sinh bộ câu hỏi đạt chuẩn sư phạm theo chủ đề và cấp độ khó.
- **AI Evaluator Agent (Đánh giá sư phạm)**: Phân tích sâu kết quả bài thi, nhận diện chính xác các lỗ hổng kiến thức (knowledge gaps), nguyên nhân sai sót/ngộ nhận, chỉ ra điểm mạnh và đưa ra lời khuyên cùng kế hoạch hành động cải thiện.
- **100% Free Tech Stack**: Vận hành hiệu quả với chi phí tối ưu.

## Tech Stack
- **Python**: 3.12+
- **LLM Provider**: NVIDIA NIM API (OpenAI-compatible)
- **Model**: deepseek-ai/deepseek-v4-flash
- **Framework**: FastAPI, Pydantic v2
- **Testing**: Pytest (TDD workflow)
