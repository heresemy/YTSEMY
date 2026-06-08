from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import re
import requests
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)

def is_youtube_url(url):
    """Check if URL is a valid YouTube URL"""
    youtube_regex = r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/'
    return re.match(youtube_regex, url) is not None

def get_video_info(url):
    """Extract video information using yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'success': True,
                'title': info.get('title', 'Unknown'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': format_duration(info.get('duration', 0)),
                'channel': info.get('uploader', 'Unknown'),
                'views': info.get('view_count', 'N/A'),
                'formats': get_available_formats(info)
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def format_duration(seconds):
    """Convert seconds to HH:MM:SS format"""
    if not seconds:
        return "00:00"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"

def get_available_formats(info):
    """Extract video and audio formats from video info"""
    video_formats = []
    audio_formats = []
    
    seen_qualities = set()
    
    for f in info.get('formats', []):
        # Video formats (with both video and audio)
        if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
            quality = f.get('height', 0)
            if quality and quality not in seen_qualities:
                seen_qualities.add(quality)
                video_formats.append({
                    'quality': f"{quality}p",
                    'extension': 'MP4',
                    'size': format_size(f.get('filesize', 0)),
                    'format_id': f.get('format_id', ''),
                    'resolution': f"{f.get('width', 0)}x{quality}"
                })
        
        # Audio formats
        elif f.get('acodec') != 'none' and f.get('vcodec') == 'none':
            bitrate = f.get('abr', 128)
            audio_formats.append({
                'quality': f"{int(bitrate)}K",
                'extension': 'M4A' if 'm4a' in f.get('ext', '') else 'MP3',
                'size': format_size(f.get('filesize', 0)),
                'format_id': f.get('format_id', '')
            })
    
    # Sort video qualities descending
    video_formats.sort(key=lambda x: int(x['quality'].replace('p', '')), reverse=True)
    
    # Remove duplicates from audio
    seen_audio = set()
    unique_audio = []
    for a in audio_formats:
        if a['quality'] not in seen_audio:
            seen_audio.add(a['quality'])
            unique_audio.append(a)
    audio_formats = unique_audio
    
    return {'video': video_formats, 'audio': audio_formats}

def format_size(bytes_size):
    """Convert bytes to human readable format"""
    if not bytes_size:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} GB"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/info', methods=['POST'])
def get_info():
    """API endpoint to get video information"""
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'success': False, 'error': 'Please provide a URL'})
    
    if not is_youtube_url(url):
        return jsonify({'success': False, 'error': 'Only YouTube URLs are supported!'})
    
    result = get_video_info(url)
    return jsonify(result)

@app.route('/api/download', methods=['POST'])
def download():
    """Download video or audio"""
    data = request.get_json()
    url = data.get('url', '').strip()
    format_id = data.get('format_id', '')
    type_ = data.get('type', 'video')  # 'video' or 'audio'
    
    if not url or not format_id:
        return jsonify({'success': False, 'error': 'Missing parameters'})
    
    ydl_opts = {
        'format': format_id,
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            
            # Send file for download
            return send_file(
                file_path,
                as_attachment=True,
                download_name=f"{info['title']}.{info['ext']}"
            )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    os.makedirs('downloads', exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)