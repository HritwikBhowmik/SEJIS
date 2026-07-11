/* ============================================================
   SEJIS — Interview Page Controller (Multi-Page Flow)
   Each interview phase lives on its own HTML page.
   State is persisted via localStorage so reloads work.
   ============================================================ */

/* -------------------------------------------------------
   STATE (from localStorage)
   ------------------------------------------------------- */
let sessionId = localStorage.getItem('sejis_session_id') || null;
let timerInterval = null;
let timerSeconds = 0;
let recordId = null;

/* -------------------------------------------------------
   PAGE DETECTION & INIT
   ------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
  if (!requireAuth()) return;

  // Detect which page we are on and initialise accordingly
  const page = detectCurrentPage();

  switch (page) {
    case 'upload':
      initUploadPage();
      break;
    case 'intro':
      initIntroPage();
      break;
    case 'dsa':
      initDSAPage();
      break;
    case 'sysd':
      initSysdPage();
      break;
    case 'final':
      initFinalPage();
      break;
    case 'complete':
      initCompletePage();
      break;
  }
});

/**
 * Detect which interview page we're on based on the filename.
 */
function detectCurrentPage() {
  const path = window.location.pathname;
  if (path.includes('interview-upload')) return 'upload';
  if (path.includes('interview-intro'))  return 'intro';
  if (path.includes('interview-dsa'))    return 'dsa';
  if (path.includes('interview-sysd'))   return 'sysd';
  if (path.includes('interview-final'))  return 'final';
  if (path.includes('interview-complete')) return 'complete';
  // Fallback: if someone hits the old interview.html, redirect to upload
  return 'upload';
}

/* -------------------------------------------------------
   GUARD: Ensure session exists before proceeding
   ------------------------------------------------------- */
function requireSession() {
  sessionId = localStorage.getItem('sejis_session_id');
  if (!sessionId) {
    showToast('No active interview session. Please start from the beginning.', 'error');
    setTimeout(() => {
      window.location.href = 'interview-upload.html';
    }, 1500);
    return false;
  }
  return true;
}

/* -------------------------------------------------------
   PAGE: UPLOAD (Phase 0)
   ------------------------------------------------------- */
function initUploadPage() {
  setupResumeUpload();
  setupStartInterview();
  setupBackButton();
}

function setupBackButton() {
  const btn = document.getElementById('interview-back-btn');
  if (btn) {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      window.location.href = 'dashboard.html';
    });
  }
}

function setupResumeUpload() {
  const uploadZone = document.getElementById('upload-zone');
  const fileInput = document.getElementById('resume-file');
  const uploadBtn = document.getElementById('upload-resume-btn');

  if (!uploadZone || !fileInput || !uploadBtn) return;

  // Drag & drop visual feedback
  uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
  });

  uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
  });

  uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file && file.type === 'application/pdf') {
      fileInput.files = e.dataTransfer.files;
      handleFileSelected(file);
    } else {
      showToast('Please upload a PDF file.', 'error');
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
      handleFileSelected(fileInput.files[0]);
    }
  });

  uploadBtn.addEventListener('click', handleResumeUpload);
}

function handleFileSelected(file) {
  const uploadZone = document.getElementById('upload-zone');
  const fileName = document.getElementById('upload-file-name');
  const uploadBtn = document.getElementById('upload-resume-btn');

  uploadZone.classList.add('uploaded');
  fileName.textContent = file.name;
  document.getElementById('upload-text').textContent = 'File selected';
  document.getElementById('upload-hint').textContent = 'Click "Upload & Analyze" to proceed';
  uploadBtn.classList.remove('hidden');
}

