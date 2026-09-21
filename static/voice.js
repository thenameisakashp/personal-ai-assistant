/* =========================================================
   IRAA V1 — VOICE ENGINE
   Speech Recognition + Speech Synthesis

   Flow:

   🎙️ User speaks
        ↓
   Speech Recognition
        ↓
   message-input
        ↓
   Existing app.js
        ↓
   Gemini / Iraa
        ↓
   Assistant response
        ↓
   Speech Synthesis
        ↓
   🔊 Iraa speaks
   ========================================================= */

(() => {

    "use strict";


    /* =====================================================
       ELEMENTS
    ===================================================== */

    const voiceButton =
        document.getElementById("voice-btn");

    const messageInput =
        document.getElementById("message-input");

    const voiceStatus =
        document.getElementById("voice-status");


    /* =====================================================
       BASIC CHECK
    ===================================================== */

    if (!voiceButton) {

        console.warn(
            "Iraa V1: Voice button was not found."
        );

        return;
    }


    if (!messageInput) {

        console.warn(
            "Iraa V1: Message input was not found."
        );

        return;
    }


    /* =====================================================
       SPEECH RECOGNITION SUPPORT
    ===================================================== */

    const SpeechRecognition =
        window.SpeechRecognition ||
        window.webkitSpeechRecognition;


    if (!SpeechRecognition) {

        console.error(
            "Iraa V1: Speech Recognition is not supported by this browser."
        );


        voiceButton.disabled =
            true;


        voiceButton.title =
            "Voice recognition is not supported in this browser.";


        if (voiceStatus) {

            voiceStatus.textContent =
                "Voice recognition is not supported in this browser.";

        }


        return;
    }


    /* =====================================================
       RECOGNITION OBJECT
    ===================================================== */

    const recognition =
        new SpeechRecognition();


    recognition.lang =
        "en-IN";


    recognition.continuous =
        false;


    recognition.interimResults =
        true;


    recognition.maxAlternatives =
        1;


    /* =====================================================
       STATE
    ===================================================== */

    let isListening =
        false;


    let finalTranscript =
        "";


    /* =====================================================
       STATUS
    ===================================================== */

    function showStatus(
        message,
        state = ""
    ) {

        if (!voiceStatus) {
            return;
        }


        voiceStatus.textContent =
            message;


        voiceStatus.classList.add(
            "show"
        );


        voiceStatus.classList.remove(
            "listening",
            "speaking"
        );


        if (state) {

            voiceStatus.classList.add(
                state
            );

        }

    }


    function hideStatus() {

        if (!voiceStatus) {
            return;
        }


        voiceStatus.classList.remove(
            "show",
            "listening",
            "speaking"
        );

    }


    /* =====================================================
       VOICE BUTTON UI
    ===================================================== */

    function setListeningUI(
        listening
    ) {

        isListening =
            listening;


        if (listening) {

            voiceButton.classList.add(
                "listening"
            );


            voiceButton.textContent =
                "🔴";


            voiceButton.title =
                "Stop listening";


            voiceButton.setAttribute(
                "aria-label",
                "Stop listening"
            );


        } else {

            voiceButton.classList.remove(
                "listening"
            );


            voiceButton.textContent =
                "🎙️";


            voiceButton.title =
                "Talk to Iraa";


            voiceButton.setAttribute(
                "aria-label",
                "Talk to Iraa"
            );

        }

    }


    /* =====================================================
       START LISTENING
    ===================================================== */

    function startListening() {

        if (isListening) {
            return;
        }


        /*
         * Stop any speech that may currently
         * be playing before listening.
         */

        if (
            "speechSynthesis" in window
        ) {

            window.speechSynthesis.cancel();

        }


        finalTranscript =
            "";


        try {

            recognition.start();

        } catch (error) {

            console.error(
                "Iraa V1: Unable to start recognition:",
                error
            );

        }

    }


    /* =====================================================
       STOP LISTENING
    ===================================================== */

    function stopListening() {

        if (!isListening) {
            return;
        }


        try {

            recognition.stop();

        } catch (error) {

            console.error(
                "Iraa V1: Unable to stop recognition:",
                error
            );

        }

    }


    /* =====================================================
       MICROPHONE BUTTON
    ===================================================== */

    voiceButton.addEventListener(
        "click",
        () => {

            if (isListening) {

                stopListening();

            } else {

                startListening();

            }

        }
    );


    /* =====================================================
       RECOGNITION START
    ===================================================== */

    recognition.addEventListener(
        "start",
        () => {

            console.log(
                "Iraa V1: Listening started."
            );


            setListeningUI(
                true
            );


            showStatus(
                "Listening...",
                "listening"
            );

        }
    );


    /* =====================================================
       SPEECH RESULT
    ===================================================== */

    recognition.addEventListener(
        "result",
        event => {

            let interimTranscript =
                "";


            for (
                let i = event.resultIndex;
                i < event.results.length;
                i++
            ) {

                const result =
                    event.results[i];


                const transcript =
                    result[0].transcript;


                if (
                    result.isFinal
                ) {

                    finalTranscript +=
                        transcript;

                } else {

                    interimTranscript +=
                        transcript;

                }

            }


            /*
             * Show both final and interim text
             * inside the existing message input.
             */

            const combinedText =
                (
                    finalTranscript +
                    interimTranscript
                ).trim();


            if (combinedText) {

                messageInput.value =
                    combinedText;

            }

        }
    );


    /* =====================================================
       RECOGNITION END
    ===================================================== */

    recognition.addEventListener(
        "end",
        () => {

            console.log(
                "Iraa V1: Listening ended."
            );


            setListeningUI(
                false
            );


            const message =
                messageInput.value.trim();


            if (!message) {

                hideStatus();

                return;
            }


            /*
             * The existing app.js already owns
             * the Send button and /chat request.
             *
             * We simply trigger the existing
             * send flow.
             */

            showStatus(
                "Iraa is thinking..."
            );


            const sendButton =
                document.getElementById(
                    "send-btn"
                );


            if (sendButton) {

                setTimeout(
                    () => {

                        sendButton.click();

                    },
                    100
                );

            } else {

                console.error(
                    "Iraa V1: Send button not found."
                );


                hideStatus();

            }

        }
    );


    /* =====================================================
       RECOGNITION ERROR
    ===================================================== */

    recognition.addEventListener(
        "error",
        event => {

            console.error(
                "Iraa V1: Speech recognition error:",
                event.error
            );


            setListeningUI(
                false
            );


            let message =
                "I couldn't hear you.";


            switch (
                event.error
            ) {

                case "not-allowed":

                    message =
                        "Microphone permission was denied.";

                    break;


                case "no-speech":

                    message =
                        "I didn't hear anything.";

                    break;


                case "audio-capture":

                    message =
                        "I couldn't access your microphone.";

                    break;


                case "network":

                    message =
                        "Voice recognition needs a network connection.";

                    break;


                case "aborted":

                    /*
                     * User intentionally stopped listening.
                     */

                    hideStatus();

                    return;


                default:

                    message =
                        "Voice recognition couldn't start.";

            }


            showStatus(
                message
            );


            setTimeout(
                hideStatus,
                3000
            );

        }
    );


    /* =====================================================
       TEXT → SPEECH
       
       This is called by app.js:

       window.iraaSpeak(response)
    ===================================================== */

    let voiceEnabled =
        true;


    function speak(
        text
    ) {

        if (!voiceEnabled) {

            console.log(
                "Iraa V1: Voice output disabled."
            );

            return;
        }


        if (
            !("speechSynthesis" in window)
        ) {

            console.warn(
                "Iraa V1: Speech synthesis is not supported."
            );

            return;
        }


        if (!text) {
            return;
        }


        /*
         * Stop any previous speech.
         */

        window.speechSynthesis.cancel();


        /*
         * Remove common markdown symbols
         * so spoken responses sound cleaner.
         */

        const cleanText =
            String(text)
                .replace(
                    /[*_`#]/g,
                    ""
                )
                .replace(
                    /\[([^\]]+)\]\([^)]+\)/g,
                    "$1"
                )
                .trim();


        if (!cleanText) {
            return;
        }


        const utterance =
            new SpeechSynthesisUtterance(
                cleanText
            );


        /* =================================================
           VOICE SETTINGS
        ================================================== */

        utterance.lang =
            "en-IN";


        utterance.rate =
            0.95;


        utterance.pitch =
            1.0;


        utterance.volume =
            1.0;


        /* =================================================
           SPEECH START
        ================================================== */

        utterance.addEventListener(
            "start",
            () => {

                console.log(
                    "Iraa V1: Speaking."
                );


                showStatus(
                    "Iraa is speaking...",
                    "speaking"
                );

            }
        );


        /* =================================================
           SPEECH END
        ================================================== */

        utterance.addEventListener(
            "end",
            () => {

                console.log(
                    "Iraa V1: Finished speaking."
                );


                hideStatus();

            }
        );


        /* =================================================
           SPEECH ERROR
        ================================================= */

        utterance.addEventListener(
            "error",
            event => {

                console.error(
                    "Iraa V1: Speech synthesis error:",
                    event
                );


                hideStatus();

            }
        );


        /*
         * Start speaking.
         */

        window.speechSynthesis.speak(
            utterance
        );

    }


    /* =====================================================
       GLOBAL VOICE API
       
       app.js uses this function after Gemini
       returns Iraa's response.
    ===================================================== */

    window.iraaSpeak =
        speak;


    /* =====================================================
       VOICE ENABLE / DISABLE
       
       These functions will be useful later
       when we add a voice settings panel.
    ===================================================== */

    window.iraaVoiceEnabled =
        () => {

            return voiceEnabled;

        };


    window.iraaSetVoiceEnabled =
        enabled => {

            voiceEnabled =
                Boolean(enabled);


            if (!voiceEnabled) {

                if (
                    "speechSynthesis" in window
                ) {

                    window.speechSynthesis.cancel();

                }


                hideStatus();

            }

        };


    /* =====================================================
       STOP IRAA SPEAKING
       
       Useful for future "interrupt Iraa" functionality.
    ===================================================== */

    window.iraaStopSpeaking =
        () => {

            if (
                "speechSynthesis" in window
            ) {

                window.speechSynthesis.cancel();

            }


            hideStatus();

        };


    /* =====================================================
       READY
    ===================================================== */

    console.log(
        "Iraa V1: Voice Engine ready."
    );

})();