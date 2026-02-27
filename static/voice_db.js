//  Voice-Based Examination System — MongoDB NoSQL Database
//   Tech Stack: Node.js + Mongoose (MongoDB)

const mongoose = require("mongoose");
require("dotenv").config();

//  DATABASE CONNECTION
const connectDB = async () => {
  try {
    await mongoose.connect(
      process.env.MONGO_URI || "mongodb://localhost:27017/voice_exam_system"
    );
    console.log(" MongoDB Connected: voice_exam_system");
  } catch (err) {
    console.error(" Connection Error:", err.message);
    process.exit(1);
  }
};

// 1 USER SCHEMA

const userSchema = new mongoose.Schema(
  {
    name:     { type: String, required: true, trim: true },
    email:    { type: String, required: true, unique: true, lowercase: true },
    password: { type: String, required: true },
    role: {
      type: String,
      enum: ["invigilator", "candidate"],
      required: true,
    },
    rollNumber: { type: String, unique: true, sparse: true },
    disability: { type: String, default: "visually_impaired" },
    voiceProfile: {
      language:   { type: String, default: "en-US" },
      speechRate: { type: Number, default: 1.0 },
      volume:     { type: Number, default: 1.0 },
    },
    isActive: { type: Boolean, default: true },
    status: {
      type: String,
      enum: ["active", "inactive"],
      default: "active",
    },
  },
  { timestamps: true }
);
const User = mongoose.model("User", userSchema);


// 2 USER PROFILE SCHEMA 

const userProfileSchema = new mongoose.Schema(
  {
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
      unique: true,                   // one profile per user only
    },

    // Personal Info
    dateOfBirth:    { type: Date },
    gender:         { type: String, enum: ["male", "female", "other"] },
    contactNumber:  { type: String },
    address:        { type: String },
    profilePicture: { type: String }, // file path or URL

    // Academic Info (candidates)
    institution:    { type: String }, // school / college name
    department:     { type: String }, // e.g., "Computer Science"
    yearOfStudy:    { type: Number }, // e.g., 3
    enrollmentYear: { type: Number },

    // Invigilator Info
    employeeId:  { type: String },
    designation: { type: String },    // e.g., "Professor", "Lecturer"

    // Accessibility Preferences
    preferredLanguage:  { type: String, default: "en" },
    requiresAssistance: { type: Boolean, default: false },
    accessibilityNotes: { type: String },

    // Preferred subject (links to Subject collection)
    preferredSubjectId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Subject",
    },

    status: {
      type: String,
      enum: ["active", "inactive"],
      default: "active",
    },
  },
  { timestamps: true }
);
const UserProfile = mongoose.model("UserProfile", userProfileSchema);

// 3 SUBJECT SCHEMA  
const subjectSchema = new mongoose.Schema(
  {
    name:        { type: String, required: true, unique: true, trim: true },
    code:        { type: String, unique: true, sparse: true }, // e.g., "AT101"
    description: { type: String },
    department:  { type: String },
    semester:    { type: Number },
    credits:     { type: Number },

    createdBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",                    // invigilator who added the subject
    },

    status: {
      type: String,
      enum: ["active", "inactive"],
      default: "active",
    },
  },
  { timestamps: true }
);
const Subject = mongoose.model("Subject", subjectSchema);


// 2.4 QUESTION BANK SCHEMA 

const questionBankSchema = new mongoose.Schema(
  {
    name:        { type: String, required: true, trim: true },
    description: { type: String },

    subjectId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Subject",
      required: true,                 // every bank belongs to a subject
    },
    createdBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
    },

    questions: [
      {
        questionId: {
          type: mongoose.Schema.Types.ObjectId,
          ref: "Question",
        },
        addedAt: { type: Date, default: Date.now },
      },
    ],

    totalQuestions: { type: Number, default: 0 },
    tags: [String],

    status: {
      type: String,
      enum: ["active", "inactive"],
      default: "active",
    },
  },
  { timestamps: true }
);
const QuestionBank = mongoose.model("QuestionBank", questionBankSchema);

// 5 QUESTION SCHEMA

const questionSchema = new mongoose.Schema(
  {
    questionText: { type: String, required: true },
    audioPrompt:  { type: String },

    type: {
      type: String,
      enum: ["short_answer", "long_answer", "mcq", "true_false"],
      default: "short_answer",
    },
    options:       [{ label: String, text: String }],
    correctAnswer: { type: String },
    marks:         { type: Number, default: 1 },
    difficultyLevel: {
      type: String,
      enum: ["easy", "medium", "hard"],
      default: "medium",
    },

    subjectId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Subject",
    },
    questionBankId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "QuestionBank",
    },
    createdBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
    },

    status: {
      type: String,
      enum: ["active", "inactive"],
      default: "active",
    },
  },
  { timestamps: true }
);
const Question = mongoose.model("Question", questionSchema);

// 6 EXAM PAPER SCHEMA

const examPaperSchema = new mongoose.Schema(
  {
    title:             { type: String, required: true },
    instructions:      { type: String },
    audioInstructions: { type: String },

    subjectId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Subject",
      required: true,
    },
    createdBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
    },

    questions: [
      {
        questionId: { type: mongoose.Schema.Types.ObjectId, ref: "Question" },
        order:      { type: Number },
      },
    ],

    durationMinutes: { type: Number, required: true },
    totalMarks:      { type: Number },

    status: {
      type: String,
      enum: ["draft", "active", "closed"],
      default: "draft",
    },
    recordStatus: {
      type: String,
      enum: ["active", "inactive"],
      default: "active",
    },
  },
  { timestamps: true }
);
const ExamPaper = mongoose.model("ExamPaper", examPaperSchema);

