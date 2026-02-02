// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: Copyright 2026 Sam Blenny
"use strict";

const STATUS = document.querySelector('#status');   // Status span
const CONNECT = document.querySelector('#connect');  // Connect button
const CANVAS = document.querySelector('#canvas');   // Canvas

const CTX = CANVAS.getContext("2d", {willReadFrequently: true});

// Update status line span
function setStatus(s) {
    STATUS.textContent = s;
}

// Disconnect and stop updating the canvas
async function disconnect(status) {
    if (WEB_RTC) {
        // TODO: await disconnect
        WEB_RTC = null;
    }
    CONNECT.classList.remove('on');
    CONNECT.textContent = 'Connect';
    setStatus(status ? status : 'disconnected');
}

// Attempt to start virtual display with data feed over Web Serial
function connect() {
    // TODO: set up WebRTC connection
    // TODO: WEB_RTC = something
    // TODO: disconnect callback = ... { disconnect('connection lost'); }
    // TODO: connect callback = ... {
    //    // Update HTML button
    //    CONNECT.classList.add('on');
    //    CONNECT.textContent = 'disconnect';
    //    // Update status line
    //    setStatus('connected');
    //    // Begin doing WebRTC stuff
    //  })
    // .catch((err) => {
    //     WEB_RTC = null;
    //     setStatus('no serial port selected');
    // });
}

// Add on/off event handlers to the button
CONNECT.addEventListener('click', function() {
    if(CONNECT.classList.contains('on')) {
        disconnect();
    } else {
        connect();
    }
});

setStatus("ready");
