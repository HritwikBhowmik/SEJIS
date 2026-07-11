/* ============================================================
   SEJIS — Web Speech API Module (TTS + STT)
   Text-to-Speech and Speech-to-Text encapsulated
   
   IMPORTANT: Both TTS and STT require the page to be served
   over HTTP/HTTPS (not file://). Access the app via:
   http://localhost:6969
   
   NOTE: http://0.0.0.0:6969 will NOT work for microphone/STT
   as Chrome requires a secure context (localhost or HTTPS).
   ============================================================ */

// Auto-redirect from 0.0.0.0 to localhost for secure context
(function() {
  if (window.location.hostname === '0.0.0.0') {
    const newUrl = window.location.href.replace('0.0.0.0', 'localhost');
    console.warn('Redirecting from 0.0.0.0 to localhost for secure context (required by STT/TTS)...');
    window.location.replace(newUrl);
  }
})();

/* -------------------------------------------------------
   TEXT-TO-SPEECH (TTS)
   Uses the SpeechSynthesis API
   ------------------------------------------------------- */

let ttsVoices = [];
let ttsReady = false;
let ttsResumeTimer = null;
let ttsFailed = false; // track if TTS keeps failing so we can stop retrying
let currentUtterance = null; // Prevent Chrome GC bug that causes synthesis-failed
let ttsWarmedUp = false; // track if we've done the silent warm-up

/**
 * Initialize TTS by loading available voices.
 * Must be called once (e.g. on page load).
 */
function initTTS() {
  if (!('speechSynthesis' in window)) {
    console.warn('SpeechSynthesis API not supported in this browser.');
    return;
  }

  function loadVoices() {
    const voices = window.speechSynthesis.getVoices();
    if (voices.length === 0) return;
    initTTSVoices(voices);
  }

  loadVoices();
  if (window.speechSynthesis.onvoiceschanged !== undefined) {
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }

  // Chrome requires a user gesture to unlock the audio context.
  // We register a one-time listener to perform a silent warm-up utterance.
  function warmUpTTS() {
    if (ttsWarmedUp) return;
    ttsWarmedUp = true;
    try {
      window.speechSynthesis.cancel(); // clear any stale state
      const silentUtterance = new SpeechSynthesisUtterance('');
      silentUtterance.volume = 0;
      silentUtterance.rate = 10; // speak as fast as possible
      window.speechSynthesis.speak(silentUtterance);
      console.log('TTS warm-up complete (silent utterance).');
    } catch (e) {
      console.warn('TTS warm-up failed:', e.message);
    }
    // Remove listeners after warm-up
    document.removeEventListener('click', warmUpTTS);
    document.removeEventListener('keydown', warmUpTTS);
    document.removeEventListener('touchstart', warmUpTTS);
  }

  document.addEventListener('click', warmUpTTS, { once: false });
  document.addEventListener('keydown', warmUpTTS, { once: false });
  document.addEventListener('touchstart', warmUpTTS, { once: false });
}

/**
 * Wait for voices to be available (Chrome/Linux loads them async via speech-dispatcher).
 * Returns a promise that resolves when voices are ready (or times out).
 */
function waitForVoices(timeoutMs = 5000) {
  return new Promise((resolve) => {
    if (ttsReady && ttsVoices.length > 0) {
      resolve();
      return;
    }

    const start = Date.now();
    const check = () => {
      const voices = window.speechSynthesis.getVoices();
      if (voices.length > 0) {
        // Voices just appeared — re-run init logic to populate ttsVoices
        initTTSVoices(voices);
        resolve();
        return;
      }
      if ((Date.now() - start) > timeoutMs) {
        console.warn('TTS: Voice loading timed out after', timeoutMs, 'ms.');
        resolve();
        return;
      }
      setTimeout(check, 200);
    };
    check();
  });
}

/**
 * Populate the ttsVoices array from a given voice list.
 * Extracted so it can be called from both initTTS and waitForVoices.
 */
