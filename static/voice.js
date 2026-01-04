const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (!SpeechRecognition) {
    alert("Speech Recognition is not supported in this browser.");
}

const recognition = new SpeechRecognition();

recognition.continuous = true;
recognition.lang = "en-US";

function speak(text) {
    const msg = new SpeechSynthesisUtterance(text);
    window.speechSynthesis.speak(msg);
}

function startExam() {
    speak("The exam has started. You may speak now.");
    recognition.start();
}

recognition.onresult = function(event) {
    const lastResult = event.results[event.results.length - 1];
    const transcript = lastResult[0].transcript.toLowerCase().trim();

    console.log("You said: ", transcript);

};