# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2026 Sam Blenny
"""
WebRTC Mock Signaling Server

Simple HTTP server that handles WebRTC signaling for prototyping.
Returns hardcoded SDP answer and mock connectivity candidates.
"""

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

# Hardcoded mock SDP answer. SDP (Session Description Protocol) is a
# standard format describing what the "server" side can send/receive: codecs,
# ports, media types, and capabilities. This answer describes VP8 video on
# port 5000. In WebRTC handshake, browser sends an offer first, and server
# responds with this answer to complete negotiation. Note: This mock answer
# uses dummy/fake values for DTLS fingerprint, candidate authentication
# since we're not doing actual media exchange yet. RTCP-MUX enables
# multiplexing RTP and RTCP control traffic on the same UDP port, reducing
# port usage and complexity. GStreamer server must be configured to support
# this when it's implemented.
MOCK_ANSWER = {
    "type": "answer",
    "sdp": "v=0\r\n"
           "o=mock 0 0 IN IP4 0.0.0.0\r\n"
           "s=-\r\n"
           "t=0 0\r\n"
           "a=extmap-allow-mixed\r\n"
           "a=msid-semantic: WMS\r\n"
           "m=video 5000 RTP/SAVPF 96\r\n"
           "a=rtpmap:96 VP8/90000\r\n"
           "a=fmtp:96 x-google-start-bitrate=1000\r\n"
           "a=ice-ufrag:mockufrag1234567890ab\r\n"
           "a=ice-pwd:mockpwdmockpwdmockpwdmockpwd\r\n"
           "a=fingerprint:sha-256 "
           "00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:"
           "00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00\r\n"
           "a=setup:passive\r\n"
           "a=mid:0\r\n"
           "a=rtcp-mux\r\n"
           "a=rtpmap:96 VP8/90000\r\n"
           "a=sendonly\r\n"
}

# Hardcoded mock connectivity candidates. Candidates are possible addresses
# where each peer can receive packets. Each candidate includes: the address
# (IP), port, protocol (UDP), and type (host/reflexive/relay). The browser
# will test these candidates to find which ones have working connectivity and
# can exchange media. These mocks use localhost for testing on the same machine.
MOCK_CANDIDATES = [
    {
        "candidate": "candidate:1 1 udp 2130706431 127.0.0.1 5000 typ host",
        "sdpMid": "video",
        "sdpMLineIndex": 0
    }
]


class SignalingHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler for WebRTC signaling.
    Handles POST /offer, GET /peer-candidate, POST /peer-candidate.
    """

    ALLOWED_ORIGINS = [
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'https://samblenny.github.io'
    ]

    def _get_cors_origin(self):
        """Return the Origin header if it's in allowed list, else None."""
        origin = self.headers.get('Origin', '')
        if origin in self.ALLOWED_ORIGINS:
            return origin
        return None

    def do_OPTIONS(self):
        """Handle OPTIONS preflight requests (required for CORS)."""
        origin = self._get_cors_origin()
        self.send_response(200)
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        """Handle POST requests (SDP offer, candidates from browser)."""
        try:
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)

            if self.path == '/offer':
                self._handle_offer(data)
            elif self.path == '/peer-candidate':
                self._handle_peer_candidate(data)
            else:
                self._send_error(404, 'Not Found')

        except json.JSONDecodeError as e:
            print(f'[Server] JSON parse error: {e}', file=sys.stderr)
            self._send_error(400, 'Malformed JSON')
        except Exception as e:
            print(f'[Server] Unexpected error in do_POST: {e}',
                  file=sys.stderr)
            self._send_error(500, 'Internal Server Error')

    def do_GET(self):
        """Handle GET requests (fetch candidates)."""
        try:
            if self.path == '/peer-candidate':
                self._handle_get_candidates()
            else:
                self._send_error(404, 'Not Found')

        except Exception as e:
            print(f'[Server] Unexpected error in do_GET: {e}',
                  file=sys.stderr)
            self._send_error(500, 'Internal Server Error')

    def _handle_offer(self, offer):
        """
        Handle SDP offer from browser.
        Log the offer (for debugging) and return hardcoded answer.
        """
        print(f'[Server] Received SDP offer')
        self._send_json(MOCK_ANSWER)

    def _handle_peer_candidate(self, candidate):
        """
        Handle connectivity candidate from browser.
        Log it (for debugging) and discard it.
        """
        cand_str = candidate.get('candidate', '')
        if cand_str == '':
            print(f'[Server] Received end-of-candidates marker')
        else:
            print(f'[Server] Received connectivity candidate from browser')

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        origin = self._get_cors_origin()
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'{}')

    def _handle_get_candidates(self):
        """Handle GET request for candidates."""
        print(f'[Server] Browser fetching connectivity candidates')
        self._send_json(MOCK_CANDIDATES)

    def _send_json(self, data):
        """Send JSON response with proper headers."""
        body = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        origin = self._get_cors_origin()
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status, message):
        """Send error response."""
        error_data = {"error": message}
        body = json.dumps(error_data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        origin = self._get_cors_origin()
        if origin:
            self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass


def main():
    """Start the mock signaling server."""
    host = '0.0.0.0'
    port = 8080

    server = HTTPServer((host, port), SignalingHandler)
    print(f'[Server] Starting WebRTC mock signaling server on {host}:{port}')
    print(f'[Server] Endpoints:')
    print(f'[Server]   POST /offer -> returns hardcoded answer')
    print(f'[Server]   POST /peer-candidate -> logs candidate')
    print(f'[Server]   GET /peer-candidate -> returns mock candidates')
    print(f'[Server] Press Ctrl+C to stop')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f'\n[Server] Shutting down')
        server.shutdown()


if __name__ == '__main__':
    main()
