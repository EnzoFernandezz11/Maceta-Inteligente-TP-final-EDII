import asyncio
import functools
import http.server
import os
import threading

import websockets

from .ws_server import make_handler, queue_listener, stop_connection_sync

WS_HOST   = "localhost"
WS_PORT   = 8765
HTTP_PORT = 8080


class _HTTPServer(http.server.HTTPServer):
    allow_reuse_address = True


def start_http_server():
    directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')
    handler   = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    handler.log_message = lambda *args: None
    httpd = _HTTPServer(("localhost", HTTP_PORT), handler)
    print(f"Serving dashboard on http://localhost:{HTTP_PORT}/")
    httpd.serve_forever()


async def main():
    data_queue = asyncio.Queue()

    threading.Thread(target=start_http_server, daemon=True).start()

    asyncio.create_task(queue_listener(data_queue))

    print(f"Starting WebSocket server on ws://{WS_HOST}:{WS_PORT}...")
    async with websockets.serve(make_handler(data_queue), WS_HOST, WS_PORT, reuse_address=True):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_connection_sync()