async function handleResumeUpload() {
  const fileInput = document.getElementById('resume-file');
  const uploadBtn = document.getElementById('upload-resume-btn');
  const roleDisplay = document.getElementById('role-display');
  const startBtn = document.getElementById('start-interview-btn');

  if (!fileInput.files.length) {
    showToast('Please select a PDF file first.', 'error');
    return;
  }

  uploadBtn.disabled = true;
  uploadBtn.innerHTML = '<span class="spinner"></span> Analyzing resume...';

  try {
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    const data = await apiPostFormData('/api/v1/resume/cv-upload', formData);

    const roleText = data['detected-role'] || 'Role detected';
    document.getElementById('role-text').textContent = roleText;
    roleDisplay.classList.remove('hidden');
    startBtn.classList.remove('hidden');

    // Say it out loud
    await speakText(roleText);

  } catch (error) {
    showToast(error.message || 'Failed to upload resume.', 'error');
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Upload & Analyze';
  }
}

function setupStartInterview() {
  const startBtn = document.getElementById('start-interview-btn');
  if (startBtn) {
    startBtn.addEventListener('click', startIntroFromUpload);
  }
}

/**
 * Called from the upload page: hit the intro-ques API, store session + question,
 * then navigate to the intro page.
 */
async function startIntroFromUpload() {
  const startBtn = document.getElementById('start-interview-btn');
  startBtn.disabled = true;
  startBtn.innerHTML = '<span class="spinner"></span> Starting interview...';

  try {
    const data = await apiGet('/api/v1/interview/intro-ques');

    sessionId = data.session_id;
    localStorage.setItem('sejis_session_id', sessionId);

    // Store the intro question so the intro page can display it immediately
    localStorage.setItem('sejis_intro_question', data.initial_message || '');

    // Navigate to intro page
    window.location.href = 'interview-intro.html';

  } catch (error) {
    showToast(error.message || 'Failed to start interview.', 'error');
    startBtn.disabled = false;
    startBtn.textContent = 'Start Interview';
  }
}

/* -------------------------------------------------------
   PAGE: INTRO (Phase 1)
   ------------------------------------------------------- */
async function initIntroPage() {
  if (!requireSession()) return;
  setupBackButtonWithWarning();

  const questionText = localStorage.getItem('sejis_intro_question') || '';
  const loading = document.getElementById('intro-loading');
  const content = document.getElementById('intro-content');

  if (questionText) {
    // Question was pre-fetched from upload page
    if (loading) loading.classList.remove('active');
    if (content) content.classList.remove('hidden');

    document.getElementById('intro-question-text').textContent = questionText;

    // Speak the question
    showSpeakingIndicator('intro-speaking');
    await speakText(questionText);
    hideSpeakingIndicator('intro-speaking');

    // Start timer (5 minutes)
    startTimer(5, 'intro-timer', () => {
      submitIntroPhase();
    });

    // Start listening for speech
    startIntroListening();
  } else {
    // No cached question — fetch fresh (reload scenario)
    if (loading) {
      loading.classList.add('active');
    }
    if (content) content.classList.add('hidden');

    try {
      const data = await apiGet('/api/v1/interview/intro-ques');
      // Update session if it changed
      if (data.session_id) {
        sessionId = data.session_id;
        localStorage.setItem('sejis_session_id', sessionId);
      }

      if (loading) loading.classList.remove('active');
      if (content) content.classList.remove('hidden');

      const q = data.initial_message || 'Tell me about yourself.';
      document.getElementById('intro-question-text').textContent = q;
      localStorage.setItem('sejis_intro_question', q);

      showSpeakingIndicator('intro-speaking');
      await speakText(q);
      hideSpeakingIndicator('intro-speaking');

      startTimer(5, 'intro-timer', () => {
        submitIntroPhase();
      });

      startIntroListening();
    } catch (error) {
      if (loading) loading.classList.remove('active');
      showToast(error.message || 'Failed to load introduction question.', 'error');
    }
  }

  // Setup submit button
  document.getElementById('intro-next-btn').addEventListener('click', submitIntroPhase);
}

function startIntroListening() {
  const transcript = document.getElementById('intro-transcript');
  const indicator = document.getElementById('intro-stt-indicator');

  if (indicator) indicator.classList.add('listening');

  startListening({
    onInterim: (text) => {
      transcript.value = text;
    },
    onResult: (text) => {
      transcript.value = text;
    },
    onError: (err) => {
      console.error('Intro STT error:', err);
    },
    onEnd: () => {
      if (indicator) indicator.classList.remove('listening');
    }
  });
}

