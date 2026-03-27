/* ============================================================
   Examiner Dashboard – Client-side Logic
   ============================================================ */

let _currentSessionId = null;

function loadStudentAnswers(sessionId) {
    _currentSessionId = sessionId;

    fetch('/examiner/get_student_answers/' + sessionId)
    .then(res => res.json())
    .then(data => {

        let div = document.getElementById("answerArea");

        if (data.error) {
            div.innerHTML = `
                <div class="section-title">Answer Review and Grading</div>
                <div class="empty-state">
                    <div class="icon">[!]</div>
                    <p>${data.error}</p>
                </div>`;
            return;
        }

        if (data.length === 0) {
            div.innerHTML = `
                <div class="section-title">Answer Review and Grading</div>
                <div class="empty-state">
                    <div class="icon">[ ]</div>
                    <p>No answers submitted for this session yet.</p>
                </div>`;
            return;
        }

        let html = `<div class="section-title">Answer Review and Grading | Session #${sessionId}</div>`;

        // Grade All with AI button
        html += `
            <div style="margin-bottom: 16px; display: flex; gap: 10px; flex-wrap: wrap;">
                <button class="btn btn-ai" onclick="aiGradeAll(${sessionId})">
                    Grade All with AI
                </button>
                <button class="btn btn-success" onclick="viewStudentResult(${sessionId})">
                    View Total Result
                </button>
            </div>`;

        data.forEach((a, idx) => {
            let tamperedClass = a.tampered ? 'tampered' : '';
            let tamperedBadge = a.tampered
                ? '<span class="badge badge-tampered">[!] Tampered</span>'
                : '';

            let methodBadge = '';
            if (a.grading_method === 'MANUAL') {
                methodBadge = '<span class="badge badge-manual">Manual</span>';
            } else if (a.grading_method === 'AI') {
                methodBadge = '<span class="badge badge-ai">AI Graded</span>';
            }

            let currentMarks = a.marks !== null && a.marks !== undefined ? a.marks : '';

            html += `
            <div class="answer-card ${tamperedClass}">
                <div class="question-text">
                    Q${idx + 1}. ${escapeHtml(a.question)}
                    ${tamperedBadge}
                </div>

                <div class="answer-text" style="border-left: 3px solid #cbd5e1;">
                    <strong>Answer Key:</strong><br>
                    ${escapeHtml(a.model_answer || "Not provided")}
                </div>

                <div class="answer-text">
                    ${escapeHtml(a.answer)}
                </div>

                <div class="grading-row">
                    <label>Marks (0-10):</label>
                    <input type="number" id="grade_${a.answer_id}"
                           value="${currentMarks}" min="0" max="10"
                           placeholder="--">

                    <button class="btn"
                            onclick="saveGrade(${a.answer_id})">
                        Save
                    </button>

                    <button class="btn btn-ai"
                            onclick="aiGrade(${a.answer_id})">
                        Grade with AI
                    </button>

                    ${methodBadge}
                </div>
            </div>`;
        });

        // Result box (hidden until requested)
        html += `<div class="result-box" id="resultBox"></div>`;

        div.innerHTML = html;

        // Smooth scroll to answers
        div.scrollIntoView({ behavior: 'smooth', block: 'start' });
    })
    .catch(err => {
        console.error('Error loading answers:', err);
        alert('Failed to load answers. Please try again.');
    });
}


function saveGrade(answerId) {
    let marksInput = document.getElementById("grade_" + answerId);
    let marks = marksInput.value;

    if (marks === '' || isNaN(marks)) {
        alert('Please enter a valid marks value.');
        return;
    }

    let form = new FormData();
    form.append("answer_id", answerId);
    form.append("marks", marks);

    fetch('/examiner/save_grade', {
        method: "POST",
        body: form
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            alert('Error: ' + data.error);
            return;
        }
        // Visual feedback
        marksInput.style.borderColor = '#16a34a';
        marksInput.style.background = '#f0fdf4';
        setTimeout(() => {
            marksInput.style.borderColor = '#cbd5e1';
            marksInput.style.background = '';
        }, 1500);
    })
    .catch(err => {
        console.error('Error saving grade:', err);
        alert('Failed to save marks. Please try again.');
    });
}


function aiGrade(answerId) {
    let form = new FormData();
    form.append("answer_id", answerId);

    // Show loading state
    let marksInput = document.getElementById("grade_" + answerId);
    marksInput.style.background = '#fef3c7';
    marksInput.placeholder = '...';

    fetch('/examiner/ai_grade', {
        method: "POST",
        body: form
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            alert('Error: ' + data.error);
            marksInput.style.background = '';
            return;
        }

        marksInput.value = data.marks;
        marksInput.style.background = '#fef3c7';
        marksInput.style.borderColor = '#f59e0b';

        setTimeout(() => {
            marksInput.style.background = '';
            marksInput.style.borderColor = '#cbd5e1';
        }, 2000);
    })
    .catch(err => {
        console.error('Error during AI grading:', err);
        alert('AI grading failed. Please try again.');
        marksInput.style.background = '';
    });
}


function aiGradeAll(sessionId) {
    fetch('/examiner/get_student_answers/' + sessionId)
    .then(res => res.json())
    .then(data => {
        if (data.error || data.length === 0) return;

        let promises = data.map(a => {
            let form = new FormData();
            form.append("answer_id", a.answer_id);
            return fetch('/examiner/ai_grade', {
                method: "POST",
                body: form
            }).then(r => r.json());
        });

        Promise.all(promises).then(results => {
            // Reload answers to show updated marks
            loadStudentAnswers(sessionId);
        });
    });
}


function viewStudentResult(sessionId) {
    fetch('/examiner/get_result/' + sessionId)
    .then(res => res.json())
    .then(data => {
        let box = document.getElementById("resultBox");
        if (box) {
            box.textContent = 'Total Marks: ' + data.total_marks;
            box.style.display = 'block';
            box.scrollIntoView({ behavior: 'smooth' });
        } else {
            alert('Total Marks: ' + data.total_marks);
        }
    })
    .catch(err => {
        console.error('Error fetching result:', err);
        alert('Failed to fetch result.');
    });
}


/* ---------- Utility ---------- */

function escapeHtml(text) {
    if (!text) return '';
    let div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