// 7 EXAM SESSION SCHEMA

const examSessionSchema = new mongoose.Schema(
  {
    examPaperId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "ExamPaper",
      required: true,
    },
    invigilatorId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
    },
    assignedCandidates: [{ type: mongoose.Schema.Types.ObjectId, ref: "User" }],

    startTime: { type: Date },
    endTime:   { type: Date },

    status: {
      type: String,
      enum: ["scheduled", "ongoing", "completed", "cancelled"],
      default: "scheduled",
    },
    recordStatus: {
      type: String,
      enum: ["active", "inactive"],
      default: "active",
    },
    notes: { type: String },
  },
  { timestamps: true }
);
const ExamSession = mongoose.model("ExamSession", examSessionSchema);

// 8 CANDIDATE ATTEMPT SCHEMA

const candidateAttemptSchema = new mongoose.Schema(
  {
    sessionId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "ExamSession",
      required: true,
    },
    candidateId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
    },
    examPaperId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "ExamPaper",
      required: true,
    },

    startedAt:   { type: Date, default: Date.now },
    submittedAt: { type: Date },

    status: {
      type: String,
      enum: ["in_progress", "submitted", "timed_out", "abandoned"],
      default: "in_progress",
    },
    currentQuestionIndex: { type: Number, default: 0 },
    totalMarksObtained:   { type: Number, default: 0 },

    recordStatus: {
      type: String,
      enum: ["active", "inactive"],
      default: "active",
    },

    voiceCommandLog: [
      {
        command:       { type: String },
        timestamp:     { type: Date, default: Date.now },
        questionIndex: { type: Number },
      },
    ],

    answers: [
      {
        questionId:      { type: mongoose.Schema.Types.ObjectId, ref: "Question" },
        questionOrder:   { type: Number },
        rawSpeechText:   { type: String },
        processedAnswer: { type: String },
        audioFilePath:   { type: String },
        marksAwarded:    { type: Number, default: 0 },
        isEvaluated:     { type: Boolean, default: false },
        evaluatorNote:   { type: String },
        submittedAt:     { type: Date, default: Date.now },
        repeatCount:     { type: Number, default: 0 },
      },
    ],
  },
  { timestamps: true }
);
const CandidateAttempt = mongoose.model("CandidateAttempt", candidateAttemptSchema);


//  VOICE COMMAND LOG SCHEMA

const voiceCommandLogSchema = new mongoose.Schema(
  {
    attemptId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "CandidateAttempt",
    },
    candidateId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
    },
    command: {
      type: String,
      enum: ["next", "previous", "repeat", "submit_answer", "submit_exam", "help", "unknown"],
    },
    rawInput:    { type: String },
    confidence:  { type: Number },
    actionTaken: { type: String },
    timestamp:   { type: Date, default: Date.now },
    status: {
      type: String,
      enum: ["active", "inactive"],
      default: "active",
    },
  },
  { timestamps: false }
);
const VoiceCommandLog = mongoose.model("VoiceCommandLog", voiceCommandLogSchema);

// 2.10 NLP LOG SCHEMA

const nlpLogSchema = new mongoose.Schema(
  {
    attemptId:  { type: mongoose.Schema.Types.ObjectId, ref: "CandidateAttempt" },
    questionId: { type: mongoose.Schema.Types.ObjectId, ref: "Question" },
    rawText:          { type: String },
    processedText:    { type: String },
    removedFillers:   [String],
    corrections: [{ original: String, corrected: String }],
    processingTimeMs: { type: Number },
    timestamp:        { type: Date, default: Date.now },
    status: {
      type: String,
      enum: ["active", "inactive"],
      default: "active",
    },
  }
);
const NlpLog = mongoose.model("NlpLog", nlpLogSchema);

// 11 LOG TABLE SCHEMA 

const logTableSchema = new mongoose.Schema(
  {
    // WHO performed the action
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
    },
    userRole: {
      type: String,
      enum: ["invigilator", "candidate", "system"],
      required: true,
    },

    // WHAT action was performed
    action: {
      type: String,
      required: true,
      enum: [
        "user_login",           "user_logout",          "password_changed",
        "user_created",         "user_updated",         "user_activated",
        "user_deactivated",     "profile_updated",
        "subject_created",      "subject_updated",      "subject_deactivated",
        "questionbank_created", "questionbank_updated",
        "question_added_to_bank",                       "question_removed_from_bank",
        "question_created",     "question_updated",     "question_deactivated",
        "exampaper_created",    "exampaper_updated",    "exampaper_activated",   "exampaper_closed",
        "session_started",      "session_ended",        "session_cancelled",
        "attempt_started",      "attempt_submitted",    "attempt_timed_out",
        "answer_evaluated",     "marks_updated",
        "system_error",         "data_exported",
      ],
    },

    // WHICH record was affected
    targetId: { type: mongoose.Schema.Types.ObjectId },
    targetCollection: {
      type: String,
      enum: [
        "User", "UserProfile", "Subject", "QuestionBank",
        "Question", "ExamPaper", "ExamSession",
        "CandidateAttempt", "VoiceCommandLog", "NlpLog",
      ],
    },

    // DETAILS
    description:   { type: String },
    previousValue: { type: mongoose.Schema.Types.Mixed },
    newValue:      { type: mongoose.Schema.Types.Mixed },

    // CONTEXT
    ipAddress: { type: String },
    userAgent: { type: String },
    sessionId: { type: String },

    status: {
      type: String,
      enum: ["active", "inactive"],
      default: "active",
    },

    timestamp: { type: Date, default: Date.now },
  },
  { timestamps: false }
);
const LogTable = mongoose.model("LogTable", logTableSchema);