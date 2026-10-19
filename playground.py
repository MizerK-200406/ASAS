"""Playground Script - Trải nghiệm trực tiếp AI Study Assistant (ASAS) với NVIDIA API."""

import asyncio
import os
import sys

# Cấu hình UTF-8 cho Windows Terminal hiển thị tiếng Việt mượt mà
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thêm src vào PYTHONPATH để import module
sys.path.insert(0, os.path.abspath("src"))

from asas.core.config import get_settings
from asas.modules.quiz.schemas import DifficultyLevel, QuizGenerationRequest
from asas.modules.quiz.service import QuizService
from asas.modules.flashcard.schemas import FlashcardGenerationRequest
from asas.modules.flashcard.service import FlashcardService
from asas.modules.tools.calculator import CalculatorTool
from asas.modules.tools.python_executor import PythonExecutorTool


async def main():
    print("=" * 60)
    print("🎓 CHÀO MỪNG BẠN ĐẾN VỚI AI STUDY ASSISTANT (ASAS)")
    print("=" * 60)

    # 1. Kiểm tra cấu hình
    try:
        settings = get_settings()
        print(f"✅ Đã kết nối Model: {settings.default_model}")
    except Exception as e:
        print(f"❌ Lỗi cấu hình: Hãy kiểm tra file .env đã có NVIDIA_API_KEY chưa!\nChi tiết: {e}")
        return

    quiz_service = QuizService()
    flashcard_service = FlashcardService()
    calculator_tool = CalculatorTool()
    python_tool = PythonExecutorTool()

    while True:
        print("\n--- MENU TRẢI NGHIỆM ---")
        print("1. Tạo bộ câu hỏi trắc nghiệm (Quiz) & Làm bài thử")
        print("2. Tạo bộ thẻ ghi nhớ (Flashcards)")
        print("3. Dùng thử công cụ Calculator (Tính toán toán học an toàn)")
        print("4. Dùng thử công cụ Safe Python Sandbox (Chạy mã Python an toàn)")
        print("0. Thoát")
        choice = input("\nChọn chức năng (0/1/2/3/4): ").strip()

        if choice == "0":
            print("Tạm biệt! Hẹn gặp lại bạn.")
            break

        elif choice == "1":
            topic = input("\nNhập chủ đề bạn muốn kiểm tra (VD: Python Basics, Transformer, Git): ").strip()
            if not topic:
                topic = "Python Basics"

            print(f"\n⏳ Đang yêu cầu AI sinh Quiz về '{topic}', vui lòng chờ giây lát...")
            try:
                request = QuizGenerationRequest(
                    topic=topic,
                    num_questions=3,
                    difficulty=DifficultyLevel.EASY,
                    language="vi",
                )
                quiz = await quiz_service.generate_quiz(request)

                print(f"\n🎯 {quiz.title.upper()}")
                user_answers = {}

                # Học sinh làm bài
                for idx, q in enumerate(quiz.questions):
                    print(f"\nCâu {idx + 1}: {q.question}")
                    for opt in q.options:
                        print(f"  {opt.id}. {opt.text}")

                    ans = input("Đáp án của bạn (A/B/C/D): ").strip().upper()
                    user_answers[idx] = ans

                # Chấm điểm tự động
                print("\n📊 ĐANG CHẤM ĐIỂM...")
                result = quiz_service.grade_quiz(quiz=quiz, user_answers=user_answers)
                print(f"👉 Điểm số: {result.correct_count}/{result.total_questions} ({result.score_percentage}%)")

                print("\nChi tiết đáp án & giải thích:")
                for d in result.details:
                    status = "✅ ĐÚNG" if d["is_correct"] else "❌ SAI"
                    print(f"- Câu {d['question_index'] + 1}: {status} (Bạn chọn: {d['user_answer']} | Đáp án đúng: {d['correct_answer']})")
                    print(f"  💡 Giải thích: {d['explanation']}")

            except Exception as e:
                print(f"❌ Lỗi khi tạo Quiz: {e}")

        elif choice == "2":
            topic = input("\nNhập chủ đề hoặc đoạn văn bản cần tạo Flashcard: ").strip()
            if not topic:
                topic = "Machine Learning Loss Functions"

            print(f"\n⏳ Đang yêu cầu AI trích xuất Flashcards cho '{topic}'...")
            try:
                request = FlashcardGenerationRequest(
                    content_or_topic=topic,
                    num_cards=3,
                    language="vi",
                )
                flashcards = await flashcard_service.generate_flashcards(request)

                print(f"\n📌 BỘ THẺ: {flashcards.topic.upper()}")
                for idx, card in enumerate(flashcards.cards):
                    print(f"\n--- Thẻ {idx + 1} ---")
                    print(f"❓ Mặt trước: {card.front}")
                    print(f"💡 Gợi ý: {card.hint or 'Không có'}")
                    input("👉 Nhấn Enter để xem đáp án...")
                    print(f"✅ Mặt sau: {card.back}")
                    print(f"🏷️  Tags: {', '.join(card.tags)}")

            except Exception as e:
                print(f"❌ Lỗi khi tạo Flashcards: {e}")

        elif choice == "3":
            print("\n💡 Hỗ trợ: +, -, *, /, **, sqrt(), sin(), cos(), abs(), pi, e...")
            expr = input("Nhập biểu thức cần tính (VD: sqrt(144) + 2**3, 25 * 4 + 10): ").strip()
            if not expr:
                expr = "sqrt(144) + 2**3"

            print(f"\n⏳ Đang tính toán: '{expr}'...")
            res = await calculator_tool.execute(expression=expr)
            if res.success:
                print(f"✅ KẾT QUẢ: {res.output}")
            else:
                print(f"❌ LỖI: {res.error}")

        elif choice == "4":
            print("\n🐍 SAFE PYTHON SANDBOX (Hỗ trợ toán học, thuật toán, numpy logic, json...)")
            print("Nhập đoạn mã Python (sử dụng print() để xuất kết quả).")
            print("Gõ code trên một dòng, hoặc nhấn Enter để dùng code mẫu tính dãy Fibonacci:")
            code_input = input("Code: ").strip()
            if not code_input:
                code_input = "def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a\nprint('Fibonacci(15) =', fib(15))"

            print(f"\n⏳ Đang thực thi trong Sandbox an toàn...")
            res = await python_tool.execute(code=code_input)
            if res.success:
                print(f"✅ OUTPUT:\n{res.output}")
            else:
                print(f"❌ LỖI / CHẶN BẢO MẬT:\n{res.error}")

        else:
            print("Lựa chọn không hợp lệ, vui lòng chọn lại!")


if __name__ == "__main__":
    asyncio.run(main())