async function submitIntroPhase() {
  clearTimer();
  const transcript = stopListening() || document.getElementById('intro-transcript').value.trim();
  const nextBtn = document.getElementById('intro-next-btn');

  if (!transcript) {
    showToast('No response recorded. Moving to next phase.', 'info');
  }

  nextBtn.disabled = true;
  nextBtn.innerHTML = '<span class="spinner"></span> Evaluating...';

  try {
    // Send for evaluation
    await apiPost('/api/v1/eval/intro-eval', {
      session_id: sessionId,
      message: transcript || 'No response provided.'
    });
  } catch (error) {
    console.error('Intro eval error:', error);
  }

  // Store the transcript for DSA page to use
  localStorage.setItem('sejis_intro_answer', transcript || 'Completed introduction phase.');

  // Clean up cached question
  localStorage.removeItem('sejis_intro_question');

  // Navigate to DSA phase
  window.location.href = 'interview-dsa.html';
}

/* -------------------------------------------------------
   PAGE: DSA (Phase 2)
   ------------------------------------------------------- */
async function initDSAPage() {
  if (!requireSession()) return;
  setupBackButtonWithWarning();

  const loading = document.getElementById('dsa-loading');
  const content = document.getElementById('dsa-content');

  loading.classList.add('active');
  content.classList.add('hidden');

  const previousAnswer = localStorage.getItem('sejis_intro_answer') || 'Completed introduction phase.';

  try {
    const data = await apiPost('/api/v1/interview/dsa-ques', {
      session_id: sessionId,
      message: previousAnswer
    });

    loading.classList.remove('active');
    content.classList.remove('hidden');

    const questionText = data.dsa_ques;
    document.getElementById('dsa-question-text').textContent = questionText;

    // Say the motivational line
    showSpeakingIndicator('dsa-speaking');
    await speakText("Solve this and you'll get this job!");
    hideSpeakingIndicator('dsa-speaking');

    // Start timer (15 minutes)
    startTimer(15, 'dsa-timer', () => {
      submitDSAPhase();
    });

  } catch (error) {
    loading.classList.remove('active');
    showToast(error.message || 'Failed to load DSA question.', 'error');
  }

  // Setup submit button
  document.getElementById('dsa-submit-btn').addEventListener('click', submitDSAPhase);
}

async function submitDSAPhase() {
  clearTimer();
  const code = document.getElementById('dsa-code-editor').value.trim();
  const submitBtn = document.getElementById('dsa-submit-btn');

  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner"></span> Submitting...';

  try {
    // Send code for evaluation
    await apiPost('/api/v1/eval/dsa-eval', {
      session_id: sessionId,
      code: code || '# No code submitted'
    });
  } catch (error) {
    console.error('DSA eval error:', error);
  }

  // Store the code answer for system design page
  localStorage.setItem('sejis_dsa_answer', code || 'Completed DSA phase.');

  // Clean up
  localStorage.removeItem('sejis_intro_answer');

  // Navigate to System Design phase
  window.location.href = 'interview-sysd.html';
}

/* -------------------------------------------------------
   PAGE: SYSTEM DESIGN (Phase 3)
   ------------------------------------------------------- */
async function initSysdPage() {
  if (!requireSession()) return;
  setupBackButtonWithWarning();

  const loading = document.getElementById('sysd-loading');
  const content = document.getElementById('sysd-content');

  loading.classList.add('active');
  content.classList.add('hidden');

  const previousAnswer = localStorage.getItem('sejis_dsa_answer') || 'Completed DSA phase.';

  try {
    const data = await apiPost('/api/v1/interview/sysd-ques', {
      session_id: sessionId,
      message: previousAnswer
    });

    loading.classList.remove('active');
    content.classList.remove('hidden');

    const questionText = data.sysd_ques;
    document.getElementById('sysd-question-text').textContent = questionText;

    // Speak the question
    showSpeakingIndicator('sysd-speaking');
    await speakText(questionText);
    hideSpeakingIndicator('sysd-speaking');

    // Start timer (15 minutes)
    startTimer(15, 'sysd-timer', () => {
      submitSysdPhase();
    });

  } catch (error) {
    loading.classList.remove('active');
    showToast(error.message || 'Failed to load system design question.', 'error');
  }

  // Setup image upload
  setupImageUpload();

  // Setup submit button
  document.getElementById('sysd-submit-btn').addEventListener('click', submitSysdPhase);
}

