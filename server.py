#!/usr/bin/env python3
"""
Simple HTTP server to serve the video comparison app locally.
Run this script and then open http://localhost:8000 in your browser.
"""

import http.server
import socketserver
import os
import sys
import json
import urllib.parse
import time
import re
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, environment variables must be set manually
    pass

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
    
    def do_OPTIONS(self):
        """Handle OPTIONS request for CORS preflight"""
        self.send_response(200)
        self.end_headers()
    
    def do_POST(self):
        """Handle POST requests for video generation"""
        if self.path == '/api/generate-videos':
            self.handle_generate_videos()
        else:
            self.send_error(404, "Endpoint not found")
    
    def handle_generate_videos(self):
        """Handle video generation request"""
        try:
            # Read the request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            prompt = data.get('prompt', '').strip()
            if not prompt:
                self.send_error(400, "Prompt is required")
                return
            
            # Generate videos using Azure OpenAI
            result = self.generate_video_pair(prompt)
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))
            
        except Exception as e:
            print(f"Error generating videos: {e}")
            self.send_error(500, f"Error generating videos: {str(e)}")
    
    def generate_video_pair(self, prompt):
        """Generate video pair using Azure OpenAI Sora models"""
        try:
            # Import Azure OpenAI SDK
            from openai import AzureOpenAI
            import requests
            
            # Get environment variables
            azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
            api_key = os.getenv('AZURE_OPENAI_API_KEY')
            api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-08-01-preview')
            sora1_deployment = os.getenv('SORA1_DEPLOYMENT_NAME', 'sora-1')
            sora2_deployment = os.getenv('SORA2_DEPLOYMENT_NAME', 'sora-2')
            
            if not azure_endpoint or not api_key:
                raise Exception("Azure OpenAI credentials not configured. Please set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY environment variables.")
            
            # Create sanitized filename from prompt
            safe_filename = re.sub(r'[^\w]', '_', prompt)
            safe_filename = safe_filename[:50]  # Limit length
            
            # Create directories if they don't exist
            Path('Model1').mkdir(exist_ok=True)
            Path('Model2').mkdir(exist_ok=True)
            
            # Initialize Azure OpenAI client
            client = AzureOpenAI(
                api_version=api_version,
                azure_endpoint=azure_endpoint,
                api_key=api_key
            )
            
            # Generate video with Sora 1
            print(f"Generating video with Sora 1 for prompt: {prompt}")
            sora1_path = self.generate_single_video(client, sora1_deployment, prompt, safe_filename, 'Sora1', 'Model1')
            
            # Generate video with Sora 2
            print(f"Generating video with Sora 2 for prompt: {prompt}")
            sora2_path = self.generate_single_video(client, sora2_deployment, prompt, safe_filename, 'Sora2', 'Model2')
            
            # Add to videos.json
            self.add_to_videos_json(prompt, sora1_path, sora2_path)
            
            return {
                'success': True,
                'prompt': prompt,
                'model1_path': sora1_path,
                'model2_path': sora2_path
            }
            
        except ImportError:
            raise Exception("Azure OpenAI SDK not installed. Please install it with: pip install openai")
        except Exception as e:
            raise Exception(f"Failed to generate videos: {str(e)}")
    
    def generate_single_video(self, client, deployment_name, prompt, safe_filename, model_prefix, directory):
        """Generate a single video using Azure OpenAI"""
        import requests
        
        # Call Azure OpenAI to generate video
        response = client.videos.generate(
            model=deployment_name,
            prompt=prompt
        )
        
        # Get the video URL from response with proper error handling
        video_url = None
        if hasattr(response, 'data') and len(response.data) > 0:
            video_url = response.data[0].url
        elif hasattr(response, 'url'):
            video_url = response.url
        else:
            raise Exception("No video URL in response from Azure OpenAI")
        
        # Validate URL is from Azure
        parsed_url = urllib.parse.urlparse(video_url)
        if not parsed_url.hostname or not parsed_url.hostname.endswith('.azure.com'):
            raise Exception(f"Untrusted video URL: {parsed_url.hostname}")
        
        # Download the video with timeout
        video_filename = f"{model_prefix}_{safe_filename}.mp4"
        video_path = os.path.join(directory, video_filename)
        
        video_response = requests.get(video_url, timeout=300)  # 5 minute timeout for video download
        video_response.raise_for_status()
        
        with open(video_path, 'wb') as f:
            f.write(video_response.content)
        
        print(f"Video saved to: {video_path}")
        return video_path
    
    def add_to_videos_json(self, prompt, model1_path, model2_path):
        """Add new video pair to videos.json"""
        videos_file = 'videos.json'
        
        # Read existing videos
        try:
            with open(videos_file, 'r') as f:
                videos = json.load(f)
        except FileNotFoundError:
            videos = []
        
        # Add new video pair
        new_pair = {
            'model1_path': model1_path,
            'model2_path': model2_path,
            'prompt': prompt
        }
        videos.append(new_pair)
        
        # Write back to file
        with open(videos_file, 'w') as f:
            json.dump(videos, f, indent=2)
        
        print(f"Added new video pair to {videos_file}")

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