function initTTSVoices(voices) {
  if (!voices || voices.length === 0) return;

  const localEnUS = voices.filter(v => v.lang === 'en-US' && v.localService);
  const localEn = voices.filter(v => v.lang.startsWith('en') && v.localService);
  const anyEnUS = voices.filter(v => v.lang === 'en-US');
  const anyEn = voices.filter(v => v.lang.startsWith('en'));

  const seen = new Set();
  ttsVoices = [];
  for (const list of [localEnUS, localEn, anyEnUS, anyEn]) {
    for (const v of list) {
      if (!seen.has(v.name)) {
        seen.add(v.name);
        ttsVoices.push(v);
      }
    }
  }

  // Fallback: add the first available voice regardless of language
  if (ttsVoices.length === 0 && voices.length > 0) {
    ttsVoices.push(voices[0]);
  }

  ttsReady = ttsVoices.length > 0;
  if (ttsReady && ttsFailed) {
    console.log('TTS voices reloaded — re-enabling TTS.');
    ttsFailed = false;
  }
  console.log('TTS voices loaded:', ttsVoices.length, '| Primary:', ttsVoices[0]?.name, '(local:', ttsVoices[0]?.localService, ')');
}

/**
 * Split text into chunks suitable for TTS (max ~80 chars per chunk).
 * Shorter chunks dramatically reduce synthesis-failed errors.
 */
function splitTextForTTS(text) {
  if (!text || text.length === 0) return [];

  // Clean up the text — remove excessive whitespace, newlines become spaces
  const cleanText = text.replace(/\n+/g, '. ').replace(/\s+/g, ' ').trim();

  // Split by sentence-ending punctuation
  const rawSentences = cleanText.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [cleanText];
  const chunks = [];
  const MAX_CHUNK = 80; // Reduced from 120 — shorter chunks are more reliable

  for (const sentence of rawSentences) {
    const trimmed = sentence.trim();
    if (!trimmed) continue;

    // If a sentence is still too long, split by commas, semicolons, or colons
    if (trimmed.length > MAX_CHUNK) {
      const subParts = trimmed.match(/[^,;:]+[,;:]?/g) || [trimmed];
      let currentChunk = '';
      for (const part of subParts) {
        if ((currentChunk + part).length > MAX_CHUNK && currentChunk.length > 0) {
          chunks.push(currentChunk.trim());
          currentChunk = part;
        } else {
          currentChunk += part;
        }
      }
      if (currentChunk.trim()) {
        chunks.push(currentChunk.trim());
      }
    } else {
      chunks.push(trimmed);
    }
  }

  return chunks.filter(c => c.length > 0);
}

/**
 * Create an utterance with the given voice (or no specific voice as fallback).
 */
function createUtterance(chunk, voice) {
  const utterance = new SpeechSynthesisUtterance(chunk);
  if (voice) {
    utterance.voice = voice;
    utterance.lang = voice.lang;
  } else {
    utterance.lang = 'en-US';
  }
  utterance.rate = 0.95;
  utterance.pitch = 1.0;
  utterance.volume = 1.0;
  return utterance;
}

/**
 * Speak text aloud using TTS.
 * Splits text into short chunks and speaks them sequentially.
 * If a voice causes synthesis-failed, it tries the next available voice.
 * @param {string} text - The text to speak
 * @returns {Promise<void>} Resolves when speech finishes
 */