function setupImageUpload() {
  const imageInput = document.getElementById('sysd-image-file');
  const preview = document.getElementById('sysd-image-preview');
  const label = document.getElementById('sysd-upload-label');

  if (!imageInput) return;

  imageInput.addEventListener('change', () => {
    if (imageInput.files.length > 0) {
      const file = imageInput.files[0];
      if (!file.type.startsWith('image/')) {
        showToast('Please upload an image file.', 'error');
        return;
      }
      const reader = new FileReader();
      reader.onload = (e) => {
        preview.src = e.target.result;
        preview.classList.add('visible');
        label.textContent = file.name;
      };
      reader.readAsDataURL(file);
    }
  });
}

async function submitSysdPhase() {
  clearTimer();
  const imageInput = document.getElementById('sysd-image-file');
  const submitBtn = document.getElementById('sysd-submit-btn');

  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner"></span> Submitting...';

  try {
    const formData = new FormData();
    formData.append('session_id', sessionId);

    if (imageInput.files.length > 0) {
      formData.append('file', imageInput.files[0]);
    } else {
      // Create a blank placeholder image if no file uploaded
      const canvas = document.createElement('canvas');
      canvas.width = 100;
      canvas.height = 100;
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
      formData.append('file', blob, 'no-design.png');
    }

    // Send for evaluation
    await apiPostFormData('/api/v1/eval/sysd-eval', formData);
  } catch (error) {
    console.error('System design eval error:', error);
  }

  // Clean up
  localStorage.removeItem('sejis_dsa_answer');

  // Navigate to Final phase
  window.location.href = 'interview-final.html';
}

/* -------------------------------------------------------
   PAGE: FINAL / HR (Phase 4)
   ------------------------------------------------------- */
async function initFinalPage() {
  if (!requireSession()) return;
  setupBackButtonWithWarning();

  const loading = document.getElementById('final-loading');
  const content = document.getElementById('final-content');

  loading.classList.add('active');
  content.classList.add('hidden');

  try {
    const data = await apiPost('/api/v1/interview/final-ques', {
      session_id: sessionId,
      message: 'Completed system design phase.'
    });

    loading.classList.remove('active');
    content.classList.remove('hidden');

    // The API returns { sysd_ques: ... } but it's actually the final question
    const questionText = data.sysd_ques;
    document.getElementById('final-question-text').textContent = questionText;

    // Speak the question
    showSpeakingIndicator('final-speaking');
    await speakText(questionText);
    hideSpeakingIndicator('final-speaking');

    // Start timer (5 minutes)
    startTimer(5, 'final-timer', () => {
      submitFinalPhase();
    });

    // Start listening for speech
    startFinalListening();

  } catch (error) {
    loading.classList.remove('active');
    showToast(error.message || 'Failed to load final question.', 'error');
  }

  // Setup submit button
  document.getElementById('final-submit-btn').addEventListener('click', submitFinalPhase);
}

function startFinalListening() {
  const transcript = document.getElementById('final-transcript');
  const indicator = document.getElementById('final-stt-indicator');

  if (indicator) indicator.classList.add('listening');

  resetTranscript();
  startListening({
    onInterim: (text) => {
      transcript.value = text;
    },
    onResult: (text) => {
      transcript.value = text;
    },
    onError: (err) => {
      console.error('Final STT error:', err);
    },
    onEnd: () => {
      if (indicator) indicator.classList.remove('listening');
    }
  });
}

