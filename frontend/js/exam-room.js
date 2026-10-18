/* =========================================================================
   exam-room.js : runs the voice exam.

   Uses the browser's built-in Web Speech API (free, no API key):
     - speechSynthesis      -> reads the question out loud (text-to-speech)
     - SpeechRecognition    -> turns the student's voice into text (speech-to-text)

   Flow for each question:
     show question -> speak it -> start listening + timer -> submit -> next
   ========================================================================= */

requireLogin("student");
const attemptId = new URLSearchParams(window.location.search).get("id");

let exam = null;              // data from the server
let current = 0;              // index of the current question
let secondsLeft = 0;
let timerId = null;
let reRecordsLeft = 1;
let typingMode = false;
let examRunning = false;

// ---------- Speech recognition setup ----------
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizer = null;
let listening = false;
let finalText = "";

if (SpeechRecognition) {
  recognizer = new SpeechRecognition();
  recognizer.lang = "en-US";
  recognizer.continuous = true;      // keep listening until we stop it
  recognizer.interimResults = true;  // show words while the student is speaking

  recognizer.onresult = (event) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const words = event.results[i][0].transcript;
      if (event.results[i].isFinal) finalText += words + " ";
      else interim += words;
    }
    showTranscript(finalText, interim);
  };

  // Chrome stops listening after a short silence. Restart it if we still want to listen.
  recognizer.onend = () => {
    if (listening) safeStart();
  };

  recognizer.onerror = (event) => {
    if (event.error === "not-allowed") {
      alert("Microphone access was blocked. You can continue by typing your answers.");
      listening = false;
      if (!typingMode) switchMode();
    }
  };
}

// start() throws an error if recognition is already running, so we ignore that case
function safeStart() {
  try { recognizer.start(); } catch (error) { /* already running */ }
}

// ---------- Load the exam ----------
async function loadExam() {
  exam = await api(`/api/attempts/${attemptId}/exam-room`);
  if (exam.status !== "In Progress") {
    window.location.href = "result.html?id=" + attemptId;
    return;
  }
  document.getElementById("examName").textContent = exam.exam_title;
  document.getElementById("startInfo").textContent =
    `${exam.questions.length} questions | ${exam.time_per_answer} seconds per answer`;
  if (!SpeechRecognition) document.getElementById("voiceWarning").classList.remove("hidden");

  // If the student refreshed the page, continue from the first unanswered question
  current = exam.questions.findIndex(q => !q.answered);
  if (current === -1) current = exam.questions.length;
}

// ---------- Screens ----------
async function startExam() {
  // Ask for microphone permission once at the start
  if (SpeechRecognition && navigator.mediaDevices) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(track => track.stop());
    } catch (error) {
      typingMode = false;
      switchMode();
    }
  } else {
    typingMode = false;
    switchMode();
  }
  if (!SpeechRecognition) document.getElementById("modeBtn").classList.add("hidden");

  examRunning = true;
  document.getElementById("startScreen").classList.add("hidden");
  document.getElementById("questionScreen").classList.remove("hidden");
  document.getElementById("timer").classList.remove("hidden");
  showQuestion();
}

function showQuestion() {
  if (current >= exam.questions.length) {
    finishExam();
    return;
  }
  const q = exam.questions[current];
  document.getElementById("qNumber").textContent = `Question ${current + 1} of ${exam.questions.length}`;
  document.getElementById("qText").textContent = q.question;
  document.getElementById("progressBar").style.width = (current / exam.questions.length) * 100 + "%";

  // reset answer area
  finalText = "";
  reRecordsLeft = 1;
  document.getElementById("typedAnswer").value = "";
  document.getElementById("reRecordBtn").disabled = false;
  document.getElementById("reRecordBtn").textContent = "Re-record (1 left)";
  document.getElementById("transcript").innerHTML =
    '<span class="muted">Your answer will appear here as you speak.</span>';

  startTimer();
  speakQuestion(() => {
    if (!typingMode) startListening();   // start listening after the question is read
  });
}

// ---------- Text-to-speech ----------
function speakQuestion(afterSpeaking) {
  stopListening();
  window.speechSynthesis.cancel();
  const speech = new SpeechSynthesisUtterance(exam.questions[current].question);
  speech.lang = "en-US";
  speech.rate = 0.95;
  speech.onend = () => { if (afterSpeaking) afterSpeaking(); };
  setMicStatus("Reading the question...");
  window.speechSynthesis.speak(speech);
}

