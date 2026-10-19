VIVAVOICE: A RAG-Grounded AI Voice Examiner
Semester Project by Muhammad Farhan Khan (F24-BSSE-027)
Foundation University Islamabad
=====================================================================
 
 
WHAT IS IN THIS FOLDER
---------------------------------------------------------------------
VivaVoice/
  frontend/                 All screens (plain HTML + CSS + a little JavaScript)
    index.html              Landing page
    login.html              Log in
    register.html           Create account (Student or Examiner)
    examiner-dashboard.html Examiner home: stats + list of exams
    create-exam.html        Upload document + exam settings
    exam-details.html       Exam code, settings, student attempts, publish/close/delete
    result.html             Full result: answers, scores, feedback, source, override
    student-dashboard.html  Student home: join exam by code, my exams
    practice.html           Practice Mode: upload own report
    exam-room.html          The voice exam (question, mic, live transcript, timer)
    admin.html              Admin panel: users and system stats
    css/style.css           One stylesheet for every page
    js/app.js               Shared helpers (talking to the server, menu, login)
    js/exam-room.js         Voice exam logic (Web Speech API)
 
  backend/                  Python server (FastAPI) + local MongoDB
    main.py                 All API routes, and serves the frontend pages
    database.py             Connection to local MongoDB (mongodb://localhost:27017)
    auth.py                 Password hashing (bcrypt) and login tokens (JWT)
    documents.py            Reads PDF/DOCX/TXT and splits it into chunks (RAG step 1)
    ai_engine.py            Question generation + grading (PLACEHOLDER, see below)
    requirements.txt        Python packages to install
 
  sample/
    Sample_Software_Testing_Chapter.docx   A test document to try the system
 
 
ONE-TIME SETUP (Windows)
---------------------------------------------------------------------
1. Install Python 3.10 or newer from https://www.python.org/downloads/
   IMPORTANT: tick "Add python.exe to PATH" on the first install screen.
 
2. Install MongoDB Community Server from
   https://www.mongodb.com/try/download/community
   - Choose "Complete" setup.
   - Keep "Install MongoDB as a Service" ticked (it then starts automatically).
   - Keep "Install MongoDB Compass" ticked (an app to SEE your database).
 
3. Open a terminal (Command Prompt) inside the "backend" folder and run:
 
       pip install -r requirements.txt
 
 
RUNNING THE PROJECT (every time)
---------------------------------------------------------------------
1. Open a terminal inside the "backend" folder and run:
 
       python -m uvicorn main:app --reload
 
2. Open Google Chrome (or Microsoft Edge) and go to:
 
       http://localhost:8000
 
3. To stop the server, press Ctrl + C in the terminal.
 
Default admin account (created automatically the first time):
       Email:    admin@vivavoice.local
       Password: Admin@123
 
 
DEMO STEPS (good for showing your teacher)
---------------------------------------------------------------------
1. Register as an Examiner -> Create Exam -> upload
   sample/Sample_Software_Testing_Chapter.docx -> copy the exam code.
2. Log out. Register as a Student -> enter the exam code -> Start exam.
   Allow the microphone. The question is read aloud, then you answer by
   speaking. Your words appear in the live transcript. ("Type instead"
   works if the mic is not available.)
3. Log out. Log in as the Examiner -> View exam -> Review the attempt.
   You can see each answer, its score, the feedback and the exact source
   section from the document. Change a score with "Override score".
   Click "Publish results" so the student can see them.
4. Log in as the Student again -> View to see the published result.
5. Log in as Admin to see all users and system numbers.
 
 
SEEING THE DATA IN MONGODB
---------------------------------------------------------------------
Open MongoDB Compass -> connect to mongodb://localhost:27017
-> open the "vivavoice" database. It has 4 collections:
   users      examiners, students and the admin (passwords are hashed)
   exams      exam settings, exam code, document name
   chunks     the document split into small sections (RAG)
   attempts   each student's questions, answers, scores and flags
 
 
IMPORTANT NOTES
---------------------------------------------------------------------
- AI PLACEHOLDER: backend/ai_engine.py currently makes questions and
  grades answers with simple keyword rules, so the full system works
  offline. In the next phase the two functions in that file
  (generate_question and grade_answer) will be replaced with Gemini API
  calls, and chunks will get embeddings for vector search. No other file
  needs to change.
- VOICE: speech-to-text uses the browser's built-in Web Speech API. It
  works in Chrome and Edge and needs an internet connection. Text-to-speech
  works in all modern browsers.
- The microphone only works on http://localhost or https sites, so always
  open the project through http://localhost:8000.
 
 
COMMON PROBLEMS
---------------------------------------------------------------------
"Cannot connect to MongoDB"
    MongoDB is not running. Press Windows key, type "Services", find
    "MongoDB Server", right-click -> Start. Then run the server again.
 
"uvicorn is not recognized" or "pip is not recognized"
    Use: python -m pip install -r requirements.txt
    and: python -m uvicorn main:app --reload
 
Microphone does not work
    Click the lock icon next to the address bar -> allow Microphone,
    or use "Type instead" during the exam.
 