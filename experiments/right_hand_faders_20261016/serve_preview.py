"""Serve the standalone local preview. No board or serial connection."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from functools import partial
from pathlib import Path

if __name__=='__main__':
    directory=Path(__file__).resolve().parent/'preview'
    address=('127.0.0.1',8766)
    print('Right-hand fader preview: http://127.0.0.1:8766/ (Ctrl+C to stop)',flush=True)
    with ThreadingHTTPServer(address,partial(SimpleHTTPRequestHandler,directory=str(directory))) as server:
        server.serve_forever()