// ---------- Speech-to-text ----------
function startListening() {
  if (!recognizer || listening) return;
  listening = true;
  safeStart();
  document.getElementById("micBtn").classList.add("listening");
  setMicStatus("Listening... tap to pause");
}

function stopListening() {
  if (!recognizer || !listening) return;
  listening = false;
  recognizer.stop();
  document.getElementById("micBtn").classList.remove("listening");
  setMicStatus("Paused. Tap to continue speaking");
}

function toggleListening() {
  if (listening) stopListening();
  else startListening();
}

function setMicStatus(text) {
  document.getElementById("micStatus").textContent = text;
}

function showTranscript(finalPart, interimPart) {
  document.getElementById("transcript").innerHTML =
    escapeHtml(finalPart) + `<span class="interim">${escapeHtml(interimPart)}</span>`;
}

function reRecord() {
  if (reRecordsLeft === 0) return;
  reRecordsLeft--;
  finalText = "";
  document.getElementById("typedAnswer").value = "";
  showTranscript("", "");
  document.getElementById("reRecordBtn").disabled = true;
  document.getElementById("reRecordBtn").textContent = "No re-records left";
  if (!typingMode) {
    stopListening();
    setTimeout(startListening, 300);
  }
}

// ---------- Typing fallback ----------
function switchMode() {
  typingMode = !typingMode;
  document.getElementById("voiceArea").classList.toggle("hidden", typingMode);
  document.getElementById("typeArea").classList.toggle("hidden", !typingMode);
  document.getElementById("modeBtn").textContent = typingMode ? "Use voice" : "Type instead";
  if (typingMode) {
    stopListening();
    document.getElementById("typedAnswer").value = finalText.trim();
  } else if (examRunning) {
    finalText = document.getElementById("typedAnswer").value + " ";
    showTranscript(finalText, "");
    startListening();
  }
}

// ---------- Timer ----------
function startTimer() {
  clearInterval(timerId);
  secondsLeft = exam.time_per_answer;
  updateTimer();
  timerId = setInterval(() => {
    secondsLeft--;
    updateTimer();
    if (secondsLeft <= 0) submitAnswer();   // time is up: submit automatically
  }, 1000);
}

function updateTimer() {
  const m = String(Math.floor(Math.max(secondsLeft, 0) / 60)).padStart(2, "0");
  const s = String(Math.max(secondsLeft, 0) % 60).padStart(2, "0");
  const timer = document.getElementById("timer");
  timer.textContent = `${m}:${s}`;
  timer.classList.toggle("low", secondsLeft <= 15);
}

// ---------- Submit ----------
async function submitAnswer() {
  clearInterval(timerId);
  stopListening();
  window.speechSynthesis.cancel();
  const button = document.getElementById("submitBtn");
  button.disabled = true;

  const answer = typingMode ? document.getElementById("typedAnswer").value : finalText;
  try {
    await api(`/api/attempts/${attemptId}/answer`, {
      method: "POST",
      body: {
        number: exam.questions[current].number,
        answer: answer.trim(),
        typed: typingMode,
        seconds_taken: exam.time_per_answer - Math.max(secondsLeft, 0),
      },
    });
    current++;
    showQuestion();
  } catch (error) {
    alert(error.message);
  }
  button.disabled = false;
}

async function finishExam() {
  examRunning = false;
  clearInterval(timerId);
  stopListening();
  await api(`/api/attempts/${attemptId}/finish`, { method: "POST" });
  document.getElementById("progressBar").style.width = "100%";
  document.getElementById("questionScreen").classList.add("hidden");
  document.getElementById("timer").classList.add("hidden");
  document.getElementById("doneScreen").classList.remove("hidden");
  document.getElementById("resultLink").href = "result.html?id=" + attemptId;
}

// ---------- Integrity: record when the student leaves the exam tab ----------
document.addEventListener("visibilitychange", () => {
  if (document.hidden && examRunning) {
    api(`/api/attempts/${attemptId}/flag`, { method: "POST", body: { type: "tab_switch" } });
  }
});

loadExam();