async function submitFinalPhase() {
  clearTimer();
  const transcript = stopListening() || document.getElementById('final-transcript').value.trim();
  const submitBtn = document.getElementById('final-submit-btn');

  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner"></span> Evaluating...';

  try {
    // Send for evaluation
    await apiPost('/api/v1/eval/final-eval', {
      session_id: sessionId,
      message: transcript || 'No response provided.'
    });
  } catch (error) {
    console.error('Final eval error:', error);
  }

  // Navigate to completion page
  window.location.href = 'interview-complete.html';
}

/* -------------------------------------------------------
   PAGE: COMPLETION (Phase 5)
   ------------------------------------------------------- */
function initCompletePage() {
  if (!requireSession()) return;

  // Submit interview
  document.getElementById('submit-interview-btn').addEventListener('click', submitInterview);

  // Download report
  document.getElementById('download-report-btn').addEventListener('click', downloadFinalReport);
}

async function submitInterview() {
  const submitBtn = document.getElementById('submit-interview-btn');
  const downloadBtn = document.getElementById('download-report-btn');

  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner"></span> Saving results...';

  try {
    const data = await apiPost(`/api/v1/interview/submit-interview?session_id=${sessionId}`, {});

    recordId = data.record_id;
    // Store recordId in localStorage so it survives reload
    localStorage.setItem('sejis_record_id', recordId);
    const totalScore = data.total_score || 0;

    document.getElementById('final-total-score').textContent = `${totalScore}/350`;
    submitBtn.classList.add('hidden');
    downloadBtn.classList.remove('hidden');
    document.getElementById('back-to-dashboard-btn').classList.remove('hidden');

    showToast('Interview submitted successfully!', 'success');

    // Speak congratulations
    await speakText(`Congratulations! Your interview has been submitted. Your total score is ${totalScore} out of 350.`);

    // Clean up session data
    localStorage.removeItem('sejis_session_id');
    localStorage.removeItem('sejis_intro_question');
    localStorage.removeItem('sejis_intro_answer');
    localStorage.removeItem('sejis_dsa_answer');

  } catch (error) {
    showToast(error.message || 'Failed to submit interview.', 'error');
    submitBtn.disabled = false;
    submitBtn.textContent = 'Submit Interview';
  }
}

async function downloadFinalReport() {
  recordId = recordId || localStorage.getItem('sejis_record_id');
  if (!recordId) {
    showToast('No record ID available.', 'error');
    return;
  }

  try {
    showToast('Generating PDF report...', 'info');
    await apiDownloadFile(
      `/api/v1/download/interview/${recordId}/pdf`,
      'interview-report.pdf'
    );
    showToast('Report downloaded!', 'success');
  } catch (error) {
    showToast(error.message || 'Failed to download report.', 'error');
  }
}

/* -------------------------------------------------------
   TIMER
   ------------------------------------------------------- */

function startTimer(durationMinutes, timerId, onExpire) {
  clearTimer();

  timerSeconds = durationMinutes * 60;
  const timerEl = document.getElementById(timerId);
  if (!timerEl) return;

  updateTimerDisplay(timerEl);

  timerInterval = setInterval(() => {
    timerSeconds--;

    if (timerSeconds <= 0) {
      clearTimer();
      timerEl.textContent = '00:00';
      timerEl.classList.remove('warning', 'critical');
      if (onExpire) onExpire();
      return;
    }

    updateTimerDisplay(timerEl);

    // Visual warnings
    if (timerSeconds <= 30) {
      timerEl.classList.add('critical');
      timerEl.classList.remove('warning');
    } else if (timerSeconds <= 60) {
      timerEl.classList.add('warning');
      timerEl.classList.remove('critical');
    }
  }, 1000);
}

function updateTimerDisplay(el) {
  const mins = Math.floor(timerSeconds / 60);
  const secs = timerSeconds % 60;
  el.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function clearTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
}

/* -------------------------------------------------------
   SHARED UTILITIES
   ------------------------------------------------------- */

function setupBackButtonWithWarning() {
  const btn = document.getElementById('interview-back-btn');
  if (btn) {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      if (!confirm('Are you sure you want to leave? Your interview progress may be lost.')) {
        return;
      }
      window.location.href = 'dashboard.html';
    });
  }
}

function showSpeakingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('hidden');
}

function hideSpeakingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('hidden');
}
