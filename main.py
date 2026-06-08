import requests
from flask import Flask, render_template, request, jsonify, Response

app = Flask(__name__)

API_BASE_URL = "https://youtube-video-download.unaux.com/"

def is_youtube_url(url):
    import re
    return bool(re.search(r'(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)', url))

def fetch_video_info(youtube_url):
    try:
        resp = requests.get(API_BASE_URL, params={"url": youtube_url}, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            return {"success": False, "error": data.get("error", "API error")}

        video = data.get("video", {})
        formats = data.get("formats", {})

        # Transform to match frontend expectation
        return {
            "success": True,
            "title": video.get("title", "Unknown"),
            "thumbnail": video.get("thumbnail"),
            "duration": video.get("duration", "00:00"),
            "channel": video.get("channel", "Unknown"),
            "views": video.get("views", "N/A"),
            "formats": {
                "video": [
                    {
                        "quality": f.get("quality"),
                        "size": f.get("size"),
                        "extension": f.get("extension"),
                        "format_id": f.get("downloadUrl")   # direct download link
                    }
                    for f in formats.get("video", [])
                ],
                "audio": [
                    {
                        "quality": f.get("quality"),
                        "size": f.get("size"),
                        "extension": f.get("extension"),
                        "format_id": f.get("downloadUrl")
                    }
                    for f in formats.get("audio", [])
                ]
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({"success": False, "error": "No URL provided"})
    if not is_youtube_url(url):
        return jsonify({"success": False, "error": "Only YouTube links are supported"})
    result = fetch_video_info(url)
    return jsonify(result)

@app.route('/api/download', methods=['POST'])
def download():
    """
    Frontend sends { url, format_id, type }
    format_id is the direct download URL from the external API.
    We proxy the download so the frontend gets a blob (same as before).
    """
    data = request.get_json()
    download_url = data.get('format_id')
    if not download_url:
        return jsonify({"success": False, "error": "No download link"}), 400

    # Fetch the file from external API and stream to client
    try:
        resp = requests.get(download_url, stream=True, timeout=60)
        resp.raise_for_status()
        # Extract filename from Content-Disposition if present
        content_disposition = resp.headers.get('Content-Disposition')
        filename = "download.mp4"
        if content_disposition and 'filename=' in content_disposition:
            import re
            match = re.search(r'filename="?([^";]+)"?', content_disposition)
            if match:
                filename = match.group(1)
        return Response(
            resp.iter_content(chunk_size=8192),
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': resp.headers.get('Content-Type', 'application/octet-stream')
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
