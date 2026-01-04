// Questions for the exam
const questions = [
    "What is the capital of India?",
    "Name the largest planet in our solar system.",
    "Who wrote Romeo and Juliet?"
];

let currentQuestionIndex = -1;
let answers = [];

// Speech Recognition setup
const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

if (!SpeechRecognition) {
    alert("Speech Recognition is not supported in this browser.");
}

const recognition = new SpeechRecognition();
recognition.continuous = true;
recognition.lang = "en-US";

// Text-to-Speech
function speak(text) {
    const msg = new SpeechSynthesisUtterance(text);
    window.speechSynthesis.speak(msg);
}

// Start exam
function startExam() {
    speak("The exam has started. You may speak now.");
    recognition.start();
}

// Listen to speech
recognition.onresult = function (event) {
    const lastResult = event.results[event.results.length - 1];
    const transcript = lastResult[0].transcript.toLowerCase().trim();

    console.log("You said:", transcript);
    handleCommand(transcript);
};

// Handle voice commands
function handleCommand(command) {

    if (command.includes("next question")) {
        currentQuestionIndex++;

        if (currentQuestionIndex < questions.length) {
            speak(
                "Question " +
                (currentQuestionIndex + 1) +
                ". " +
                questions[currentQuestionIndex]
            );
        } else {
            speak("You have reached the end of the exam. Say submit exam to finish.");
        }
    }

    else if (command.includes("repeat question")) {
        if (currentQuestionIndex >= 0) {
            speak(questions[currentQuestionIndex]);
        } else {
            speak("No question has been asked yet.");
        }
    }

    else if (command.includes("submit exam")) {
        speak("Your exam has been submitted. Thank you.");
        recognition.stop();
        console.log("Answers:", answers);
    }

    else if (currentQuestionIndex >= 0) {
        answers[currentQuestionIndex] = command;
        speak("Answer recorded. Say next question to proceed.");
    }
}