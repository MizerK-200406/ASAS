# Tài liệu Kỹ thuật & Kiến trúc Hệ thống ASAS
> **Adaptive Student Assessment System** — Nền tảng Đánh giá & Hỗ trợ Học tập Cá nhân hóa

---

## 1. Sơ đồ Kiến trúc Tương tác (Architecture Diagram)

Hệ thống được thiết kế và trực quan hóa bằng công nghệ **Archify**, tạo ra tệp HTML tương tác độc lập (Standalone Interactive Diagram) tại:
- **Đường dẫn tệp**: [`docs/diagrams/asas_architecture.html`](diagrams/asas_architecture.html)
- **Đặc tả nguồn JSON**: [`docs/diagrams/candidate.json`](candidate.json)

### Cách mở trên trình duyệt
Chạy lệnh sau trong PowerShell tại thư mục gốc của dự án:
```powershell
Start-Process "docs\diagrams\asas_architecture.html"
```

### Các phím tắt tương tác trong sơ đồ
| Phím tắt | Chức năng | Mô tả chi tiết |
| :---: | :--- | :--- |
| <kbd>T</kbd> | **Đổi Theme** | Chuyển đổi qua lại giữa giao diện Tối (Dark) và Sáng (Light). |
| <kbd>M</kbd> | **Bản đồ Radar** | Bật/tắt bản đồ thu nhỏ góc nhìn tổng quan (Mini-map). |
| <kbd>F</kbd> | **Chế độ Thuyết trình** | Bật/tắt toàn màn hình không viền (Presentation Mode). |
| <kbd>E</kbd> | **Xuất file ảnh** | Mở menu xuất sơ đồ định dạng vector SVG hoặc ảnh PNG sắc nét. |
| <kbd>+</kbd> / <kbd>-</kbd> | **Phóng to / Thu nhỏ** | Zoom mượt mà vào từng vùng kiến trúc. |
| <kbd>0</kbd> | **Khôi phục tỷ lệ** | Trở về khung nhìn mặc định toàn cảnh. |
| **Click vào khối** | **Chi tiết & Mã nguồn** | Xem thông tin chi tiết và liên kết trực tiếp tới file code tương ứng. |

---

## 2. Bản đồ Cấu trúc Dự án (Repository Map)

```text
ASAS/
├── data/                            # Lưu trữ cơ sở dữ liệu SQLite kép (Dual DB)
│   ├── users.db                     # Dữ liệu thực thể: học sinh, kết quả quiz, tiến độ SM-2, nhật ký
│   └── chats.db                     # Dữ liệu sự kiện: phiên hội thoại và lịch sử tin nhắn
├── docs/                            # Thư mục tài liệu kỹ thuật
│   ├── README.md                    # Tài liệu tổng quan kiến trúc & hướng dẫn sơ đồ
│   └── diagrams/
│       ├── candidate.json           # Bản đặc tả JSON nguồn của sơ đồ kiến trúc
│       └── asas_architecture.html   # Sơ đồ kiến trúc tương tác hoàn chỉnh
├── src/asas/                        # Mã nguồn nghiệp vụ chính (Modular Monolith)
│   ├── core/                        # Cấu hình Pydantic, LLM Client (NVIDIA NIM), Token Budget
│   └── modules/
│       ├── agents/                  # Hệ thống Đa tác tử (Supervisor, Tutor, Evaluator, Planner, Orchestrator)
│       ├── quiz/                    # Dịch vụ sinh đề và chấm điểm câu hỏi trắc nghiệm
│       ├── flashcard/               # Dịch vụ sinh bộ thẻ ghi nhớ thuật toán SM-2
│       ├── memory/                  # Tầng lưu trữ CSDL kép, Session Memory, Kho lưu trữ DAO
│       └── tools/                   # Rào chắn bảo mật: Python Sandbox & DuckDuckGo Search có kiểm duyệt
├── tests/                           # Kiểm thử tự động (Phản chiếu 1:1 với src/)
│   ├── unit/
│   │   ├── core/                    # Kiểm thử config, client LLM, token manager
│   │   ├── modules/
│   │   │   ├── agents/              # Kiểm thử hành vi và định tuyến của các tác tử
│   │   │   ├── quiz/                # Kiểm thử sinh đề, chấm bài và schemas Quiz
│   │   │   ├── flashcard/           # Kiểm thử tạo thẻ và schemas Flashcard
│   │   │   ├── memory/              # Kiểm thử CSDL kép, thuật toán SM-2, DAO repository
│   │   │   └── tools/               # Kiểm thử sandbox, web search, tool registry
│   │   └── diagrams/                # Kiểm thử tính toàn vẹn của sơ đồ Archify
├── playground.py                    # Giao diện trải nghiệm CLI (Quiz, Flashcard, Trợ lý AI, Hồ sơ)
└── requirements.txt                 # Danh sách gói phụ thuộc Python
```

---

## 3. Các Nguyên tắc Kiến trúc Cốt lõi

1. **Mặt tiền Điều phối Đa tác tử (Supervisor Facade Pattern)**:
   - Người học chỉ tương tác trực tiếp với một "Trợ lý Học tập AI" duy nhất.
   - `SupervisorAgent` đọc ý định của học sinh và điều phối ngầm tới tác tử phù hợp (`TutorAgent` để giải thích lý thuyết/code, `EvaluatorAgent` để chấm điểm và phản biện, `PlannerAgent` để đề xuất lộ trình).
2. **Phân vùng CSDL Kép (Dual-Database Segregation)**:
   - Tách rời vật lý giữa `data/users.db` (dữ liệu hồ sơ, kết quả học tập) và `data/chats.db` (dữ liệu tin nhắn chat tần suất cao).
   - Tối ưu hóa I/O, giảm kích thước file sao lưu và đảm bảo tính riêng tư.
3. **Rào chắn An toàn (Security Sandbox & Search Guardrails)**:
   - `SafePythonSandbox`: Thực thi Python trong môi trường headless, chặn hoàn toàn các import và built-in nguy hiểm (`os`, `sys`, `open`, `eval`).
   - `WebSearchGuardrails`: Tìm kiếm chỉ phục vụ kiểm chứng dữ liệu tri thức của tác tử, nghiêm cấm hoạt động như một proxy tìm kiếm hộ người dùng.
