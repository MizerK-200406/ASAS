"""Playground Script - Trải nghiệm trực tiếp AI Assessment System (ASAS) với Evaluator Agent."""

import asyncio
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
from asas.core.llm_client import LLMClient
from asas.modules.agents.evaluator import EvaluatorAgent
from asas.modules.memory.service import MemoryService
from asas.modules.quiz.schemas import DifficultyLevel, QuizGenerationRequest
from asas.modules.quiz.service import QuizService


async def main():
    print("=" * 65)
    print("🎓 CHÀO MỪNG BẠN ĐẾN VỚI AI ASSESSMENT SYSTEM (ASAS)")
    print("=" * 65)

    # 1. Kiểm tra cấu hình
    try:
        settings = get_settings()
        print(f"✅ Đã kết nối Model: {settings.default_model}")
    except Exception as e:
        print(f"❌ Lỗi cấu hình: Hãy kiểm tra file .env đã có NVIDIA_API_KEY chưa!\nChi tiết: {e}")
        return

    llm_client = LLMClient()
    evaluator_agent = EvaluatorAgent(llm_client=llm_client)
    quiz_service = QuizService(llm_client=llm_client, evaluator_agent=evaluator_agent)

    # Khởi tạo Memory Service
    memory_service = MemoryService()
    await memory_service.initialize()

    # -------------------------------------------------------------
    # Quản lý danh tính học sinh (Identity & Profile Selection)
    # -------------------------------------------------------------
    existing_students = await memory_service.get_all_students()
    student_profile = None

    if existing_students:
        print("\n" + "=" * 65)
        print("👥 DANH SÁCH HỒ SƠ HỌC SINH ĐÃ LƯU TRONG CƠ SỞ DỮ LIỆU")
        print("=" * 65)
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
            for st in existing_students:
                if st.student_id.lower() == user_choice.lower():
                    student_profile = st
                    break

    # Nếu chưa có hồ sơ nào hoặc người dùng chọn tạo mới:
    if not student_profile:
        print("\n" + "=" * 65)
        print("📝 ĐĂNG KÝ HỒ SƠ HỌC SINH MỚI")
        print("=" * 65)
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
    print("✨ Hệ thống Hồ sơ cá nhân hóa & Evaluator Agent đã sẵn sàng.\n")

    while True:
        print("\n" + "=" * 50)
        print("--- MENU CHỨC NĂNG HỆ THỐNG ASAS ---")
        print("=" * 50)
        print("1. Tạo đề trắc nghiệm (Quiz) & Đánh giá lỗ hổng kiến thức với AI Agent")
        print("2. Xem Hồ sơ & Lịch sử học tập (PostgreSQL Database)")
        print("0. Thoát")
        choice = input("\nChọn chức năng (0/1/2): ").strip()

        if choice == "0":
            print("Tạm biệt! Hẹn gặp lại bạn.")
            break

        elif choice == "1":
            topic = input("\nNhập chủ đề bạn muốn kiểm tra (VD: Python Basics, Transformer, Lượng giác): ").strip()
            if not topic:
                topic = "Python Basics"

            print(f"\n⏳ Đang yêu cầu AI thiết kế bộ câu hỏi về '{topic}', vui lòng chờ giây lát...")
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
                grade_result = quiz_service.grade_quiz(quiz=quiz, user_answers=user_answers)
                print(f"👉 Điểm số đạt được: {grade_result.correct_count}/{grade_result.total_questions} ({grade_result.score_percentage}%)")

                # Kích hoạt EvaluatorAgent
                print("\n🤖 ĐANG KÍCH HOẠT EVALUATOR AGENT ĐÁNH GIÁ LỖ HỔNG KIẾN THỨC...")
                try:
                    evaluation = await quiz_service.evaluate_quiz_with_agent(
                        quiz=quiz,
                        user_answers=user_answers,
                        grade_result=grade_result,
                        student_name=student_profile.name,
                    )

                    print("\n" + "=" * 65)
                    print("📋 BẢNG ĐÁNH GIÁ SƯ PHẠM TỪ EVALUATOR AGENT")
                    print("=" * 65)

                    if evaluation.strengths:
                        print("\n🌟 ĐIỂM MẠNH ĐÃ NẮM VỮNG:")
                        for s in evaluation.strengths:
                            print(f"   ✓ {s}")

                    if evaluation.knowledge_gaps:
                        print("\n🔍 LỖ HỔNG KIẾN THỨC & NGỘ NHẬN PHÁT HIỆN ĐƯỢC:")
                        for gap in evaluation.knowledge_gaps:
                            print(f"   ⚠️ {gap}")
                    else:
                        print("\n🔍 LỖ HỔNG KIẾN THỨC: Không có lỗ hổng kiến thức!")

                    print(f"\n💬 NHẬN XÉT SƯ PHẠM CHI TIẾT:\n   {evaluation.critique}")

                    if evaluation.recommendations:
                        print("\n💡 LỜI KHUYÊN & CHỦ ĐỀ CẦN TẬP TRUNG ÔN TẬP:")
                        for rec in evaluation.recommendations:
                            print(f"   👉 {rec}")
                    else:
                        print("\n💡 LỜI KHUYÊN: Bạn đã làm đúng 100%, hãy tiếp tục duy trì phong độ xuất sắc này!")

                    if evaluation.improvement_plan:
                        print(f"\n🚀 KẾ HOẠCH HÀNH ĐỘNG CẢI THIỆN:\n   {evaluation.improvement_plan}")

                    print("=" * 65)

                    # Lưu kết quả vào CSDL PostgreSQL
                    praise_str = ", ".join(evaluation.strengths) if evaluation.strengths else None
                    critique_str = evaluation.critique
                    plan_str = evaluation.improvement_plan or (", ".join(evaluation.recommendations) if evaluation.recommendations else None)

                    record_id = await memory_service.record_quiz_result(
                        student_id=student_id,
                        topic=quiz.topic,
                        score_percentage=grade_result.score_percentage,
                        total_questions=grade_result.total_questions,
                        correct_count=grade_result.correct_count,
                        ai_praise=praise_str,
                        ai_critique=critique_str,
                        improvement_plan=plan_str,
                    )
                    print(f"\n💾 [Memory] Đã lưu kết quả bài thi #{record_id} kèm phân tích của AI vào hồ sơ!")

                except Exception as eval_err:
                    print(f"⚠️ Không thể thực thi Evaluator Agent: {eval_err}")
                    await memory_service.record_quiz_result(
                        student_id=student_id,
                        topic=quiz.topic,
                        score_percentage=grade_result.score_percentage,
                        total_questions=grade_result.total_questions,
                        correct_count=grade_result.correct_count,
                    )

                # Hiển thị đáp án chi tiết
                print("\nChi tiết đáp án & giải thích:")
                for d in grade_result.details:
                    status_badge = "✅ ĐÚNG" if d["is_correct"] else "❌ SAI"
                    print(f"- Câu {d['question_index'] + 1}: {status_badge} (Bạn chọn: {d['user_answer']} | Đáp án đúng: {d['correct_answer']})")
                    print(f"  💡 Giải thích: {d['explanation']}")

            except Exception as e:
                print(f"❌ Lỗi khi thực hiện Quiz: {e}")

        elif choice == "2":
            print("\n" + "=" * 65)
            print("📊 HỒ SƠ HỌC TẬP & DÒNG THỜI GIAN HOẠT ĐỘNG (POSTGRESQL DATABASE)")
            print("=" * 65)
            summary = await memory_service.get_student_summary(student_id, activity_limit=10)
            profile = summary["profile"]
            stats = summary["quiz_stats"]
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
            print(f"- Tổng số câu làm đúng: {stats.get('total_correct', 0)}/{stats.get('total_questions', 0)}")

            print("\n🕒 DÒNG THỜI GIAN HOẠT ĐỘNG GẦN NHẤT:")
            if not activities:
                print("  (Chưa có hoạt động nào được ghi nhận)")
            else:
                for idx, act in enumerate(activities, 1):
                    act_date = act.created_at.strftime("%Y-%m-%d %H:%M")
                    print(f"  {idx}. [{act_date}] 🎯 [{act.action_type}] {act.description}")

            # Tra cứu chi tiết bài Quiz theo mã ID khi cần
            print("\n" + "-" * 65)
            detail_choice = input("👉 Nhập mã bài thi (VD: 1 hoặc #1) để xem lại phân tích lỗi sai từ AI (Enter để quay lại): ").strip()
            if detail_choice:
                clean_id = detail_choice.lstrip("#")
                if clean_id.isdigit():
                    target_quiz = await memory_service.get_quiz_record_by_id(int(clean_id))
                    if target_quiz:
                        print("\n" + "=" * 65)
                        badge_id = f"#{target_quiz.id} " if target_quiz.id else ""
                        print(f"🔍 CHI TIẾT BÀI KIỂM TRA {badge_id}- CHỦ ĐỀ: {target_quiz.topic.upper()}")
                        print("=" * 65)
                        date_str = target_quiz.completed_at.strftime("%Y-%m-%d %H:%M:%S")
                        print(f"📅 Thời gian hoàn thành: {date_str}")
                        print(f"🎯 Điểm số: {target_quiz.score_percentage}% ({target_quiz.correct_count}/{target_quiz.total_questions} câu)")
                        if target_quiz.ai_praise:
                            print(f"\n🌟 Điểm mạnh ghi nhận:\n   {target_quiz.ai_praise}")
                        if target_quiz.ai_critique:
                            print(f"\n💬 Nhận xét sư phạm & Góp ý từ AI:\n   {target_quiz.ai_critique}")
                        if target_quiz.improvement_plan:
                            print(f"\n🚀 Kế hoạch cải thiện đề xuất:\n   {target_quiz.improvement_plan}")
                        print("=" * 65)
                        input("\n👉 Nhấn Enter để quay lại menu chính...")
                    else:
                        print(f"⚠️ Không tìm thấy bài kiểm tra có mã #{clean_id}.")
                else:
                    print("⚠️ Mã bài thi không hợp lệ.")

        else:
            print("Lựa chọn không hợp lệ, vui lòng chọn lại!")


if __name__ == "__main__":
    asyncio.run(main())