async function speakText(text) {
  if (!('speechSynthesis' in window)) {
    console.warn('TTS not supported');
    return;
  }

  if (!text || text.trim().length === 0) {
    return;
  }

  if (ttsFailed) {
    // TTS has been permanently failing, skip to avoid blocking the UI
    console.warn('TTS previously failed on all voices, skipping.');
    return;
  }

  // Cancel any ongoing speech
  stopSpeaking();

  // Wait for voices to load (Chrome loads them asynchronously)
  await waitForVoices();

  // If voices still aren't ready, skip TTS gracefully
  if (!ttsReady || ttsVoices.length === 0) {
    console.warn('No TTS voices available, skipping.');
    return;
  }

  const chunks = splitTextForTTS(text);
  if (chunks.length === 0) {
    return;
  }

  return new Promise((resolve) => {
    let chunkIndex = 0;
    let voiceIndex = 0; // which voice to try from ttsVoices array
    let consecutiveErrors = 0;
    let chunkRetries = 0; // retries for the same chunk
    const MAX_CHUNK_RETRIES = 3; // retry same chunk up to 3 times before switching voice

    function speakNextChunk() {
      if (chunkIndex >= chunks.length) {
        clearResumeTimer();
        resolve();
        return;
      }

      const chunk = chunks[chunkIndex];
      const voice = ttsVoices[voiceIndex] || null;
      const utterance = createUtterance(chunk, voice);

      utterance.onend = () => {
        consecutiveErrors = 0; // reset on success
        chunkRetries = 0;
        chunkIndex++;
        // Small delay between chunks prevents synthesis-failed on rapid succession
        setTimeout(() => speakNextChunk(), 50);
      };

      utterance.onerror = (event) => {
        if (event.error === 'interrupted' || event.error === 'canceled') {
          clearResumeTimer();
          resolve();
          return;
        }

        consecutiveErrors++;
        console.warn(`TTS error: "${event.error}" with voice: ${voice?.name || 'default'}`);

        if (event.error === 'synthesis-failed' || event.error === 'audio-busy') {
          // First, retry the same voice a few times (synthesis-failed is often transient)
          chunkRetries++;
          if (chunkRetries <= MAX_CHUNK_RETRIES) {
            console.log(`Retrying chunk (attempt ${chunkRetries}/${MAX_CHUNK_RETRIES}) with voice: ${voice?.name || 'default'}`);
            // Cancel and wait before retry — clears stale engine state
            window.speechSynthesis.cancel();
            setTimeout(() => speakNextChunk(), 300 * chunkRetries);
            return;
          }

          // Exhausted retries for this voice — try the next voice
          chunkRetries = 0;
          voiceIndex++;
          if (voiceIndex < ttsVoices.length) {
            console.log(`Switching to next voice: ${ttsVoices[voiceIndex]?.name}`);
            window.speechSynthesis.cancel();
            setTimeout(() => speakNextChunk(), 500);
            return;
          }

          // Also try with NO specific voice (let browser pick)
          if (voiceIndex === ttsVoices.length) {
            voiceIndex++; // move past voices list — createUtterance will get null
            console.log('Trying with browser default voice...');
            window.speechSynthesis.cancel();
            setTimeout(() => speakNextChunk(), 500);
            return;
          }
        }

        // If we've had too many consecutive errors across all voices, give up
        if (consecutiveErrors >= (ttsVoices.length + 1) * MAX_CHUNK_RETRIES + 5) {
          console.error('TTS failed on all voices after extensive retries. Disabling TTS for this session.');
          ttsFailed = true;
          clearResumeTimer();
          resolve();
          return;
        }

        // Skip this chunk and move on (reset voice to primary for next chunk)
        voiceIndex = 0;
        chunkRetries = 0;
        chunkIndex++;
        speakNextChunk();
      };

      // Cancel before speaking to ensure clean state — prevents synthesis-failed from stale queue
      window.speechSynthesis.cancel();
      currentUtterance = utterance; // Retain globally to prevent Chrome GC bug
      // Delay after cancel to let the engine reset
      setTimeout(() => {
        window.speechSynthesis.speak(utterance);
      }, 50);
    }

    // Chrome workaround: periodically resume to prevent auto-pause on long speech
    startResumeTimer();

    // Delay to let cancel() finish before starting new speech
    setTimeout(() => speakNextChunk(), 200);
  });
}

