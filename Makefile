# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright 2026 Sam Blenny
.PHONY: server

# Start an HTTP server serving files in current directory on http://localhost
# (a secure context) so Chrome will let us use APIs that need secure origin
server:
	python3 -m http.server --bind 127.0.0.1
