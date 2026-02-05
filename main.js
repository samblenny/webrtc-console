// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: Copyright 2026 Sam Blenny
"use strict";

const STATUS = document.querySelector('#status');
const CONNECT = document.querySelector('#connect');
const VIDEO = document.querySelector('#video');
const SERVER_URL = document.querySelector('#serverUrl');

let WEB_RTC = null;

// Update status line span
function setStatus(s) {
    STATUS.textContent = s;
}

// Disconnect and stop updating the video
async function disconnect(status) {
    if (WEB_RTC) {
        // TODO: proper WebRTC cleanup
        WEB_RTC = null;
    }
    CONNECT.classList.remove('on');
    CONNECT.textContent = 'Connect';
    setStatus(status ? status : 'disconnected');
}

// Attempt to establish WebRTC connection to gstreamer server
async function connect() {
    const url = SERVER_URL.value.trim();

    if (!url) {
        setStatus('error: no server URL');
        return;
    }

    setStatus('connecting...');

    try {
        // Step 1: Create RTCPeerConnection for media exchange.
        // RTCPeerConnection manages the entire WebRTC connection lifecycle
        // including SDP negotiation, candidate gathering/exchange, and
        // media stream handling.
        const peerConnection = new RTCPeerConnection();
        WEB_RTC = peerConnection;
        console.log('[WebRTC] Created RTCPeerConnection');

        // Step 1b: Add video transceiver to announce browser can receive video.
        // This makes the browser include a video m-line in its offer with
        // a=recvonly direction. The server will answer with a=sendonly,
        // allowing both sides to negotiate candidates for the video stream.
        peerConnection.addTransceiver('video', {send: false, recv: true});
        console.log('[WebRTC] Added video transceiver (recv only)');

        // Step 2: Set up candidate handler. When candidates are discovered,
        // we POST each one to the server (trickle method).
        peerConnection.onicecandidate = (event) => {
            if (event.candidate !== null) {
                // Browser generated a candidate with its address and port.
                // POST it to server so server knows where to send packets.
                console.log('[WebRTC] Generated connectivity candidate');
                const candidate = {
                    candidate: event.candidate.candidate,
                    sdpMid: event.candidate.sdpMid,
                    sdpMLineIndex: event.candidate.sdpMLineIndex
                };
                fetch(url + '/peer-candidate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(candidate)
                }).catch(e => {
                    console.error('[WebRTC] Failed to POST candidate:', e);
                });
            } else {
                // event.candidate === null signals end of candidate gathering.
                // POST empty candidate marker to tell server we're done.
                console.log('[WebRTC] Candidate gathering complete');
                fetch(url + '/peer-candidate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({candidate: ''})
                }).catch(e => {
                    console.error(
                        '[WebRTC] Failed to POST end-of-candidates:', e);
                });
            }
        };
        console.log('[WebRTC] Set up candidate handler');

        // Step 3: Set up handler for remote video track from server.
        // When server sends VP8 video via RTP, ontrack fires with the incoming
        // media stream. We attach it to the video element for display.
        peerConnection.ontrack = (event) => {
            console.log('[WebRTC] Received remote track, attaching to video');
            VIDEO.srcObject = event.streams[0];
        };
        console.log('[WebRTC] Set up ontrack handler');

        // Step 4: Set up connection state listener for debugging.
        // connectionState transitions through: new → connecting → connected →
        // (or failed/disconnected). This helps us know when connection is ready.
        peerConnection.addEventListener('connectionstatechange',
            (event) => {
            console.log('[WebRTC] Connection state:',
                peerConnection.connectionState);
            if (peerConnection.connectionState === 'connected') {
                console.log('[WebRTC] Connected! Waiting for video track...');
            } else if (peerConnection.connectionState === 'failed') {
                console.log('[WebRTC] Connection failed');
            }
        });
        console.log('[WebRTC] Set up connectionstatechange listener');

        // Step 5: Generate SDP offer describing what browser can send/receive.
        // SDP (Session Description Protocol) is a standard format for describing
        // media capabilities, codecs, and network parameters.
        const offer = await peerConnection.createOffer();
        console.log('[WebRTC] Generated SDP offer');

        // Step 6: Set offer as local description. This tells RTCPeerConnection
        // that we're committing to this offer and starts candidate
        // gathering.
        await peerConnection.setLocalDescription(offer);
        console.log('[WebRTC] Set local description with offer');

        // Step 7: Send offer to server via HTTP POST to /offer endpoint.
        // Server will process it and respond with SDP answer describing what it
        // is sending (codecs, ports, etc.).
        const offerResponse = await fetch(url + '/offer', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(offer)
        });
        const answer = await offerResponse.json();
        console.log('[WebRTC] Received SDP answer from server');

        // Step 8: Set answer as remote description. This tells RTCPeerConnection
        // what the remote peer (server) is sending and completes SDP
        // negotiation. After this, candidate gathering and testing begins.
        await peerConnection.setRemoteDescription(answer);
        console.log('[WebRTC] Set remote description with answer');

        // Step 9: Fetch candidates from server (single attempt). Candidates
        // candidates tell each peer where the other one is listening. We make
        // one GET request to fetch all remote candidates the server has ready.
        const candidateResponse = await fetch(url + '/peer-candidate', {
            method: 'GET'
        });
        const candidates = await candidateResponse.json();
        console.log('[WebRTC] Received ' + candidates.length +
            ' remote candidates');

        // Step 10: Add each remote candidate to RTCPeerConnection. These are
        // possible addresses where the server is listening for RTP packets.
        // addIceCandidate can fail for individual candidates (they provide
        // redundancy), so we wrap each in try/catch but don't abort on failure.
        for (const candidate of candidates) {
            try {
                await peerConnection.addIceCandidate(candidate);
            } catch (error) {
                console.log('[WebRTC] Failed to add candidate:', error);
            }
        }
        console.log('[WebRTC] Added all remote candidates');

        // Connection setup complete. Update UI and wait for video track.
        CONNECT.classList.add('on');
        CONNECT.textContent = 'Disconnect';
        setStatus('connected');
        console.log('[WebRTC] Connection setup complete, waiting for video...');

    } catch (error) {
        console.error('[WebRTC] Connection failed:', error);
        setStatus('connection failed: ' + error.message);
        WEB_RTC = null;
    }
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