/**
 * Chrome bug: speech pauses after ~14 seconds.
 * This timer periodically nudges it.
 */
function startResumeTimer() {
  clearResumeTimer();
  ttsResumeTimer = setInterval(() => {
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.resume();
    } else {
      clearResumeTimer();
    }
  }, 10000);
}

function clearResumeTimer() {
  if (ttsResumeTimer) {
    clearInterval(ttsResumeTimer);
    ttsResumeTimer = null;
  }
}

/**
 * Stop any currently playing speech.
 */
function stopSpeaking() {
  clearResumeTimer();
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
}

/**
 * Check if TTS is currently speaking.
 * @returns {boolean}
 */
function isSpeaking() {
  return 'speechSynthesis' in window && window.speechSynthesis.speaking;
}


/* -------------------------------------------------------
   SPEECH-TO-TEXT (STT)
   Uses the Web Speech Recognition API
   
   REQUIRES:
   - Google Chrome (NOT Chromium — it lacks the speech backend)
   - Page served over HTTP/HTTPS (not file://)
   - Chrome uses Google cloud servers for recognition.
   ------------------------------------------------------- */

let recognition = null;
let sttRunning = false;
let fullTranscript = '';
let sttOptions = {};
let restartAttempts = 0;
let networkErrorCount = 0; // Track consecutive network errors
const MAX_RESTART_ATTEMPTS = 5;
const MAX_NETWORK_ERRORS = 3; // Stop after 3 consecutive network errors

/**
 * Check if Speech Recognition is supported.
 * @returns {boolean}
 */
function isSTTSupported() {
  return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

/**
 * Detect if the browser is Google Chrome (not Chromium, Edge, etc.).
 * Chromium has the SpeechRecognition API stub but lacks Google's
 * proprietary speech recognition backend, causing 'network' errors.
 * @returns {boolean}
 */
function isGoogleChrome() {
  const ua = navigator.userAgent;
  // Chrome has "Chrome/" in UA, but so does Chromium, Edge, Opera, Brave...
  // Google Chrome is the only one that does NOT have Chromium, Edg, OPR, or Brave in UA
  if (!ua.includes('Chrome/')) return false;
  if (ua.includes('Chromium/')) return false;
  if (ua.includes('Edg/')) return false;
  if (ua.includes('OPR/')) return false;
  if (ua.includes('Brave/')) return false;
  return true;
}

/**
 * Check if the page is served over a Secure Context.
 * Speech Recognition and Microphone access are blocked by Chrome 
 * on insecure origins like http://0.0.0.0. Must use http://localhost.
 */
function isSecureContext() {
  const protocol = window.location.protocol;
  const hostname = window.location.hostname;
  
  if (protocol === 'https:') return true;
  if (protocol === 'http:' && (hostname === 'localhost' || hostname === '127.0.0.1')) return true;
  
  return false;
}

/**
 * Create a fresh SpeechRecognition instance with event handlers.
 */
function createRecognition(options) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const rec = new SpeechRecognition();

  rec.lang = 'en-US';
  rec.continuous = true;
  rec.interimResults = true;
  rec.maxAlternatives = 1;

  rec.onresult = (event) => {
    let interimTranscript = '';
    let finalTranscript = '';

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalTranscript += transcript + ' ';
      } else {
        interimTranscript += transcript;
      }
    }

    if (finalTranscript) {
      fullTranscript += finalTranscript;
      if (options.onResult) options.onResult(fullTranscript.trim());
    }

    if (interimTranscript && options.onInterim) {
      options.onInterim(fullTranscript + interimTranscript);
    }
  };

  rec.onerror = (event) => {
    if (event.error === 'no-speech' || event.error === 'aborted') {
      return; // Normal, not errors
    }

    console.error('STT error:', event.error);

    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
      sttRunning = false;
      if (options.onError) options.onError('Microphone access denied. Please allow microphone permission.');
      return;
    }

    if (event.error === 'network') {
      networkErrorCount++;

      if (!isSecureContext()) {
        sttRunning = false;
        if (options.onError) options.onError('Speech recognition requires localhost. Please open http://localhost:6969');
        return;
      }

      // If we get repeated network errors, the speech backend is unavailable
      // (most likely Chromium without Google's proprietary speech service)
      if (networkErrorCount >= MAX_NETWORK_ERRORS) {
        sttRunning = false;
        console.error(`STT: ${networkErrorCount} consecutive network errors. Speech recognition backend unavailable.`);
        if (!isGoogleChrome()) {
          if (options.onError) options.onError(
            'Speech recognition requires Google Chrome (not Chromium). ' +
            'Please install Google Chrome, or type your answer manually.'
          );
        } else {
          if (options.onError) options.onError(
            'Speech recognition service unavailable. Please check your internet connection, or type your answer manually.'
          );
        }
        return;
      }

      // Transient network issue — will auto-restart via onend
      return;
    }

    if (options.onError) options.onError(event.error);
  };

  rec.onend = () => {
    if (sttRunning && restartAttempts < MAX_RESTART_ATTEMPTS) {
      restartAttempts++;
      setTimeout(() => {
        if (!sttRunning) return;
        try {
          recognition = createRecognition(options);
          recognition.start();
        } catch (e) {
          console.warn('STT restart failed:', e.message);
          sttRunning = false;
          if (options.onEnd) options.onEnd();
        }
      }, 300);
    } else {
      sttRunning = false;
      if (options.onEnd) options.onEnd();
    }
  };

  rec.onaudiostart = () => {
    restartAttempts = 0;
  };

  return rec;
}

