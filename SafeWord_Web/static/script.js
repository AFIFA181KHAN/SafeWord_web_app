let isListening = false;
let recognition;
let safeWord = "help";

// Initialize speech recognition
if ('webkitSpeechRecognition' in window) {
    recognition = new webkitSpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onresult = function(event) {
        const transcript = event.results[event.results.length - 1][0].transcript.trim().toLowerCase();
        console.log("You said: " + transcript);

        if (transcript.includes(safeWord.toLowerCase())) {
            triggerEmergency();
        }
    };

    recognition.onerror = function(event) {
        console.error("Speech recognition error: " + event.error);
    };
} else {
    alert("Speech recognition not supported in this browser.");
}

// Toggle listening
function toggleListening() {
    if (!isListening) {
        recognition.start();
        isListening = true;
        document.getElementById('listenButton').textContent = "Stop Listening";
        document.getElementById('status').textContent = "Status: Listening...";
    } else {
        recognition.stop();
        isListening = false;
        document.getElementById('listenButton').textContent = "Start Listening";
        document.getElementById('status').textContent = "Status: Not listening";
    }
}

// Set safe word
function setSafeWord() {
    safeWord = document.getElementById('safeWord').value;
    fetch('/set_safe_word', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ safe_word: safeWord }),
    })
    .then(response => response.json())
    .then(data => {
        console.log("Safe word set to: " + data.safe_word);
    });
}

// Trigger emergency
function triggerEmergency() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition((position) => {
            const location = `Lat: ${position.coords.latitude}, Long: ${position.coords.longitude}`;
            document.getElementById('location').textContent = "Location: " + location;

            fetch('/trigger_emergency', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ location: location }),
            })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
            });
        });
    } else {
        alert("Geolocation is not supported by this browser.");
    }
}