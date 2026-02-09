function loadQuestions(exam_id) {

    fetch('/invigilator/get_questions/' + exam_id)
    .then(res => res.json())
    .then(data => {

        let div = document.getElementById("questionArea");

        div.innerHTML = "<h3>Manage Questions</h3>";

        data.forEach(q => {

            div.innerHTML += `
            <div class="item">
            <input id='q${q.id}' value='${q.text}' size='60'>

            <button class="btn" onclick='updateQuestion(${q.id})'>Update</button>

            <button class="btn danger" onclick='deleteQuestion(${q.id})'>Delete</button>
            </div>
            `;
        });

        div.innerHTML += `
        <br>
        <input id='newq' placeholder='New Question' size='60'>
        <button class="btn" onclick='addQuestion(${exam_id})'>Add Question</button>
        `;
    });
}

function addQuestion(exam_id) {

    let text = document.getElementById("newq").value;

    let form = new FormData();
    form.append("exam_id", exam_id);
    form.append("text", text);

    fetch('/invigilator/add_question', {
        method: "POST",
        body: form
    }).then(() => loadQuestions(exam_id));
}

function updateQuestion(qid) {

    let text = document.getElementById("q"+qid).value;

    let form = new FormData();
    form.append("qid", qid);
    form.append("text", text);

    fetch('/invigilator/update_question', {
        method: "POST",
        body: form
    }).then(() => alert("Updated Successfully"));
}

function deleteQuestion(qid) {

    fetch('/invigilator/delete_question/' + qid)
    .then(() => location.reload());
}

function viewAnswers(session_id) {

    fetch('/invigilator/get_answers/' + session_id)
    .then(res => res.json())
    .then(data => {

        let div = document.getElementById("answerArea");

        div.innerHTML = "<h3>Evaluate Answers</h3>";

        data.forEach(a => {

            div.innerHTML += `
            <div class="item">

            <b>${a.question}</b><br><br>

            ${a.answer}<br><br>

            Marks:
            <input id='m${a.answer_id}' value='${a.marks || 0}' size='5'>

            <button class="btn" onclick='saveMarks(${a.answer_id})'>
            Save Marks
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

    let marks = document.getElementById("m"+answer_id).value;

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