/**
 * Start continuous speech-to-text listening.
 * @param {object} options
 * @param {function(string)} options.onInterim - Called with interim transcript
 * @param {function(string)} options.onResult - Called with finalized transcript
 * @param {function()} options.onEnd - Called when recognition stops
 * @param {function(string)} options.onError - Called on error
 */
function startListening(options = {}) {
  if (!isSTTSupported()) {
    if (options.onError) options.onError('Speech recognition is not supported in this browser. Please use Google Chrome.');
    return;
  }

  // Warn upfront if using Chromium (it has the API but no backend)
  if (!isGoogleChrome()) {
    console.warn('STT: Browser is not Google Chrome. Speech recognition may not work (Chromium lacks the backend).');
  }

  if (!isSecureContext()) {
    if (options.onError) options.onError('Microphone requires a secure context. Please access the app via http://localhost:6969');
    return;
  }

  // Stop any existing recognition cleanly
  if (recognition) {
    sttRunning = false;
    try { recognition.abort(); } catch (e) { /* ignore */ }
    recognition = null;
  }

  fullTranscript = '';
  restartAttempts = 0;
  networkErrorCount = 0; // reset network error counter
  sttRunning = true;
  sttOptions = options;

  recognition = createRecognition(options);

  try {
    recognition.start();
    console.log('STT started listening');
  } catch (e) {
    console.error('Failed to start STT:', e);
    sttRunning = false;
    if (options.onError) options.onError('Failed to start speech recognition. Please check microphone permissions.');
  }
}

/**
 * Stop speech-to-text listening.
 * @returns {string} The full accumulated transcript
 */
function stopListening() {
  sttRunning = false;
  if (recognition) {
    try { recognition.stop(); } catch (e) {
      try { recognition.abort(); } catch (e2) { /* ignore */ }
    }
    recognition = null;
  }
  const result = fullTranscript.trim();
  console.log('STT stopped. Transcript length:', result.length);
  return result;
}

/**
 * Get the current accumulated transcript.
 * @returns {string}
 */
function getCurrentTranscript() {
  return fullTranscript.trim();
}

/**
 * Reset the accumulated transcript.
 */
function resetTranscript() {
  fullTranscript = '';
}

// Initialize TTS when module loads
initTTS();
