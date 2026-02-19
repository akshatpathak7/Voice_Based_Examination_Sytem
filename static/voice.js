let questions = [];
let currentQuestionIndex = -1;

let answerBuffer = "";
let listeningForAnswer = false;
let examOver = false;

let ui = null;
const voiceLog = (msg, data) => {
    try {
        console.log("[voice]", msg, data || "");
    } catch (e) {
        // ignore
    }
};

function ensureUiRefs() {
    if (ui) return ui;
    ui = {
        questionNumber: document.getElementById("questionNumber"),
        questionText: document.getElementById("questionText"),
        answerText: document.getElementById("answerText"),
        listeningStatus: document.getElementById("listeningStatus"),
        examStatus: document.getElementById("examStatus"),
        startExamButton: document.getElementById("startExamButton"),
    };
    return ui;
}

// Load questions from database
function loadQuestions() {
    ensureUiRefs();
    fetch('/api/questions')
        .then(response => response.json())
        .then(data => {
            questions = data;
            if (!questions.length && ui.examStatus) {
                ui.examStatus.textContent = "No questions available for this exam.";
            }
        });
}

function startExam() {

    ensureUiRefs();

    if (!recognitionAvailable) {
        if (ui.examStatus) {
            ui.examStatus.textContent =
                "Speech recognition is not available in this browser. Please switch to Chrome on desktop.";
        }
        speak("Speech recognition is not available in this browser.");
        return;
    }

    if (ui.startExamButton) {
        ui.startExamButton.disabled = true;
    }

    speak("Welcome to the physics voice examination system.");
    speak("Instructions:");
    speak("Say NEXT to go to next question.");
    speak("Say REPEAT to hear the question again.");
    speak("After speaking your answer, say SUBMIT ANSWER.");
    speak("After all questions, say SUBMIT EXAM.");

    if (ui.examStatus) {
        ui.examStatus.textContent = "Starting exam… loading questions and initializing microphone.";
    }

    fetch('/api/start_exam')
        .then(response => response.json())
        .then(data => {

            if (data.error) {
                speak("Unable to start exam session.");
                if (ui.examStatus) {
                    ui.examStatus.textContent = "Unable to start exam session.";
                }
                return;
            }

            loadQuestions();

            setTimeout(() => {
                nextQuestion();
                try {
                    recognition.start();
                } catch (e) {
                    console.error("Failed to start recognition:", e);
                    if (ui.examStatus) {
                        ui.examStatus.textContent =
                            "Microphone access failed. Please check browser permissions and try again.";
                    }
                    speak("Microphone access failed. Please check browser permissions and try again.");
                    return;
                }
                if (ui.examStatus) {
                    ui.examStatus.textContent = "Exam in progress. Speak your answer after each question.";
                }
                if (ui.listeningStatus) {
                    ui.listeningStatus.style.display = "inline-block";
                }
            }, 4000);
        });
}


function nextQuestion() {

    ensureUiRefs();

    currentQuestionIndex++;
    answerBuffer = "";
    listeningForAnswer = true;

    if (ui.answerText) {
        ui.answerText.textContent = "";
    }

    if (currentQuestionIndex < questions.length) {
        const numberLabel = "Question " + (currentQuestionIndex + 1) + " of " + questions.length;
        if (ui.questionNumber) {
            ui.questionNumber.textContent = numberLabel;
        }
        if (ui.questionText) {
            ui.questionText.textContent = questions[currentQuestionIndex].text;
        }

        speak("Question " +
            (currentQuestionIndex + 1) +
            ". " +
            questions[currentQuestionIndex].text);
    } else {
        speak("All questions answered. Say submit exam.");
        if (ui.examStatus) {
            ui.examStatus.textContent = "All questions answered. Say “submit exam” to finish.";
        }
    }
}

// Speech Recognition Setup
const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

let recognition = null;
let recognitionAvailable = !!SpeechRecognition;

if (recognitionAvailable) {
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "en-US";
} else {
    // Graceful fallback if browser does not support Web Speech API
    ensureUiRefs();
    if (ui && ui.examStatus) {
        ui.examStatus.textContent =
            "Your browser does not support speech recognition. Please use the latest version of Chrome on desktop.";
    }
}

function speak(text) {
    const msg = new SpeechSynthesisUtterance(text);
    window.speechSynthesis.speak(msg);
}

if (recognitionAvailable) {
    recognition.onresult = function (event) {

        if (examOver) return;

        let transcript =
            event.results[event.results.length - 1][0].transcript
                .toLowerCase()
                .trim();

        voiceLog("onresult transcript", transcript);
        handleInput(transcript);
    };

    recognition.onend = function () {
        if (!examOver) {
            try {
                recognition.start();
            } catch (e) {
                console.error("Failed to restart recognition:", e);
            }
        }
    };
}

function handleInput(text) {

    ensureUiRefs();

    const commandText = text.toLowerCase();
    voiceLog("handleInput received", commandText);

    // ----- COMMAND DETECTION (more robust) -----

    // Submit exam: variations like "submit exam", "submit my exam", "finish exam"
    if (/\bsubmit\b.*\bexam\b/.test(commandText) || /\bfinish\b.*\bexam\b/.test(commandText)) {
        voiceLog("command", "submit exam");
        finishExam();
        return;
    }

    // Submit answer: "submit answer", "submit my answer", "submit the answer"
    if (/\bsubmit\b.*\banswer\b/.test(commandText)) {
        voiceLog("command", "submit answer");
        finalizeAnswer();
        return;
    }

    // Next question: "next", "next question"
    if (/\bnext(\s+question)?\b/.test(commandText)) {
        voiceLog("command", "next");
        listeningForAnswer = true;
        answerBuffer = "";
        nextQuestion();
        return;
    }

    // Repeat question: "repeat", "repeat the question"
    if (/\brepeat(\s+the)?\s+question?\b/.test(commandText) || /\brepeat\b/.test(commandText)) {
        voiceLog("command", "repeat");
        speak(questions[currentQuestionIndex].text);
        return;
    }

    // ----- OTHERWISE TREAT AS ANSWER -----

    if (listeningForAnswer) {
        answerBuffer += " " + text;
        if (ui.answerText) {
            ui.answerText.textContent = answerBuffer.trim();
        }
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
        voiceLog("save_answer response", data);
        speak("Answer saved successfully.");
        if (data && data.normalized_answer && ui.answerText) {
            // Show the normalized version once the server has processed it
            ui.answerText.textContent = data.normalized_answer;
        }
        if (ui.examStatus) {
            ui.examStatus.textContent =
                "Answer saved. Say “next” for the next question or “submit exam” to finish.";
        }
    });

    listeningForAnswer = false;
    answerBuffer = "";
    if (ui.answerText) {
        ui.answerText.textContent = "";
    }

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

    ensureUiRefs();
    if (ui.listeningStatus) {
        ui.listeningStatus.style.display = "none";
    }
    if (ui.examStatus) {
        ui.examStatus.textContent = "Exam submitted successfully.";
    }

}
