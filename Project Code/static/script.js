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
                div.innerHTML +=
                    "<div class='item flex'>" +
                    "<input id='q" + q.id + "' value=\"" + safeText + "\" style='flex:1; min-width:220px;'>" +
                    "<button class='btn' onclick='updateQuestion(" + q.id + ")'>Update</button>" +
                    "<button class='btn btn-danger' onclick='deleteQuestion(" + q.id + ")'>Delete</button>" +
                    "</div>";
            });
            div.innerHTML +=
                "<div class='item flex'>" +
                "<input id='newq' placeholder='New question' style='flex:1; min-width:220px;'>" +
                "<button class='btn' onclick='addQuestion(" + exam_id + ")'>Add Question</button>" +
                "</div>";
        })
        .catch(function (err) {
            let div = document.getElementById("questionArea");
            div.innerHTML = "<div class='section-title'>Question Management</div><p class='error'>" + escapeAttr(err.message) + "</p>";
        });
}

function addQuestion(exam_id) {
    var text = document.getElementById("newq").value;
    if (!text || !text.trim()) {
        alert("Please enter question text.");
        return;
    }
    var form = new FormData();
    form.append("exam_id", exam_id);
    form.append("text", text.trim());
    fetch('/invigilator/add_question', { method: "POST", body: form, credentials: 'same-origin' })
        .then(function (res) {
            if (!res.ok) throw new Error("Failed to add question.");
            return res.json();
        })
        .then(function () {
            document.getElementById("newq").value = "";
            loadQuestions(exam_id);
        })
        .catch(function () { alert("Failed to add question. Try again."); });
}

function updateQuestion(qid) {
    var text = document.getElementById("q" + qid).value;
    var form = new FormData();
    form.append("qid", qid);
    form.append("text", text);
    fetch('/invigilator/update_question', { method: "POST", body: form, credentials: 'same-origin' })
        .then(function (res) {
            if (!res.ok) throw new Error("Failed to update.");
            return res.json();
        })
        .then(function () { alert("Updated successfully."); })
        .catch(function () { alert("Failed to update question. Try again."); });
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

            ${a.answer}<br><br>

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
