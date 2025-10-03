#!/usr/bin/env python3
"""
Simple HTTP server to serve the video comparison app locally.
Run this script and then open http://localhost:8000 in your browser.
"""

import http.server
import socketserver
import os
import sys

# Change to the directory containing this script
os.chdir(os.path.dirname(os.path.abspath(__file__)))

PORT = 8000

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers to allow local file access
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def log_message(self, format, *args):
        # Custom log format
        print(f"[{self.log_date_time_string()}] {format % args}")

if __name__ == "__main__":
    try:
        with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
            print(f"Starting server at http://localhost:{PORT}")
            print(f"Serving files from: {os.getcwd()}")
            print("Press Ctrl+C to stop the server")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except OSError as e:
        if e.errno == 10048:  # Port already in use on Windows
            print(f"Port {PORT} is already in use. Try a different port or close other applications using this port.")
        else:
            print(f"Error starting server: {e}")
        sys.exit(1)