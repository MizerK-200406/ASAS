# ASAS - AI Assessment System

Nền tảng Đánh giá & Hỗ trợ Học tập Cá nhân hóa sử dụng kiến trúc AI Engineering hiện đại:
- **Tạo đề trắc nghiệm AI (Quiz Generation)**: Sinh bộ câu hỏi đạt chuẩn sư phạm theo chủ đề và cấp độ.
- **AI Evaluator Agent (Đánh giá sư phạm)**: Phân tích sâu kết quả bài thi, nhận diện chính xác các lỗ hổng kiến thức (knowledge gaps), nguyên nhân sai sót/ngộ nhận, chỉ ra điểm mạnh và đưa ra lời khuyên cùng kế hoạch hành động cải thiện.
- **100% Free Tech Stack**: Vận hành hiệu quả với chi phí tối ưu.

## Tech Stack
- **Python**: 3.12+ (Quản lý qua `uv`)
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (Cực nhanh, hỗ trợ PEP 621 & lockfile)
- **LLM Provider**: NVIDIA NIM API (OpenAI-compatible)
- **Model**: deepseek-ai/deepseek-v4-flash
- **Framework**: FastAPI, Pydantic v2, asyncpg (PostgreSQL)
- **Testing**: Pytest (TDD workflow)

## Cài đặt & Sử dụng với `uv`

### 1. Đồng bộ môi trường (Sync dependencies)
```bash
uv sync
```

### 2. Chạy Kiểm thử (Unit Tests)
```bash
uv run pytest
```

### 3. Khởi chạy RESTful API Server
```bash
uv run uvicorn asas.api.app:app --reload --port 8000
```
Truy cập Swagger Docs tại: `http://localhost:8000/docs`

### 4. Khởi chạy Giao diện Dòng lệnh (CLI Playground)
```bash
uv run python playground.py
```
