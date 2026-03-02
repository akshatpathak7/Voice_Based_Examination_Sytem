// ============================================================
//  Voice Examination Module
//  Locale: en-IN | Fuzzy commands | Live transcription
// ============================================================

(function () {
  "use strict";

  // ----- State -----
  const state = {
    questions: [
      "What is the capital of India?",
      "Name the largest planet in our solar system.",
      "Who wrote Romeo and Juliet?",
    ],
    currentIndex: -1,
    answers: [],
    isListening: false,
    examActive: false,
    ttsActive: false,
    restartTimer: null,
    cooldownUntil: 0,
  };

  const COOLDOWN_AFTER_TTS_MS = 1200;

  // ----- DOM refs (populated on DOMContentLoaded) -----
  let els = {};

  document.addEventListener("DOMContentLoaded", () => {
    els = {
      statusDot: document.getElementById("status-dot"),
      statusText: document.getElementById("status-text"),
      interimBox: document.getElementById("interim-transcript"),
      finalBox: document.getElementById("final-transcript"),
      questionBox: document.getElementById("current-question"),
      answerList: document.getElementById("answer-list"),
      startBtn: document.getElementById("start-exam-btn"),
      logBox: document.getElementById("activity-log"),
    };
    if (els.startBtn) {
      els.startBtn.addEventListener("click", startExam);
    }
  });

  // ============================================================
  //  1. Speech Recognition Setup
  // ============================================================
  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    alert("Speech Recognition is not supported in this browser. Please use Chrome.");
  }

  const recognition = new SpeechRecognition();
  recognition.lang = "en-IN";
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.maxAlternatives = 3;

  recognition.onresult = handleRecognitionResult;
  recognition.onerror = handleRecognitionError;
  recognition.onend = handleRecognitionEnd;
  recognition.onstart = () => setListeningState(true);

  function safeStartRecognition() {
    clearTimeout(state.restartTimer);
    try {
      recognition.start();
    } catch (_) {
      // already started — ignore
    }
  }

  function handleRecognitionEnd() {
    setListeningState(false);
    if (state.examActive && !state.ttsActive) {
      state.restartTimer = setTimeout(safeStartRecognition, 300);
    }
  }

  function handleRecognitionError(event) {
    const ignorable = ["no-speech", "aborted"];
    if (ignorable.includes(event.error)) {
      log(`Mic idle — still listening…`);
      return;
    }
    log(`Recognition error: ${event.error}`);
    if (event.error === "not-allowed") {
      setStatus("error", "Microphone access denied");
      state.examActive = false;
    }
  }

  // ============================================================
  //  2. Result handling — interim + final
  // ============================================================
  function handleRecognitionResult(event) {
    let interim = "";
    let finalTranscript = "";

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalTranscript += transcript;
      } else {
        interim += transcript;
      }
    }

    if (interim) {
      showInterim(interim);
    }

    if (finalTranscript) {
      const normalized = normalize(finalTranscript);
      showFinal(normalized);

      if (Date.now() < state.cooldownUntil) {
        log("Ignored (cooldown — mic settling)");
        return;
      }

      processTranscript(normalized);
    }
  }

  // ============================================================
  //  3. Word Normalization Pipeline
  // ============================================================
  const NUMBER_WORDS = {
    zero: "0", one: "1", two: "2", three: "3", four: "4",
    five: "5", six: "6", seven: "7", eight: "8", nine: "9",
    ten: "10", eleven: "11", twelve: "12", thirteen: "13",
    fourteen: "14", fifteen: "15", sixteen: "16", seventeen: "17",
    eighteen: "18", nineteen: "19", twenty: "20", thirty: "30",
    forty: "40", fifty: "50", sixty: "60", seventy: "70",
    eighty: "80", ninety: "90", hundred: "100", thousand: "1000",
    lakh: "100000", crore: "10000000",
  };

  const CONTRACTIONS = {
    "don't": "do not", "doesn't": "does not", "didn't": "did not",
    "won't": "will not", "can't": "cannot", "couldn't": "could not",
    "shouldn't": "should not", "wouldn't": "would not",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not",
    "weren't": "were not", "haven't": "have not", "hasn't": "has not",
    "hadn't": "had not", "it's": "it is", "that's": "that is",
    "there's": "there is", "here's": "here is", "what's": "what is",
    "who's": "who is", "let's": "let us", "i'm": "i am",
    "you're": "you are", "we're": "we are", "they're": "they are",
    "i've": "i have", "you've": "you have", "we've": "we have",
    "they've": "they have", "i'll": "i will", "you'll": "you will",
    "he'll": "he will", "she'll": "she will", "we'll": "we will",
    "they'll": "they will", "i'd": "i would", "you'd": "you would",
    "he'd": "he would", "she'd": "she would", "we'd": "we would",
    "they'd": "they would",
  };

  const FILLER_WORDS = [
    "um", "uh", "umm", "uhh", "hmm", "ah", "er", "erm",
    "like", "basically", "actually", "you know", "so yeah",
    "i mean", "sort of", "kind of",
  ];

  function normalize(text) {
    let result = text.toLowerCase().trim();

    // Expand contractions
    for (const [contraction, expansion] of Object.entries(CONTRACTIONS)) {
      result = result.replace(new RegExp("\\b" + escapeRegex(contraction) + "\\b", "gi"), expansion);
    }

    // Remove filler words (longest first to avoid partial matches)
    const sortedFillers = [...FILLER_WORDS].sort((a, b) => b.length - a.length);
    for (const filler of sortedFillers) {
      result = result.replace(new RegExp("\\b" + escapeRegex(filler) + "\\b", "gi"), " ");
    }

    // Normalize number words to digits (standalone, not inside longer words)
    for (const [word, digit] of Object.entries(NUMBER_WORDS)) {
      result = result.replace(new RegExp("\\b" + word + "\\b", "gi"), digit);
    }

    // Collapse whitespace
    result = result.replace(/\s+/g, " ").trim();

    return result;
  }

  function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  // ============================================================
  //  4. Fuzzy Command Matching
  // ============================================================
  const COMMANDS = {
    next: {
      synonyms: [
        "next question", "go next", "move on", "move to next",
        "next one please", "next one", "agle question",
        "agla question", "agla sawal",
      ],
      action: cmdNextQuestion,
    },
    skip: {
      synonyms: [
        "skip question", "skip this", "skip this question",
        "leave this", "come back later",
      ],
      action: cmdSkipQuestion,
    },
    repeat: {
      synonyms: [
        "repeat question", "say again", "say that again",
        "repeat that", "once more", "phir se", "phir se bolo",
        "repeat karo", "dobara bolo",
      ],
      action: cmdRepeatQuestion,
    },
    clear: {
      synonyms: [
        "clear answer", "delete answer", "redo answer",
        "erase answer", "remove answer", "clear my answer",
        "i want to redo", "answer dobara",
      ],
      action: cmdClearAnswer,
    },
    submit: {
      synonyms: [
        "submit exam", "finish exam", "end exam",
        "i am done", "exam khatam", "submit karo",
        "exam over", "exam finish",
      ],
      action: cmdSubmitExam,
    },
    help: {
      synonyms: [
        "help me", "help please", "what can i say",
        "list commands", "voice commands",
      ],
      action: cmdHelp,
    },
  };

  const COMMAND_THRESHOLD = 0.55;

  function matchCommand(transcript) {
    let bestMatch = null;
    let bestScore = 0;

    for (const [name, cmd] of Object.entries(COMMANDS)) {
      for (const synonym of cmd.synonyms) {
        // Exact containment
        if (transcript.includes(synonym)) {
          return { name, action: cmd.action, score: 1.0 };
        }

        // Word-overlap score
        const overlapScore = wordOverlap(transcript, synonym);
        if (overlapScore > bestScore) {
          bestScore = overlapScore;
          bestMatch = { name, action: cmd.action, score: overlapScore };
        }

        // Edit-distance similarity
        const simScore = similarity(transcript, synonym);
        if (simScore > bestScore) {
          bestScore = simScore;
          bestMatch = { name, action: cmd.action, score: simScore };
        }
      }
    }

    if (bestMatch && bestMatch.score >= COMMAND_THRESHOLD) {
      return bestMatch;
    }
    return null;
  }

  function wordOverlap(a, b) {
    const wordsA = new Set(a.split(/\s+/));
    const wordsB = b.split(/\s+/);
    if (wordsB.length === 0) return 0;
    let hits = 0;
    for (const w of wordsB) {
      if (wordsA.has(w)) hits++;
    }
    return hits / wordsB.length;
  }

  function similarity(a, b) {
    const distance = levenshtein(a, b);
    const maxLen = Math.max(a.length, b.length);
    if (maxLen === 0) return 1;
    return 1 - distance / maxLen;
  }

  function levenshtein(a, b) {
    const m = a.length, n = b.length;
    const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
    for (let i = 0; i <= m; i++) dp[i][0] = i;
    for (let j = 0; j <= n; j++) dp[0][j] = j;
    for (let i = 1; i <= m; i++) {
      for (let j = 1; j <= n; j++) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        dp[i][j] = Math.min(
          dp[i - 1][j] + 1,
          dp[i][j - 1] + 1,
          dp[i - 1][j - 1] + cost
        );
      }
    }
    return dp[m][n];
  }

  // ============================================================
  //  5. Transcript Processing
  // ============================================================
  function processTranscript(text) {
    // Check for "go to question N" pattern before fuzzy matching
    const goToMatch = text.match(
      /(?:go\s*(?:to|back\s*to)?|question)\s*(\d+)/
    );
    if (goToMatch) {
      const qNum = parseInt(goToMatch[1], 10);
      if (qNum >= 1 && qNum <= state.questions.length) {
        cmdGoToQuestion(qNum);
        return;
      }
    }

    const cmd = matchCommand(text);

    if (cmd) {
      log(`Command recognized: "${cmd.name}" (score: ${cmd.score.toFixed(2)})`);
      cmd.action();
      return;
    }

    // Not a command — record as answer
    if (state.currentIndex >= 0 && state.currentIndex < state.questions.length) {
      state.answers[state.currentIndex] = text;
      updateAnswerDisplay();
      speak("Answer recorded. You may continue when ready.");
      log(`Answer for Q${state.currentIndex + 1}: "${text}"`);
    } else if (state.currentIndex === -1) {
      speak("Say next question to hear the first question.");
    } else if (state.currentIndex >= state.questions.length) {
      const skipped = findSkippedQuestions();
      if (skipped.length > 0) {
        speak(
          `You are past the last question. Say go to question ${skipped[0]} to answer a skipped question, or submit exam to finish.`
        );
      } else {
        speak("All questions are answered. Say submit exam to finish.");
      }
    }
  }

  // ============================================================
  //  6. Command Actions
  // ============================================================
  function cmdNextQuestion() {
    state.currentIndex++;

    if (state.currentIndex < state.questions.length) {
      const qNum = state.currentIndex + 1;
      const qText = state.questions[state.currentIndex];
      showQuestion(qNum, qText);
      speak(`Question ${qNum}. ${qText}`);
      log(`Question ${qNum} presented`);
    } else {
      state.currentIndex = state.questions.length;
      const skipped = findSkippedQuestions();
      let msg = "You have reached the end of the exam. ";
      if (skipped.length > 0) {
        msg += `You have ${skipped.length} unanswered question${skipped.length > 1 ? "s" : ""}: ${skipped.join(", ")}. Say go to question followed by the number to answer them. `;
      }
      msg += "Say submit exam to finish.";
      speak(msg);
      log("All questions completed");
    }
  }

  function cmdSkipQuestion() {
    if (state.currentIndex < 0) {
      speak("No question to skip. Say next question to begin.");
      return;
    }
    if (state.currentIndex >= state.questions.length) {
      speak("You are already past the last question.");
      return;
    }

    const skippedNum = state.currentIndex + 1;
    log(`Question ${skippedNum} skipped`);

    state.currentIndex++;
    if (state.currentIndex < state.questions.length) {
      const qNum = state.currentIndex + 1;
      const qText = state.questions[state.currentIndex];
      showQuestion(qNum, qText);
      speak(`Question ${skippedNum} skipped. Question ${qNum}. ${qText}`);
    } else {
      state.currentIndex = state.questions.length;
      speak(
        `Question ${skippedNum} skipped. You have reached the end. ` +
        `Say go to question ${skippedNum} to go back, or submit exam to finish.`
      );
    }
  }

  function cmdGoToQuestion(qNum) {
    const idx = qNum - 1;
    state.currentIndex = idx;
    const qText = state.questions[idx];
    showQuestion(qNum, qText);

    const existingAnswer = state.answers[idx];
    let msg = `Going to question ${qNum}. ${qText}`;
    if (existingAnswer) {
      msg += ` Your current answer is: ${existingAnswer}. Say clear answer to remove it and answer again.`;
    }
    speak(msg);
    log(`Jumped to question ${qNum}`);
  }

  function cmdClearAnswer() {
    if (state.currentIndex < 0 || state.currentIndex >= state.questions.length) {
      speak("No question selected. Say next question or go to a question number first.");
      return;
    }

    const qNum = state.currentIndex + 1;
    if (!state.answers[state.currentIndex]) {
      speak(`There is no answer for question ${qNum} to clear.`);
      return;
    }

    state.answers[state.currentIndex] = undefined;
    updateAnswerDisplay();
    speak(`Answer for question ${qNum} has been cleared. You may now give a new answer.`);
    log(`Answer for Q${qNum} cleared`);
  }

  function cmdRepeatQuestion() {
    if (state.currentIndex >= 0 && state.currentIndex < state.questions.length) {
      speak(state.questions[state.currentIndex]);
      log("Question repeated");
    } else {
      speak("No question to repeat. Say next question to begin.");
    }
  }

  function cmdSubmitExam() {
    state.examActive = false;
    recognition.stop();

    const skipped = findSkippedQuestions();
    let msg = "";
    if (skipped.length > 0) {
      msg = `Note: question${skipped.length > 1 ? "s" : ""} ${skipped.join(", ")} ${skipped.length > 1 ? "are" : "is"} unanswered. `;
    }
    msg += "Your exam has been submitted. Thank you and all the best.";

    const utterance = new SpeechSynthesisUtterance(msg);
    utterance.lang = "en-IN";
    utterance.rate = 0.92;
    const voices = window.speechSynthesis.getVoices();
    const indianVoice = voices.find(
      (v) => v.lang === "en-IN" || v.lang.startsWith("en-IN")
    );
    if (indianVoice) utterance.voice = indianVoice;

    utterance.onend = () => {
      window.location.href = "/exam/submitted";
    };

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);

    setStatus("idle", "Exam submitted");
    log("Exam submitted");
    console.log("Final answers:", state.answers);
  }

  function cmdHelp() {
    const helpText =
      "Available commands. " +
      "Say next question to hear the next question. " +
      "Say skip question to skip and come back later. " +
      "Say go to question followed by the number, for example, go to question 3, to jump to that question. " +
      "Say repeat question to hear the current question again. " +
      "Say clear answer to delete your answer and record a new one. " +
      "Say submit exam when you are finished. " +
      "Say help me to hear these instructions again.";
    speak(helpText);
    log("Help instructions spoken");
  }

  function findSkippedQuestions() {
    const skipped = [];
    for (let i = 0; i < state.questions.length; i++) {
      if (!state.answers[i]) {
        skipped.push(i + 1);
      }
    }
    return skipped;
  }

  // ============================================================
  //  7. Text-to-Speech (en-IN voice preferred)
  // ============================================================
  function speak(text) {
    window.speechSynthesis.cancel();
    state.ttsActive = true;

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-IN";
    utterance.rate = 0.92;
    utterance.pitch = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const indianVoice = voices.find(
      (v) => v.lang === "en-IN" || v.lang.startsWith("en-IN")
    );
    if (indianVoice) {
      utterance.voice = indianVoice;
    }

    if (state.examActive) {
      recognition.stop();
      utterance.onend = () => {
        state.cooldownUntil = Date.now() + COOLDOWN_AFTER_TTS_MS;
        setTimeout(() => {
          speakCue("You may speak now.");
        }, COOLDOWN_AFTER_TTS_MS);
      };
    }

    window.speechSynthesis.speak(utterance);
  }

  function speakCue(text) {
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-IN";
    utterance.rate = 1.1;
    utterance.pitch = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const indianVoice = voices.find(
      (v) => v.lang === "en-IN" || v.lang.startsWith("en-IN")
    );
    if (indianVoice) {
      utterance.voice = indianVoice;
    }

    utterance.onend = () => {
      state.ttsActive = false;
      state.cooldownUntil = Date.now() + 400;
      setTimeout(safeStartRecognition, 400);
    };

    window.speechSynthesis.speak(utterance);
  }

  // Pre-load voices (Chrome fires this async)
  if (window.speechSynthesis) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => {
      window.speechSynthesis.getVoices();
    };
  }

  // ============================================================
  //  8. UI Updates
  // ============================================================
  function setListeningState(listening) {
    state.isListening = listening;
    if (listening) {
      setStatus("listening", "Listening…");
    } else if (state.examActive) {
      setStatus("processing", "Restarting mic…");
    }
  }

  function setStatus(type, message) {
    if (!els.statusDot || !els.statusText) return;
    els.statusDot.className = "status-dot " + type;
    els.statusText.textContent = message;
  }

  function showInterim(text) {
    if (els.interimBox) {
      els.interimBox.textContent = text;
    }
  }

  function showFinal(text) {
    if (els.interimBox) els.interimBox.textContent = "";
    if (els.finalBox) {
      els.finalBox.textContent = text;
    }
  }

  function showQuestion(num, text) {
    if (els.questionBox) {
      els.questionBox.innerHTML =
        `<span class="q-number">Q${num}.</span> ${text}`;
    }
  }

  function updateAnswerDisplay() {
    if (!els.answerList) return;
    els.answerList.innerHTML = "";
    state.answers.forEach((ans, idx) => {
      if (!ans) return;
      const li = document.createElement("li");
      li.innerHTML = `<strong>Q${idx + 1}:</strong> ${ans}`;
      els.answerList.appendChild(li);
    });
  }

  function log(message) {
    const ts = new Date().toLocaleTimeString("en-IN");
    const entry = `[${ts}] ${message}`;
    console.log(entry);
    if (els.logBox) {
      const div = document.createElement("div");
      div.className = "log-entry";
      div.textContent = entry;
      els.logBox.prepend(div);
    }
  }

  // ============================================================
  //  9. Exam Lifecycle
  // ============================================================
  function startExam() {
    if (state.examActive) return;

    state.examActive = true;
    state.currentIndex = -1;
    state.answers = [];

    if (els.startBtn) {
      els.startBtn.disabled = true;
      els.startBtn.textContent = "Exam in Progress…";
    }

    speak(
      "The exam has started. Say next question to hear your first question. " +
      "You can say repeat question, help, or submit exam at any time."
    );
    log("Exam started");
  }

  // Expose startExam globally for the button onclick fallback
  window.startExam = startExam;
})();
