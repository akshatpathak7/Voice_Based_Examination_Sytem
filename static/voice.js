let questions = [];
let currentQuestionIndex = -1;

let answerBuffer = "";
let listeningForAnswer = false;
let examOver = false;

// Load questions from database
function loadQuestions() {
    fetch('/api/questions')
        .then(response => response.json())
        .then(data => {
            questions = data;
        });
}

function startExam() {

    speak("Welcome to the examination system.");

    speak("Instructions:");

    speak("Say NEXT to go to next question.");

    speak("Say REPEAT to hear the question again.");

    speak("After speaking your answer, say SUBMIT ANSWER.");

    speak("After all questions, say SUBMIT EXAM.");

    fetch('/api/start_exam')
        .then(response => response.json())
        .then(data => {

            if (data.error) {
                speak("Unable to start exam session.");
                return;
            }

            loadQuestions();

            setTimeout(() => {
                nextQuestion();
                recognition.start();
            }, 4000);
        });
}


function nextQuestion() {

    currentQuestionIndex++;
    answerBuffer = "";
    listeningForAnswer = true;

    if (currentQuestionIndex < questions.length) {
        speak("Question " +
            (currentQuestionIndex + 1) +
            ". " +
            questions[currentQuestionIndex].text);
    } else {
        speak("All questions answered. Say submit exam.");
    }
}

// Speech Recognition Setup
const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

const recognition = new SpeechRecognition();

recognition.continuous = true;
recognition.interimResults = false;
recognition.lang = "en-US";

function speak(text) {
    const msg = new SpeechSynthesisUtterance(text);
    window.speechSynthesis.speak(msg);
}

recognition.onresult = function (event) {

    if (examOver) return;

    let transcript =
        event.results[event.results.length - 1][0].transcript
        .toLowerCase()
        .trim();

    handleInput(transcript);
};

recognition.onend = function () {
    if (!examOver) {
        recognition.start();
    }
};

function handleInput(text) {

    // ----- COMMAND DETECTION -----

    if (text.includes("next")) {
        listeningForAnswer = true;
        answerBuffer = "";
        nextQuestion();
        return;
    }

    if (text.includes("repeat")) {
        speak(questions[currentQuestionIndex].text);
        return;
    }

    if (text.includes("submit exam")) {
        finishExam();
        return;
    }

    if (text.includes("submit answer")) {
        finalizeAnswer();
        return;
    }

    // ----- OTHERWISE TREAT AS ANSWER -----

    if (listeningForAnswer) {
        answerBuffer += " " + text;
        speak("Answer noted. Say submit answer when finished.");
    }
}

function finalizeAnswer() {

    if (!listeningForAnswer || answerBuffer.trim() === "") {
        speak("No answer detected.");
        return;
    }

    let qid = questions[currentQuestionIndex].id;

    fetch('/api/save_answer', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            question_id: qid,
            answer: answerBuffer
        })
    })
    .then(response => response.json())
    .then(data => {
        speak("Answer saved successfully.");
    });

    listeningForAnswer = false;
    answerBuffer = "";

    if (currentQuestionIndex + 1 < questions.length) {
        speak("Say next to continue.");
    } else {
        speak("All questions answered. Say submit exam.");
    }
}

function finishExam() {

    examOver = true;

    recognition.stop();

    speak("Exam submitted successfully. Thank you.");

}
