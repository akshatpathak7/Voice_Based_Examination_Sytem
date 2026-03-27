// Keep current exam id so delete can refresh the list
let _currentExamId = null;

function escapeAttr(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function loadQuestions(exam_id) {
    _currentExamId = exam_id;
    fetch('/invigilator/get_questions/' + exam_id, { credentials: 'same-origin' })
        .then(function (res) {
            if (!res.ok) {
                throw new Error(res.status === 401 ? 'Session expired. Please log in again.' : 'Failed to load questions.');
            }
            return res.json();
        })
        .then(function (data) {
            let div = document.getElementById("questionArea");
            if (!Array.isArray(data)) {
                div.innerHTML = "<div class='section-title'>Question Management</div><p class='error'>Unexpected response. Please try again.</p>";
                return;
            }
            div.innerHTML = "<div class='section-title'>Question Management</div>";
            data.forEach(function (q) {
                var safeText = escapeAttr(q.text);
                var safeAnswer = escapeHtml(q.model_answer || "");
                div.innerHTML +=
                    "<div class='answer-card'>" +
                    "<div style='display:flex; gap:8px; align-items:center; margin-bottom:8px;'>" +
                    "<strong>Question #" + q.id + "</strong>" +
                    "</div>" +
                    "<input id='q" + q.id + "' value=\"" + safeText + "\" placeholder='Question text' style='width:100%; margin-bottom:8px;'>" +
                    "<textarea id='qa" + q.id + "' placeholder='Answer key / model answer' style='width:100%; min-height:70px;'>" + safeAnswer + "</textarea>" +
                    "<div style='display:flex; gap:8px; margin-top:10px;'>" +
                    "<button class='btn' onclick='updateQuestion(" + q.id + ")'>Update</button>" +
                    "<button class='btn btn-danger' onclick='deleteQuestion(" + q.id + ")'>Delete</button>" +
                    "</div>" +
                    "</div>";
            });
            div.innerHTML +=
                "<div class='answer-card'>" +
                "<strong>Add Question</strong>" +
                "<input id='newq' placeholder='New question' style='width:100%; margin-top:8px; margin-bottom:8px;'>" +
                "<textarea id='newqa' placeholder='Answer key / model answer' style='width:100%; min-height:80px;'></textarea>" +
                "<div style='margin-top:10px;'>" +
                "<button class='btn' onclick='addQuestion(" + exam_id + ")'>Add Question</button>" +
                "</div>" +
                "</div>";
        })
        .catch(function (err) {
            let div = document.getElementById("questionArea");
            div.innerHTML = "<div class='section-title'>Question Management</div><p class='error'>" + escapeAttr(err.message) + "</p>";
        });
}

function addQuestion(exam_id) {
    var text = document.getElementById("newq").value;
    var modelAnswer = document.getElementById("newqa").value;
    if (!text || !text.trim()) {
        alert("Please enter question text.");
        return;
    }
    if (!modelAnswer || !modelAnswer.trim()) {
        alert("Please enter the answer key.");
        return;
    }
    var form = new FormData();
    form.append("exam_id", exam_id);
    form.append("text", text.trim());
    form.append("model_answer", modelAnswer.trim());
    fetch('/invigilator/add_question', { method: "POST", body: form, credentials: 'same-origin' })
        .then(function (res) {
            return res.json().then(function (body) {
                if (!res.ok) throw new Error(body.error || "Failed to add question.");
                return body;
            });
        })
        .then(function () {
            document.getElementById("newq").value = "";
            document.getElementById("newqa").value = "";
            loadQuestions(exam_id);
        })
        .catch(function (err) { alert(err.message || "Failed to add question. Try again."); });
}

function updateQuestion(qid) {
    var text = document.getElementById("q" + qid).value;
    var modelAnswer = document.getElementById("qa" + qid).value;
    if (!text || !text.trim() || !modelAnswer || !modelAnswer.trim()) {
        alert("Both question and answer key are required.");
        return;
    }
    var form = new FormData();
    form.append("qid", qid);
    form.append("text", text.trim());
    form.append("model_answer", modelAnswer.trim());
    fetch('/invigilator/update_question', { method: "POST", body: form, credentials: 'same-origin' })
        .then(function (res) {
            return res.json().then(function (body) {
                if (!res.ok) throw new Error(body.error || "Failed to update.");
                return body;
            });
        })
        .then(function () { alert("Updated successfully."); })
        .catch(function (err) { alert(err.message || "Failed to update question. Try again."); });
}

function deleteQuestion(qid) {
    if (!confirm("Delete this question?")) return;
    fetch('/invigilator/delete_question/' + qid, { method: "POST", credentials: 'same-origin' })
        .then(function (res) {
            if (!res.ok) throw new Error("Failed to delete.");
            if (_currentExamId != null) loadQuestions(_currentExamId);
            else location.reload();
        })
        .catch(function () {
            alert("Failed to delete question. Try again.");
        });
}

function viewAnswers(session_id) {

    fetch('/invigilator/get_answers/' + session_id)
        .then(res => res.json())
        .then(data => {

            let div = document.getElementById("answerArea");

            div.innerHTML = "<div class='section-title'>Answer Evaluation</div>";

            if (!Array.isArray(data) || data.length === 0) {
                div.innerHTML += "<div class='empty-state'>No answers submitted for this session yet.</div>";
                return;
            }

            data.forEach(a => {

                div.innerHTML += `
            <div class="item">

            <b>${a.question}</b><br><br>
            <div style="color:#334155; margin-bottom:8px;"><strong>Answer Key:</strong> ${escapeHtml(a.model_answer || 'Not provided')}</div>

            ${escapeHtml(a.answer)}<br><br>

            Marks:
            <input id='m${a.answer_id}' value='${a.marks || 0}' size='5'>

            <button class="btn" onclick='saveMarks(${a.answer_id})'>
            Save
            </button>

            </div>
            `;
            });

            div.innerHTML += `
        <button class="btn" onclick='viewResult(${session_id})'>
        View Total Result
        </button>
        `;
        });
}

function saveMarks(answer_id) {

    let marks = document.getElementById("m" + answer_id).value;

    let form = new FormData();
    form.append("answer_id", answer_id);
    form.append("marks", marks);

    fetch('/invigilator/save_marks', {
        method: "POST",
        body: form
    }).then(() => alert("Marks Saved"));
}

function viewResult(session_id) {

    fetch('/invigilator/get_result/' + session_id)
        .then(res => res.json())
        .then(data => {

            alert("Total Marks: " + data.total_marks);

        });
}
