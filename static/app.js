/**
 * ASAS Frontend Application Logic
 * Modern Pedagogical Assessment & Isolated Device Profile Management
 * Built with Robust Async Lifecycle, Cancellation Tokens & State Guards
 */

document.addEventListener("DOMContentLoaded", () => {
  // ---------------------------------------------------------------------------
  // 1. State & DOM References
  // ---------------------------------------------------------------------------
  const state = {
    currentStudentId: localStorage.getItem("asas_student_id") || "",
    currentStudent: null,
    students: [],
    currentQuiz: null,
    userAnswers: {}, // { questionIndex: optionId }
    timerInterval: null,
    secondsElapsed: 0,

    // Async Lifecycle & Cancellation Controls
    activeQuizRequestId: 0,
    activeGradeRequestId: 0,
    quizGenerateAbortController: null,
    quizGradeAbortController: null,
  };

  // Main Views
  const authSection = document.getElementById("authSection");
  const configSection = document.getElementById("configSection");
  const loadingView = document.getElementById("loadingView");
  const quizSection = document.getElementById("quizSection");
  const resultSection = document.getElementById("resultSection");

  // Navbar Elements
  const userNavActions = document.getElementById("userNavActions");
  const guestNavNotice = document.getElementById("guestNavNotice");
  const navStudentName = document.getElementById("navStudentName");
  const navStudentId = document.getElementById("navStudentId");
  const btnOpenHistory = document.getElementById("btnOpenHistory");
  const btnSwitchAccount = document.getElementById("btnSwitchAccount");

  // Auth / Profile Gate Elements
  const accountSelectBox = document.getElementById("accountSelectBox");
  const studentAccountsList = document.getElementById("studentAccountsList");
  const btnShowCreateAccount = document.getElementById("btnShowCreateAccount");
  const accountCreateBox = document.getElementById("accountCreateBox");
  const createAccountTitle = document.getElementById("createAccountTitle");
  const authCreateForm = document.getElementById("authCreateForm");
  const authStudentName = document.getElementById("authStudentName");
  const authStudentId = document.getElementById("authStudentId");
  const authStudentGrade = document.getElementById("authStudentGrade");
  const authStudentSchool = document.getElementById("authStudentSchool");
  const btnCancelCreateAccount = document.getElementById("btnCancelCreateAccount");

  // Modals
  const historyModal = document.getElementById("historyModal");
  const btnCloseModal = document.getElementById("btnCloseModal");

  // Quiz Form Elements
  const quizForm = document.getElementById("quizForm");
  const topicInput = document.getElementById("topicInput");
  const numQuestionsSelect = document.getElementById("numQuestions");
  const btnGenerate = document.getElementById("btnGenerate");

  // Active Quiz Elements
  const quizSourceBadge = document.getElementById("quizSourceBadge");
  const quizTitle = document.getElementById("quizTitle");
  const quizMeta = document.getElementById("quizMeta");
  const quizTimerText = document.getElementById("quizTimerText");
  const questionsContainer = document.getElementById("questionsContainer");
  const btnCancelQuiz = document.getElementById("btnCancelQuiz");
  const btnSubmitQuiz = document.getElementById("btnSubmitQuiz");

  // Results Elements
  const scoreCircle = document.getElementById("scoreCircle");
  const scorePercentage = document.getElementById("scorePercentage");
  const scoreRatio = document.getElementById("scoreRatio");
  const telemetryBadge = document.getElementById("telemetryBadge");
  const resultSourceBadge = document.getElementById("resultSourceBadge");
  const strengthsBox = document.getElementById("strengthsBox");
  const strengthsList = document.getElementById("strengthsList");
  const gapsBox = document.getElementById("gapsBox");
  const gapsList = document.getElementById("gapsList");
  const critiqueText = document.getElementById("critiqueText");
  const recommendationsBox = document.getElementById("recommendationsBox");
  const recommendationsList = document.getElementById("recommendationsList");
  const planBox = document.getElementById("planBox");
  const planText = document.getElementById("planText");
  const reviewQuestionsContainer = document.getElementById("reviewQuestionsContainer");
  const btnRetake = document.getElementById("btnRetake");
  const btnViewHistoryFromResult = document.getElementById("btnViewHistoryFromResult");

  // ---------------------------------------------------------------------------
  // 2. View Switcher & Zero-Delay Cleanup Helpers
  // ---------------------------------------------------------------------------
  function showView(view) {
    authSection.classList.add("hidden");
    configSection.classList.add("hidden");
    loadingView.classList.add("hidden");
    quizSection.classList.add("hidden");
    resultSection.classList.add("hidden");

    if (view === "auth") authSection.classList.remove("hidden");
    else if (view === "config") configSection.classList.remove("hidden");
    else if (view === "loading") loadingView.classList.remove("hidden");
    else if (view === "quiz") quizSection.classList.remove("hidden");
    else if (view === "result") resultSection.classList.remove("hidden");
  }

  function abortPendingRequests() {
    if (state.quizGenerateAbortController) {
      try { state.quizGenerateAbortController.abort(); } catch (e) {}
      state.quizGenerateAbortController = null;
    }
    if (state.quizGradeAbortController) {
      try { state.quizGradeAbortController.abort(); } catch (e) {}
      state.quizGradeAbortController = null;
    }
  }

  function clearActiveQuizState() {
    clearInterval(state.timerInterval);
    state.currentQuiz = null;
    state.userAnswers = {};
    state.secondsElapsed = 0;
    if (questionsContainer) {
      questionsContainer.innerHTML = "";
    }
  }

  // ---------------------------------------------------------------------------
  // 3. Device Identification & Profile Management (Device Gate)
  // ---------------------------------------------------------------------------
  function getDeviceId() {
    let devId = localStorage.getItem("asas_device_id");
    if (!devId) {
      if (window.crypto && crypto.randomUUID) {
        devId = "dev_" + crypto.randomUUID().replace(/-/g, "").slice(0, 16);
      } else {
        devId = "dev_" + Math.random().toString(36).substring(2, 18);
      }
      localStorage.setItem("asas_device_id", devId);
    }
    return devId;
  }

  async function loadStudentsAndInit() {
    try {
      const devId = getDeviceId();
      const response = await fetch(`/api/v1/students?device_id=${encodeURIComponent(devId)}`);
      if (!response.ok) throw new Error("Không thể tải danh sách học sinh trên thiết bị.");
      const students = await response.json();
      state.students = students;

      if (state.currentStudentId) {
        const found = students.find((st) => st.student_id === state.currentStudentId);
        if (found) {
          loginAs(found);
          return;
        }
      }

      renderAuthGate();
    } catch (err) {
      console.error("Lỗi khởi tạo hồ sơ học sinh:", err);
      renderAuthGate();
    }
  }

  function renderAuthGate() {
    abortPendingRequests();
    clearActiveQuizState();

    state.currentStudentId = "";
    state.currentStudent = null;
    localStorage.removeItem("asas_student_id");

    userNavActions.classList.add("hidden");
    guestNavNotice.classList.remove("hidden");

    showView("auth");

    if (state.students && state.students.length > 0) {
      accountSelectBox.classList.remove("hidden");
      accountCreateBox.classList.add("hidden");
      btnCancelCreateAccount.classList.remove("hidden");

      studentAccountsList.innerHTML = "";
      state.students.forEach((st) => {
        const card = document.createElement("div");
        card.className = "student-card-item";
        const initial = st.name ? st.name.trim().charAt(0).toUpperCase() : "U";
        card.innerHTML = `
          <div class="card-avatar">${escapeHtml(initial)}</div>
          <div class="card-info">
            <div class="card-name">${escapeHtml(st.name)}</div>
            <div class="card-id">#${escapeHtml(st.student_id)}</div>
            ${st.grade_level ? `<div class="card-meta">🎓 ${escapeHtml(st.grade_level)}</div>` : ""}
          </div>
          <div class="card-action">➔</div>
        `;
        card.addEventListener("click", () => {
          loginAs(st);
        });
        studentAccountsList.appendChild(card);
      });
    } else {
      accountSelectBox.classList.add("hidden");
      accountCreateBox.classList.remove("hidden");
      createAccountTitle.textContent = "Chào mừng! Hãy tạo hồ sơ học sinh trên thiết bị này";
      btnCancelCreateAccount.classList.add("hidden");
    }
  }

  function loginAs(student) {
    // Khi đăng nhập tài khoản mới, hủy sạch toàn bộ request cũ còn sót lại
    abortPendingRequests();
    clearActiveQuizState();

    state.currentStudentId = student.student_id;
    state.currentStudent = student;
    localStorage.setItem("asas_student_id", student.student_id);

    guestNavNotice.classList.add("hidden");
    userNavActions.classList.remove("hidden");
    navStudentName.textContent = student.name;
    navStudentId.textContent = `#${student.student_id}`;

    showView("config");
  }

  function logout() {
    abortPendingRequests();
    clearActiveQuizState();
    renderAuthGate();
  }

  btnSwitchAccount.addEventListener("click", () => {
    logout();
  });

  btnShowCreateAccount.addEventListener("click", () => {
    accountSelectBox.classList.add("hidden");
    accountCreateBox.classList.remove("hidden");
    createAccountTitle.textContent = "Tạo thêm tài khoản mới trên máy này";
    btnCancelCreateAccount.classList.remove("hidden");
  });

  btnCancelCreateAccount.addEventListener("click", () => {
    accountCreateBox.classList.add("hidden");
    accountSelectBox.classList.remove("hidden");
  });

  authCreateForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const studentId = authStudentId.value.trim();
    const name = authStudentName.value.trim();
    const gradeLevel = authStudentGrade.value.trim();
    const school = authStudentSchool.value.trim();

    if (!studentId || !name) {
      alert("Vui lòng điền đầy đủ Tên và Mã ID học sinh.");
      return;
    }

    try {
      const response = await fetch("/api/v1/students", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          student_id: studentId,
          name: name,
          grade_level: gradeLevel || null,
          school: school || null,
          device_id: getDeviceId(),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Không thể tạo hồ sơ học sinh");
      }

      const created = await response.json();
      const existingIdx = state.students.findIndex((s) => s.student_id === created.student_id);
      if (existingIdx >= 0) {
        state.students[existingIdx] = created;
      } else {
        state.students.push(created);
      }

      authCreateForm.reset();
      loginAs(created);
    } catch (err) {
      alert(`Lỗi tạo hồ sơ: ${err.message}`);
    }
  });

  // ---------------------------------------------------------------------------
  // 4. Lịch sử bài thi Modal
  // ---------------------------------------------------------------------------
  btnOpenHistory.addEventListener("click", () => {
    openHistoryModal(state.currentStudentId);
  });

  btnViewHistoryFromResult.addEventListener("click", () => {
    openHistoryModal(state.currentStudentId);
  });

  btnCloseModal.addEventListener("click", () => {
    historyModal.classList.add("hidden");
  });

  window.addEventListener("click", (e) => {
    if (e.target === historyModal) historyModal.classList.add("hidden");
  });

  async function openHistoryModal(studentId) {
    if (!studentId) {
      alert("Vui lòng đăng nhập hồ sơ trước khi xem lịch sử.");
      return;
    }

    const summaryBox = document.getElementById("profileSummaryBox");
    const historyList = document.getElementById("historyList");
    summaryBox.innerHTML = "<p>Đang tải dữ liệu hồ sơ...</p>";
    historyList.innerHTML = "";
    historyModal.classList.remove("hidden");

    try {
      const res = await fetch(`/api/v1/students/${studentId}`);
      if (!res.ok) throw new Error("Không thể tải thông tin lịch sử học tập");
      const data = await res.json();

      const stats = data.quiz_stats || {};
      const totalQuizzes = stats.total_quizzes || 0;
      const avgScore = stats.average_score !== undefined ? stats.average_score : 0;
      const subjectsCount = stats.subjects_attempted ? stats.subjects_attempted.length : 0;

      summaryBox.innerHTML = `
        <div class="stat-box">
          <span class="stat-value">${totalQuizzes}</span>
          <span class="stat-label">Bài thi đã làm</span>
        </div>
        <div class="stat-box">
          <span class="stat-value">${avgScore}%</span>
          <span class="stat-label">Điểm trung bình</span>
        </div>
        <div class="stat-box">
          <span class="stat-value">${subjectsCount}</span>
          <span class="stat-label">Chủ đề đã ôn luyện</span>
        </div>
      `;

      const records = data.recent_quizzes || [];
      if (records.length === 0) {
        historyList.innerHTML = "<p class='empty-text'>Chưa có bài thi nào được ghi nhận cho học sinh này.</p>";
      } else {
        historyList.innerHTML = records
          .map((r) => {
            const dateStr = r.completed_at ? new Date(r.completed_at).toLocaleString("vi-VN") : "Gần đây";
            return `
              <div class="history-item">
                <div>
                  <strong>${escapeHtml(r.topic)}</strong>
                  <div class="history-time">${dateStr}</div>
                </div>
                <div class="history-score">${Math.round(r.score_percentage)}%</div>
              </div>
            `;
          })
          .join("");
      }
    } catch (err) {
      summaryBox.innerHTML = `<p style="color: var(--danger-accent);">Lỗi: ${err.message}</p>`;
    }
  }

  // ---------------------------------------------------------------------------
  // 5. Topic Chips
  // ---------------------------------------------------------------------------
  document.querySelectorAll(".chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      topicInput.value = btn.dataset.topic;
      topicInput.focus();
    });
  });

  // ---------------------------------------------------------------------------
  // 6. Quiz Generation Request (với AbortController & State Guards)
  // ---------------------------------------------------------------------------
  quizForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.currentStudentId) {
      alert("Vui lòng chọn hoặc tạo hồ sơ học sinh trước khi bắt đầu!");
      logout();
      return;
    }

    const topic = topicInput.value.trim();
    if (!topic) return;

    // 1. Hủy bỏ bất kỳ request tạo câu hỏi nào đang chạy ngầm trước đó
    if (state.quizGenerateAbortController) {
      state.quizGenerateAbortController.abort();
    }
    state.quizGenerateAbortController = new AbortController();

    // 2. Ghi nhận sequence requestId và snapshot ID học sinh yêu cầu
    const currentRequestId = ++state.activeQuizRequestId;
    const requestingStudentId = state.currentStudentId;

    // 3. Dọn sạch DOM và state của câu hỏi cũ ngay lập tức (Zero-delay cleanup)
    clearActiveQuizState();

    const numQuestions = parseInt(numQuestionsSelect.value, 10);
    const difficultyEl = document.querySelector('input[name="difficulty"]:checked');
    const difficulty = difficultyEl ? difficultyEl.value : "medium";

    if (btnGenerate) {
      btnGenerate.disabled = true;
      btnGenerate.querySelector(".spinner")?.classList.remove("hidden");
    }

    showView("loading");
    document.getElementById("loadingText").textContent = `Đang thiết kế đề thi: "${topic}"...`;
    document.getElementById("loadingSubText").textContent = "AI đang thiết kế câu hỏi đạt chuẩn sư phạm và dự phòng ngộ nhận lý thuyết...";

    try {
      const response = await fetch("/api/v1/quiz/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: state.quizGenerateAbortController.signal,
        body: JSON.stringify({
          topic: topic,
          num_questions: numQuestions,
          difficulty: difficulty,
          force_new: true,
          student_id: state.currentStudentId,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Lỗi máy chủ (${response.status})`);
      }

      const quizData = await response.json();

      // State Guard: Chỉ render khi request này đúng là request mới nhất và người dùng chưa đổi tài khoản
      if (currentRequestId !== state.activeQuizRequestId) {
        console.warn("Bỏ qua kết quả tạo quiz cũ do đã có yêu cầu mới hơn.");
        return;
      }
      if (state.currentStudentId !== requestingStudentId) {
        console.warn("Bỏ qua kết quả tạo quiz do người dùng đã chuyển tài khoản.");
        return;
      }

      state.currentQuiz = quizData;
      state.userAnswers = {};

      renderActiveQuiz(quizData);
      showView("quiz");
      startTimer();
    } catch (err) {
      if (err.name === "AbortError") {
        console.info("Yêu cầu tạo đề thi đã bị hủy bởi thao tác mới.");
        return;
      }
      if (currentRequestId === state.activeQuizRequestId) {
        alert(`Không thể tạo đề thi: ${err.message}`);
        showView("config");
      }
    } finally {
      if (currentRequestId === state.activeQuizRequestId && btnGenerate) {
        btnGenerate.disabled = false;
        btnGenerate.querySelector(".spinner")?.classList.add("hidden");
      }
    }
  });

  // ---------------------------------------------------------------------------
  // 7. Active Quiz View & Timer
  // ---------------------------------------------------------------------------
  function startTimer() {
    clearInterval(state.timerInterval);
    state.secondsElapsed = 0;
    quizTimerText.textContent = "00:00";

    state.timerInterval = setInterval(() => {
      state.secondsElapsed++;
      const mins = String(Math.floor(state.secondsElapsed / 60)).padStart(2, "0");
      const secs = String(state.secondsElapsed % 60).padStart(2, "0");
      quizTimerText.textContent = `${mins}:${secs}`;
    }, 1000);
  }

  function renderActiveQuiz(quiz) {
    quizTitle.textContent = quiz.title || quiz.topic;
    quizMeta.textContent = `Chủ đề: ${quiz.topic} | ${quiz.questions.length} câu hỏi`;

    if (quiz.source === "bank") {
      quizSourceBadge.textContent = "⚡ Kho CSDL (0 Token)";
      quizSourceBadge.className = "badge badge-success";
    } else {
      quizSourceBadge.textContent = "🤖 AI Sinh Mới";
      quizSourceBadge.className = "badge badge-purple";
    }

    questionsContainer.innerHTML = "";

    quiz.questions.forEach((q, idx) => {
      const card = document.createElement("div");
      card.className = "question-card fade-in";
      card.dataset.questionIndex = idx;

      const qText = q.question || q.stem || `Câu ${idx + 1}`;
      card.innerHTML = `
        <div class="question-header">
          <span class="question-num">Câu ${idx + 1}</span>
          <span class="question-diff">${escapeHtml(q.difficulty || "medium")}</span>
        </div>
        <p class="question-stem">${escapeHtml(qText)}</p>
        <div class="options-group">
          ${q.options
            .map(
              (opt) => `
            <div class="option-item" data-opt-id="${opt.id}">
              <div class="opt-indicator">${opt.id}</div>
              <div class="opt-text">${escapeHtml(cleanOptionText(opt.text, opt.id))}</div>
            </div>
          `
            )
            .join("")}
        </div>
      `;

      card.querySelectorAll(".option-item").forEach((optEl) => {
        optEl.addEventListener("click", () => {
          card.querySelectorAll(".option-item").forEach((item) => item.classList.remove("selected"));
          optEl.classList.add("selected");
          state.userAnswers[idx] = optEl.dataset.optId;
        });
      });

      questionsContainer.appendChild(card);
    });
  }

  btnCancelQuiz.addEventListener("click", () => {
    if (confirm("Bạn có chắc chắn muốn hủy bỏ bài thi đang làm?")) {
      abortPendingRequests();
      clearActiveQuizState();
      showView("config");
    }
  });

  // ---------------------------------------------------------------------------
  // 8. Chấm điểm & Đánh giá bài thi (với AbortController & State Guards)
  // ---------------------------------------------------------------------------
  btnSubmitQuiz.addEventListener("click", async () => {
    if (!state.currentQuiz) return;

    const totalQuestions = state.currentQuiz.questions.length;
    const answeredCount = Object.keys(state.userAnswers).length;

    if (answeredCount < totalQuestions) {
      const ok = confirm(`Bạn mới trả lời ${answeredCount}/${totalQuestions} câu. Bạn có muốn nộp bài luôn không?`);
      if (!ok) return;
    }

    clearInterval(state.timerInterval);

    // 1. Hủy bất kỳ request chấm điểm nào đang chạy trước đó
    if (state.quizGradeAbortController) {
      state.quizGradeAbortController.abort();
    }
    state.quizGradeAbortController = new AbortController();

    // 2. Ghi nhận sequence requestId và snapshot ID học sinh đang chấm
    const currentGradeRequestId = ++state.activeGradeRequestId;
    const gradingStudentId = state.currentStudentId;

    btnSubmitQuiz.disabled = true;
    btnSubmitQuiz.querySelector(".spinner").classList.remove("hidden");
    btnSubmitQuiz.querySelector(".btn-text").textContent = "Đang chấm điểm & đánh giá...";

    try {
      const response = await fetch("/api/v1/quiz/grade", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: state.quizGradeAbortController.signal,
        body: JSON.stringify({
          quiz: state.currentQuiz,
          user_answers: state.userAnswers,
          student_id: state.currentStudentId,
          evaluate_with_agent: true,
        }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Không thể chấm điểm bài thi");
      }

      const gradeResult = await response.json();

      // State Guard: Tuyệt đối không cho phép kết quả của tài khoản cũ hiển thị nếu người dùng đã chuyển tài khoản
      if (currentGradeRequestId !== state.activeGradeRequestId) {
        console.warn("Bỏ qua kết quả đánh giá cũ do đã có yêu cầu chấm điểm mới hơn.");
        return;
      }
      if (state.currentStudentId !== gradingStudentId) {
        console.warn("Bỏ qua kết quả đánh giá do tài khoản học sinh đã thay đổi.");
        return;
      }

      renderResults(gradeResult);
      showView("result");
    } catch (err) {
      if (err.name === "AbortError") {
        console.info("Yêu cầu chấm điểm đã bị hủy do chuyển tài khoản/hủy bài.");
        return;
      }
      if (currentGradeRequestId === state.activeGradeRequestId) {
        alert(`Lỗi nộp bài: ${err.message}`);
      }
    } finally {
      if (currentGradeRequestId === state.activeGradeRequestId) {
        btnSubmitQuiz.disabled = false;
        btnSubmitQuiz.querySelector(".spinner").classList.add("hidden");
        btnSubmitQuiz.querySelector(".btn-text").textContent = "📤 Nộp bài & Xem đánh giá";
      }
    }
  });

  // ---------------------------------------------------------------------------
  // 9. Hiển thị Kết quả & Nhận xét AI Sư phạm
  // ---------------------------------------------------------------------------
  function renderResults(res) {
    const pct = Math.round(res.score_percentage);
    scorePercentage.textContent = `${pct}%`;
    scoreRatio.textContent = `${res.correct_count}/${res.total_questions} đúng`;

    scoreCircle.style.background = `conic-gradient(var(--primary-600) ${pct}%, var(--primary-100) ${pct}%)`;

    const dur = res.duration_ms ? `${Math.round(res.duration_ms)}ms` : "0ms";
    const tok = res.total_tokens !== undefined && res.total_tokens !== null ? res.total_tokens : 0;
    telemetryBadge.textContent = `⏱️ ${dur} | 🪙 ${tok} Tokens`;

    if (res.source === "bank") {
      resultSourceBadge.textContent = "⚡ Nguồn: Kho CSDL (0 Token)";
      resultSourceBadge.className = "badge badge-success";
    } else {
      resultSourceBadge.textContent = "🤖 Nguồn: AI Đánh giá";
      resultSourceBadge.className = "badge badge-purple";
    }

    const evalRes = res.evaluation;
    if (evalRes) {
      document.getElementById("evaluatorContainer").classList.remove("hidden");

      if (evalRes.strengths && evalRes.strengths.length > 0) {
        strengthsBox.classList.remove("hidden");
        strengthsList.innerHTML = evalRes.strengths.map((s) => `<li>${escapeHtml(s)}</li>`).join("");
      } else {
        strengthsBox.classList.add("hidden");
      }

      if (evalRes.knowledge_gaps && evalRes.knowledge_gaps.length > 0) {
        gapsBox.classList.remove("hidden");
        gapsList.innerHTML = evalRes.knowledge_gaps.map((g) => `<li>${escapeHtml(g)}</li>`).join("");
      } else {
        gapsBox.classList.add("hidden");
      }

      critiqueText.textContent = evalRes.critique || "Bạn đã hoàn thành tốt bài kiểm tra.";

      if (evalRes.recommendations && evalRes.recommendations.length > 0) {
        recommendationsBox.classList.remove("hidden");
        recommendationsList.innerHTML = evalRes.recommendations.map((r) => `<li>${escapeHtml(r)}</li>`).join("");
      } else {
        recommendationsBox.classList.add("hidden");
      }

      if (evalRes.improvement_plan) {
        planBox.classList.remove("hidden");
        planText.textContent = evalRes.improvement_plan;
      } else {
        planBox.classList.add("hidden");
      }
    } else {
      document.getElementById("evaluatorContainer").classList.add("hidden");
    }

    reviewQuestionsContainer.innerHTML = "";
    (res.details || []).forEach((d, idx) => {
      const card = document.createElement("div");
      card.className = "review-card";
      const isCorrect = d.is_correct;

      let misconceptionHtml = "";
      if (!isCorrect && d.misconception) {
        misconceptionHtml = `
          <div class="misconception-callout">
            <span class="callout-icon">💡</span>
            <div>
              <strong>Ngộ nhận kiến thức phát hiện:</strong>
              <p>${escapeHtml(d.misconception)}</p>
            </div>
          </div>
        `;
      }

      const qText = d.question || d.stem || `Câu ${idx + 1}`;

      card.innerHTML = `
        <div class="review-stem">Câu ${idx + 1}: ${escapeHtml(qText)}</div>
        <div class="review-answer-grid">
          <div class="answer-row">
            <span class="answer-label">Bạn đã chọn:</span>
            <span class="answer-val" style="color: ${isCorrect ? "var(--success-accent)" : "var(--danger-accent)"}">
              ${escapeHtml(d.user_answer || "(Chưa trả lời)")}
            </span>
          </div>
          <div class="answer-row">
            <span class="answer-label">Đáp án đúng:</span>
            <span class="answer-val" style="color: var(--success-accent); font-weight: 700;">
              ${escapeHtml(d.correct_answer || "")}
            </span>
          </div>
          ${d.explanation ? `
          <div class="answer-row" style="margin-top: 4px;">
            <span class="answer-label">Giải thích:</span>
            <span class="answer-val" style="color: var(--text-muted); font-weight: 400;">
              ${escapeHtml(d.explanation)}
            </span>
          </div>` : ""}
        </div>
        ${misconceptionHtml}
      `;
      reviewQuestionsContainer.appendChild(card);
    });
  }

  btnRetake.addEventListener("click", () => {
    abortPendingRequests();
    clearActiveQuizState();
    reviewQuestionsContainer.innerHTML = "";
    showView("config");
  });

  // Hủy tất cả các request đang chạy ngầm khi người dùng F5 hoặc đóng tab
  window.addEventListener("beforeunload", () => {
    abortPendingRequests();
  });

  // ---------------------------------------------------------------------------
  // 10. Utility Functions
  // ---------------------------------------------------------------------------
  function cleanOptionText(text, optId) {
    if (!text) return "";
    let cleaned = text.trim();
    cleaned = cleaned.replace(/^\s*\[?[A-Fa-f0-9]\]?[\.\:\)\-\–\s]+\s*/, "");
    if (optId && cleaned.startsWith(optId) && cleaned.length > 1) {
      const secondChar = cleaned.charAt(1);
      if (secondChar === secondChar.toUpperCase() && secondChar !== secondChar.toLowerCase()) {
        cleaned = cleaned.substring(1).trim();
      }
    }
    return cleaned || text.trim();
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Khởi động ứng dụng
  loadStudentsAndInit();
});
