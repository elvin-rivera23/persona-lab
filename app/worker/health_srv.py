# app/worker/health_srv.py
# Tiny HTTP server exposing /health on 0.0.0.0:8022
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8022


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    # Be quiet in logs (avoid noisy 200 lines)
    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Worker health server listening on :{PORT}")
    server.serve_forever()
