"""Playground Script - Trải nghiệm trực tiếp AI Study Assistant (ASAS) với NVIDIA API."""

import asyncio
import hashlib
import os
import re
import sys
import uuid


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
from asas.core.llm_client import LLMClient
from asas.modules.tools.calculator import CalculatorTool
from asas.modules.tools.python_executor import PythonExecutorTool
from asas.modules.tools.web_search import WebSearchTool
from asas.modules.tools.registry import create_default_registry
from asas.modules.memory.service import MemoryService
from asas.modules.agents.orchestrator import MultiAgentOrchestrator


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
    search_tool = WebSearchTool()
    llm_client = LLMClient()
    tool_registry = create_default_registry()

    # Khởi tạo Memory Service (SQLite async)
    memory_service = MemoryService(db_path="data/asas.db")
    await memory_service.initialize()

    # Khởi tạo Multi-Agent Orchestrator
    orchestrator = MultiAgentOrchestrator(
        llm_client=llm_client,
        tool_registry=tool_registry,
        memory_service=memory_service,
    )

    # -------------------------------------------------------------
    # Quản lý danh tính học sinh (Identity & Profile Selection)
    # -------------------------------------------------------------
    existing_students = await memory_service.get_all_students()
    student_profile = None

    if existing_students:
        print("\n" + "=" * 60)
        print("👥 DANH SÁCH HỒ SƠ HỌC SINH ĐÃ LƯU TRONG CƠ SỞ DỮ LIỆU")
        print("=" * 60)
        for idx, st in enumerate(existing_students, 1):
            grade_str = f"[{st.grade_level}]" if st.grade_level else ""
            school_str = f"({st.school})" if st.school else ""
            print(f"  {idx}. {st.name} {grade_str} {school_str} - Mã ID: {st.student_id}")

        print("\n[LỰA CHỌN ĐĂNG NHẬP]:")
        print("  - Nhập số thứ tự (1, 2, ...) để chọn nhanh hồ sơ.")
        print("  - Nhập 'new' để tạo một hồ sơ học sinh mới hoàn toàn.")
        print("  - Nhập mã ID / Username cụ thể để đăng nhập trực tiếp.")
        user_choice = input("\n👉 Lựa chọn của bạn (Nhấn Enter để chọn hồ sơ số 1): ").strip()

        if not user_choice and len(existing_students) > 0:
            student_profile = existing_students[0]
        elif user_choice.isdigit() and 1 <= int(user_choice) <= len(existing_students):
            student_profile = existing_students[int(user_choice) - 1]
        elif user_choice.lower() == "new":
            student_profile = None
        else:
            # Tìm theo student_id chính xác
            for st in existing_students:
                if st.student_id.lower() == user_choice.lower():
                    student_profile = st
                    break

    # Nếu chưa có hồ sơ nào hoặc người dùng chọn tạo mới:
    if not student_profile:
        print("\n" + "=" * 60)
        print("📝 ĐĂNG KÝ HỒ SƠ HỌC SINH MỚI (CHỐNG TRÙNG DANH TÍNH)")
        print("=" * 60)
        raw_name = input("👤 Họ và tên học sinh (VD: Nguyễn Duy Long, Phạm Dương): ").strip()
        if not raw_name:
            raw_name = "Nguyễn Duy Long"

        default_uname = re.sub(r'[^a-zA-Z0-9]', '', raw_name.lower())[:8] or "student"
        suggested_id = f"{default_uname}_{uuid.uuid4().hex[:4]}"
        uname_input = input(f"🔑 Mã học sinh / Username riêng biệt (Enter để dùng '{suggested_id}'): ").strip()
        if not uname_input:
            uname_input = suggested_id

        student_id_val = f"st_{uname_input.lower().strip()}"
        grade_input = input("🏫 Bạn đang học lớp mấy? (VD: Lớp 10, Lớp 12, Đại học - Enter để bỏ qua): ").strip()
        school_input = input("🏛️  Trường học của bạn? (VD: THPT Chuyên Hà Nội - Amsterdam - Enter để bỏ qua): ").strip()
        goal_input = input("🎯 Mục tiêu học tập? (VD: Đạt 9.0 điểm môn Toán - Enter để bỏ qua): ").strip()

        student_profile = await memory_service.get_or_create_student(
            student_id=student_id_val,
            name=raw_name,
            grade_level=grade_input or "Lớp 12",
            school=school_input or "THPT",
            target_goal=goal_input or "Học giỏi toàn diện",
        )

    student_id = student_profile.student_id
    grade_badge = f"[{student_profile.grade_level}]" if student_profile.grade_level else ""
    school_badge = f"- {student_profile.school}" if student_profile.school else ""
    print(f"\n👋 Đã đăng nhập: {student_profile.name} {grade_badge} {school_badge} (Mã ID: {student_profile.student_id})")
    print("✨ Hệ thống Hồ sơ cá nhân hóa, Bộ nhớ & Spaced Repetition đã sẵn sàng.\n")

    while True:
        print("\n--- MENU TRẢI NGHIỆM ---")
        print("1. Tạo bộ câu hỏi trắc nghiệm (Quiz) & Làm bài thử (Tự động lưu điểm)")
        print("2. Tạo bộ thẻ ghi nhớ (Flashcards) (Tự động nạp vào lịch ôn tập)")
        print("3. Dùng thử công cụ Calculator (Tính toán toán học an toàn)")
        print("4. Dùng thử công cụ Safe Python Sandbox (Chạy mã Python an toàn)")
        print("5. Dùng thử công cụ Web Search (Tìm kiếm internet miễn phí qua DuckDuckGo)")
        print("6. Chat Đa tác tử thông minh (Multi-Agent: Supervisor -> Tutor / Evaluator / Planner)")
        print("7. Xem Hồ sơ & Thống kê học tập cá nhân (SQLite Database)")
        print("8. Ôn tập Flashcards thông minh (Thuật toán Spaced Repetition SM-2)")
        print("0. Thoát")
        choice = input("\nChọn chức năng (0/1/2/3/4/5/6/7/8): ").strip()

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

                # AI tạo lời nhận xét & định hướng cải thiện
                print("⏳ AI đang phân tích bài giải, đưa ra lời khen ngợi và chỉ dẫn lỗi sai...")
                mistakes = [
                    f"Câu {d['question_index'] + 1} (Bạn chọn {d['user_answer']}, đáp án đúng là {d['correct_answer']})"
                    for d in result.details if not d["is_correct"]
                ]
                feedback_prompt = (
                    f"Học sinh {student_profile.name} vừa làm bài kiểm tra chủ đề '{quiz.topic}' đạt {result.score_percentage}% ({result.correct_count}/{result.total_questions} câu).\n"
                    f"Các câu làm sai: {', '.join(mistakes) if mistakes else 'Không có (Làm đúng 100%)'}.\n"
                    f"Hãy đưa ra nhận xét sư phạm ngắn gọn (tối đa 3-4 dòng):\n"
                    f"- Lời khen ngợi động viên (1 câu)\n"
                    f"- Nhận xét lỗi sai / Lỗ hổng kiến thức cần chú ý (1 câu)\n"
                    f"- Hành động hoặc chủ đề cần ôn luyện tiếp theo (1 câu)"
                )
                try:
                    ai_feedback = await llm_client.chat_completion(
                        messages=[{"role": "user", "content": feedback_prompt}],
                        temperature=0.3,
                    )
                except Exception:
                    ai_feedback = f"Em đã hoàn thành bài thi với kết quả {result.score_percentage}%! Hãy tiếp tục rèn luyện nhé."

                print(f"\n🤖 [LỜI PHÊ & GÓP Ý CỦA AI]:\n{ai_feedback}")

                # Lưu kết quả vào CSDL SQLite dài hạn
                await memory_service.record_quiz_result(
                    student_id=student_id,
                    topic=quiz.topic,
                    score_percentage=result.score_percentage,
                    total_questions=result.total_questions,
                    correct_count=result.correct_count,
                    ai_critique=ai_feedback,
                )
                print("\n💾 [Memory] Đã tự động lưu kết quả bài thi và lời nhận xét của AI vào hồ sơ!")

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

                # Tự động nạp thẻ vào hệ thống ôn tập SM-2
                await memory_service.import_flashcard_set(student_id=student_id, card_set=flashcards)
                print(f"\n💾 [Memory] Đã lưu {len(flashcards.cards)} thẻ vào hệ thống ôn tập ngắt quãng (SM-2) của bạn!")

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

        elif choice == "5":
            print("\n🔍 DUCKDUCKGO WEB SEARCH (100% Free - Không cần API Key)")
            query_input = input("Nhập từ khóa tìm kiếm (VD: FastAPI tutorial, Python 3.12 new features): ").strip()
            if not query_input:
                query_input = "Python 3.12 new features"

            print(f"\n⏳ Đang tìm kiếm trên Internet: '{query_input}'...")
            res = await search_tool.execute(query=query_input, max_results=3)
            if res.success:
                print(f"\n✅ KẾT QUẢ TÌM KIẾM:\n{res.output}")
            else:
                print(f"\n❌ LỖI TÌM KIẾM:\n{res.error}")

        elif choice == "6":
            print("\n" + "=" * 60)
            print("🤖 HỆ THỐNG ĐA TÁC TỬ THÔNG MINH (MULTI-AGENT ORCHESTRATION)")
            print("1. Supervisor: Phân tích câu hỏi & tự động điều phối chuyên gia.")
            print("2. Tutor Agent: Giảng dạy Socratic & tự động gọi Tools tính toán/code.")
            print("3. Evaluator Agent: Chấm điểm bài giải, phản biện logic & tìm lỗi sai.")
            print("4. Planner Agent: Phân tích điểm yếu từ Memory để lên lộ trình học tập.")
            print("Gõ 'exit' hoặc 'q' để quay lại menu chính.")
            print("=" * 60 + "\n")

            session = memory_service.get_or_create_session(
                session_id=f"multiagent_{student_id}",
                max_messages=10,
            )

            while True:
                prompt = input("\n👤 Bạn: ").strip()
                if not prompt:
                    continue
                if prompt.lower() in ("exit", "q", "quit"):
                    print("Quay lại menu chính...")
                    break

                session.add_message("user", prompt)
                print("⏳ Supervisor đang phân tích câu hỏi và điều phối tới chuyên gia phù hợp...")
                try:
                    decision, response = await orchestrator.dispatch(
                        messages=session.to_openai_messages(),
                        student_id=student_id,
                    )

                    role_name = {
                        "tutor": "GIA SƯ (TUTOR AGENT)",
                        "evaluator": "GIÁM KHẢO (EVALUATOR AGENT)",
                        "planner": "CỐ VẤN LỘ TRÌNH (PLANNER AGENT)",
                    }.get(decision.next_agent.value, decision.next_agent.value.upper())

                    print(f"\n🧭 [Supervisor điều phối]: -> Chuyển tới {role_name}")
                    print(f"💡 [Lý do điều phối]: {decision.reasoning}")
                    print(f"\n🤖 [{role_name}]:\n{response.content}")

                    session.add_message("assistant", response.content)

                    # Ghi nhật ký tương tác
                    await memory_service.log_activity(
                        student_id=student_id,
                        action_type="CHAT_AGENT",
                        description=f"Hỏi {role_name}: '{prompt[:30]}...'",
                    )
                except Exception as e:
                    print(f"❌ Lỗi khi điều phối đa tác tử: {e}")

        elif choice == "7":
            print("\n" + "=" * 65)
            print("📊 HỒ SƠ HỌC TẬP & NHẬT KÝ HOẠT ĐỘNG (SQLITE DATABASE)")
            print("=" * 65)
            summary = await memory_service.get_student_summary(student_id)
            profile = summary["profile"]
            stats = summary["quiz_stats"]
            recent = summary["recent_quizzes"]
            activities = summary.get("recent_activities", [])

            print(f"👤 Học sinh: {profile.name} (Mã ID: {profile.student_id})")
            if profile.grade_level:
                print(f"🏫 Khối / Lớp: {profile.grade_level}")
            if profile.school:
                print(f"🏛️  Trường học: {profile.school}")
            if profile.target_goal:
                print(f"🎯 Mục tiêu: {profile.target_goal}")
            if profile.learning_style:
                print(f"💡 Phong cách học: {profile.learning_style}")

            print("\n📈 THỐNG KÊ KẾT QUẢ HỌC TẬP:")
            print(f"- Tổng số bài Quiz đã làm: {stats['total_quizzes']}")
            print(f"- Điểm trung bình: {stats['average_score']}%")
            print(f"- Tổng số câu làm đúng: {stats['total_correct']}/{stats['total_questions']}")

            print("\n📜 5 bài Quiz gần nhất:")
            if not recent:
                print("  (Chưa có bài quiz nào được ghi nhận)")
            else:
                for idx, q in enumerate(recent, 1):
                    date_str = q.completed_at.strftime("%Y-%m-%d %H:%M")
                    q_id_badge = f"[Mã #{q.id}] " if q.id else ""
                    print(f"  {idx}. [{date_str}] {q_id_badge}Chủ đề: {q.topic} - Điểm: {q.score_percentage}% ({q.correct_count}/{q.total_questions})")

            print("\n🕒 5 Hoạt động gần nhất:")
            if not activities:
                print("  (Chưa có hoạt động nào được ghi nhận)")
            else:
                for idx, act in enumerate(activities, 1):
                    act_date = act.created_at.strftime("%Y-%m-%d %H:%M")
                    print(f"  {idx}. [{act_date}] [{act.action_type}] {act.description}")

            # Chế độ xem chi tiết bài kiểm tra (Detail Drilldown on demand)
            if recent:
                print("\n" + "-" * 65)
                detail_choice = input("👉 Nhập số thứ tự (1, 2, ...) hoặc Mã bài thi để xem chi tiết nhận xét & lời phê AI (Enter để quay lại): ").strip()
                if detail_choice:
                    target_quiz = None
                    if detail_choice.isdigit():
                        num = int(detail_choice)
                        if 1 <= num <= len(recent):
                            target_quiz = recent[num - 1]
                        else:
                            target_quiz = await memory_service.get_quiz_record_by_id(num)
                    elif detail_choice.startswith("#") and detail_choice[1:].isdigit():
                        target_quiz = await memory_service.get_quiz_record_by_id(int(detail_choice[1:]))

                    if target_quiz:
                        print("\n" + "=" * 65)
                        badge_id = f"#{target_quiz.id} " if target_quiz.id else ""
                        print(f"🔍 CHI TIẾT BÀI KIỂM TRA {badge_id}- CHỦ ĐỀ: {target_quiz.topic.upper()}")
                        print("=" * 65)
                        date_str = target_quiz.completed_at.strftime("%Y-%m-%d %H:%M:%S")
                        print(f"📅 Thời gian hoàn thành: {date_str}")
                        print(f"🎯 Điểm số: {target_quiz.score_percentage}% ({target_quiz.correct_count}/{target_quiz.total_questions} câu)")
                        if target_quiz.ai_praise:
                            print(f"\n🌟 Lời khen ngợi từ AI:\n   {target_quiz.ai_praise}")
                        if target_quiz.ai_critique:
                            print(f"\n💬 Nhận xét sư phạm & Góp ý từ AI:\n   {target_quiz.ai_critique}")
                        if target_quiz.improvement_plan:
                            print(f"\n🚀 Kế hoạch cải thiện đề xuất:\n   {target_quiz.improvement_plan}")
                        print("=" * 65)
                        input("\n👉 Nhấn Enter để quay lại menu chính...")
                    else:
                        print("⚠️ Không tìm thấy bài kiểm tra phù hợp.")

        elif choice == "8":
            print("\n" + "=" * 55)
            print("🧠 ÔN TẬP FLASHCARDS THÔNG MINH (SUPERMEMO SM-2)")
            print("Hệ thống tự động lọc các thẻ đã đến hạn cần ôn tập hôm nay.")
            print("=" * 55)

            due_cards = await memory_service.get_due_flashcards(student_id)
            if not due_cards:
                print("\n🎉 Tuyệt vời! Hiện tại bạn không có thẻ nào cần ôn tập hôm nay.")
            else:
                print(f"\n📚 Bạn có {len(due_cards)} thẻ cần ôn tập:\n")
                for idx, card in enumerate(due_cards, 1):
                    print(f"--- Thẻ {idx}/{len(due_cards)} ---")
                    print(f"❓ Mặt trước: {card.front}")
                    input("👉 Nhấn Enter để xem đáp án...")
                    print(f"✅ Mặt sau: {card.back}")

                    while True:
                        q_str = input("\nĐánh giá mức độ nhớ (0: Quên sạch -> 5: Nhớ hoàn hảo): ").strip()
                        if q_str in ("0", "1", "2", "3", "4", "5"):
                            q_val = int(q_str)
                            break
                        print("Vui lòng nhập một số từ 0 đến 5!")

                    updated = await memory_service.review_flashcard(card.card_id, quality=q_val)
                    print(f"📅 SM-2 xếp lịch: Lần ôn tiếp theo sau {updated.interval_days} ngày (Ease Factor: {updated.ease_factor})\n")
                print("🎉 Bạn đã hoàn thành phiên ôn tập Flashcard hôm nay!")

        else:
            print("Lựa chọn không hợp lệ, vui lòng chọn lại!")


if __name__ == "__main__":
    asyncio.run(main())
