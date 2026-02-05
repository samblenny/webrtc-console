"""
Localhost tunnel for WebRTC-style workloads (HTTP + RTP/UDP).

Chrome on macOS currently blocks direct connections to private IP addresses
(192.168.x.x, 10.x.x.x). It's not clear if this will get fixed in the
future, but for now it requires a workaround. This tunnel allows a
browser-based WebRTC client on macOS to reach a WebRTC server on a private
network by forwarding traffic through localhost, which Chrome treats as a
secure origin. The tunnel handles both TCP signaling (HTTP/SDP) and UDP
media (RTP/RTCP) simultaneously in a single asyncio event loop.

Design requirements
-------------------
- Everything must appear as localhost to browser (Chrome secure-origin rules)
- No Homebrew or third-party dependencies
- One user action to start (single process, no multiple terminals)
- Low latency for RTP (VP8 video, Opus audio)
- Fixed peers, fixed ports, no NAT traversal
- Signaling over HTTP/WebSocket (TCP)
- Media + inputs over UDP

Strategy
--------
- Run a single asyncio event loop
- Bind TCP and UDP sockets on 127.0.0.1
- Forward bytes immediately to a fixed local server address
- No parsing, no buffering beyond the kernel socket buffers
- One asyncio Task per forwarded port

This is *not* a general tunnel or VPN.
It is explicit port forwarding optimized for LAN WebRTC dev.

Usage:
  python3 rtc-tunnel.py <server>

Examples:
  python3 rtc-tunnel.py BeagleBoard.local
  python3 rtc-tunnel.py 192.168.2.2
"""

import asyncio
import socket
import sys

# -------------------------
# Configuration
# -------------------------

# TCP signaling (HTTP)
HTTP_PORT = 8080

# UDP media (RTP/RTCP)
RTP_PORT = 5004

# UDP data channel (inputs, control, etc.)
DATA_PORT = 6000


# -------------------------
# TCP forwarding
# -------------------------

async def tcp_pipe(reader, writer):
    # Copy data from reader to writer until EOF.
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def handle_tcp_client(client_reader, client_writer, remote_addr):
    # Accept a client connection, establish connection to remote, then
    # forward bytes bidirectionally between them.
    try:
        remote_reader, remote_writer = await asyncio.open_connection(
            remote_addr[0], remote_addr[1]
        )

        await asyncio.gather(
            tcp_pipe(client_reader, remote_writer),
            tcp_pipe(remote_reader, client_writer),
        )
    except Exception:
        client_writer.close()


async def start_tcp_forward(local_port, remote_host, remote_port):
    # Listen on localhost:local_port and forward connections to
    # remote_host:remote_port.
    server = await asyncio.start_server(
        lambda r, w: handle_tcp_client(r, w, (remote_host, remote_port)),
        host="127.0.0.1",
        port=local_port,
    )

    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    print(f"[TCP] forwarding {addrs} -> {remote_host}:{remote_port}")

    async with server:
        await server.serve_forever()


# -------------------------
# Bidirectional UDP proxy (robust for ephemeral ports)
# -------------------------

class UDPProxy:
    # Bidirectional UDP proxy: localhost:local_port <-> remote_host:remote_port
    #
    # Packet routing rules:
    # - From remote (remote_host:remote_port) → forward to localhost
    # - From localhost (any source port) → forward to remote
    # - All other packets (stray / scans) are dropped silently

    def __init__(self, local_port, remote_host, remote_port):
        self.local_port = local_port
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.remote_addr = (remote_host, remote_port)
        self.local_transport = None
        self.remote_transport = None

    async def start(self):
        loop = asyncio.get_running_loop()

        # Local socket (receives from browser)
        local_transport, local_proto = (
            await loop.create_datagram_endpoint(
                lambda: LocalUDPProtocol(self),
                local_addr=("127.0.0.1", self.local_port),
            )
        )
        self.local_transport = local_transport

        # Remote socket (sends to server)
        remote_transport, remote_proto = (
            await loop.create_datagram_endpoint(
                lambda: RemoteUDPProtocol(self),
                remote_addr=self.remote_addr,
            )
        )
        self.remote_transport = remote_transport

        print(
            f"[UDP] proxy localhost:{self.local_port} <-> "
            f"{self.remote_host}:{self.remote_port}"
        )

        # Keep running indefinitely
        await asyncio.sleep(float('inf'))


class LocalUDPProtocol(asyncio.DatagramProtocol):
    # Receives packets from browser on localhost, forwards to remote

    def __init__(self, proxy):
        self.proxy = proxy

    def datagram_received(self, data, addr):
        # Only forward packets from localhost
        if addr[0] == "127.0.0.1":
            self.proxy.remote_transport.sendto(data, self.proxy.remote_addr)


class RemoteUDPProtocol(asyncio.DatagramProtocol):
    # Receives packets from remote server, forwards to localhost

    def __init__(self, proxy):
        self.proxy = proxy

    def datagram_received(self, data, addr):
        # Only forward packets from the configured remote address
        if addr == self.proxy.remote_addr:
            self.proxy.local_transport.sendto(
                data, ("127.0.0.1", self.proxy.local_port)
            )


# -------------------------
# Main
# -------------------------

async def main(server_hostname):
    tasks = [
        # TCP signaling (HTTP)
        asyncio.create_task(
            start_tcp_forward(HTTP_PORT, server_hostname, HTTP_PORT)
        ),

        # UDP media (RTP/RTCP)
        asyncio.create_task(
            UDPProxy(RTP_PORT, server_hostname, RTP_PORT).start()
        ),

        # UDP data channel (inputs, control, etc.)
        asyncio.create_task(
            UDPProxy(DATA_PORT, server_hostname, DATA_PORT).start()
        ),
    ]

    print("Tunnel active.")
    print(f"  HTTP  -> http://localhost:{HTTP_PORT}")
    print(f"  RTP   -> udp://localhost:{RTP_PORT}")
    print(f"  DATA  -> udp://localhost:{DATA_PORT}")

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 rtc-tunnel.py <server>")
        print("  <server> can be BeagleBoard.local, 192.168.2.2, etc.")
        sys.exit(1)

    server_hostname = sys.argv[1]

    try:
        asyncio.run(main(server_hostname))
    except KeyboardInterrupt:
        print("\nShutting down.")
