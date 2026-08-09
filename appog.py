# app.py
import os
import threading
import queue
import uuid
from urllib.parse import urlparse

from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from yt_dlp import YoutubeDL

app = Flask(__name__, template_folder="templates", static_folder="static")

BASE_DIR = os.path.dirname(__file__)
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Default cookie file path (adjust if your cookies.txt is elsewhere)
DEFAULT_COOKIE_FILE = os.path.join(BASE_DIR, "cookies.txt")
ALLOWED_COOKIE_EXTS = {'.txt', '.cookies'}

tasks = {}
task_queue = queue.Queue()


def is_youtube_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return 'youtube.com' in host or 'youtu.be' in host or 'm.youtube.com' in host


def worker():
    while True:
        task_id = task_queue.get()
        if task_id is None:
            break
        task = tasks.get(task_id)
        if not task:
            task_queue.task_done()
            continue
        try:
            task['status'] = 'processing'
            if task['mode'] == 'single':
                _download_single(task_id, task)
            elif task['mode'] == 'playlist':
                _download_playlist(task_id, task)
            if task.get('status') not in ('error',):
                task['status'] = 'done'
        except Exception as e:
            task['status'] = 'error'
            task['error'] = str(e)
        finally:
            task_queue.task_done()


threading.Thread(target=worker, daemon=True).start()


def _attempt_download(ydl_opts, url):
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True, None
    except Exception as e:
        return False, e


def _common_opts(outtmpl):
    """Options from yt-dlp.conf applied here"""
    return {
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
        'nopart': True,                        # --no-part
        'restrictfilenames': True,             # --restrict-filenames
        'concurrent_fragment_downloads': 10,   # -N 10
        'http_chunk_size': 10485760,           # --http-chunk-size 10M
        'fragment_retries': 20,
        'continuedl': True,
        'retries': 20,
    }


def _apply_cookies_if_any(ydl_opts, task):
    cookiefile = task.get('cookiefile_path')
    if cookiefile and os.path.exists(cookiefile):
        ydl_opts['cookiefile'] = cookiefile
        print(f"[DEBUG] Using uploaded cookie file: {cookiefile}")
    elif os.path.exists(DEFAULT_COOKIE_FILE):
        ydl_opts['cookiefile'] = DEFAULT_COOKIE_FILE
        print(f"[DEBUG] Using default cookie file: {DEFAULT_COOKIE_FILE}")
    else:
        print("[DEBUG] No cookie file provided or found")


def _download_single(task_id, task):
    url = task['url']
    is_yt = is_youtube_url(url)
    outtmpl = os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s')

    ydl_opts = {
        **_common_opts(outtmpl),
        'noplaylist': True,
        'writesubtitles': True,
        'subtitleslangs': ['en'],
        'convertsubtitles': 'srt',
        'embedsubtitles': True,
        'writethumbnail': True,
        'merge_output_format': 'mkv',   # final output in MKV
        'postprocessors': [
            {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mkv'},
            {'key': 'FFmpegMetadata'},
            {'key': 'EmbedThumbnail'},   # embed thumbnail into MKV
        ],
    }

    if is_yt:
        ydl_opts.update({
            'format': (
                'bestvideo[height<=720]+bestaudio/best[height<=720]'
            )
        })
    else:
        ydl_opts.update({'format': 'bestvideo+bestaudio/best'})

    _apply_cookies_if_any(ydl_opts, task)

    success, exc = _attempt_download(ydl_opts, url)
    if not success:
        task['status'] = 'error'
        task['error'] = str(exc)


def _download_playlist(task_id, task):
    url = task['url']
    is_yt = is_youtube_url(url)
    outtmpl = os.path.join(DOWNLOAD_DIR, '%(playlist_index)03d - %(title)s.%(ext)s')

    ydl_opts = {
        **_common_opts(outtmpl),
        'noplaylist': False,
        'writesubtitles': True,
        'subtitleslangs': ['en'],
        'convertsubtitles': 'srt',
        'embedsubtitles': True,
        'writethumbnail': True,
        'merge_output_format': 'mkv',
        'postprocessors': [
            {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mkv'},
            {'key': 'FFmpegMetadata'},
            {'key': 'EmbedThumbnail'},
        ],
    }

    if is_yt:
        ydl_opts.update({
            'format': (
                'bestvideo[height<=720]+bestaudio/best[height<=720]'
            )
        })
    else:
        ydl_opts.update({'format': 'bestvideo+bestaudio/best'})

    _apply_cookies_if_any(ydl_opts, task)

    success, exc = _attempt_download(ydl_opts, url)
    if not success:
        task['status'] = 'error'
        task['error'] = str(exc)


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/start_download", methods=["POST"])
def start_download():
    data = request.get_json() if request.is_json else request.form
    url = (data.get("url") or "").strip()
    mode = data.get("mode", "single")

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    saved_cookie_path = None
    if 'cookiefile' in request.files:
        cookiefile = request.files.get("cookiefile")
        if cookiefile and cookiefile.filename:
            filename = secure_filename(cookiefile.filename)
            _, ext = os.path.splitext(filename)
            if ext.lower() not in ALLOWED_COOKIE_EXTS:
                return jsonify({"error": "Unsupported cookie file extension"}), 400
            saved_cookie_name = f"cookies_{uuid.uuid4().hex}.txt"
            saved_cookie_path = os.path.join(DOWNLOAD_DIR, saved_cookie_name)
            cookiefile.save(saved_cookie_path)

    task_id = str(uuid.uuid4())
    task = {
        'id': task_id,
        'url': url,
        'mode': mode,
        'cookiefile_path': saved_cookie_path,
        'status': 'queued',
        'progress': {'status': 'queued'},
        'files': []
    }
    tasks[task_id] = task
    task_queue.put(task_id)
    return jsonify({"task_id": task_id}), 200


@app.route("/task_status/<task_id>")
def task_status(task_id):
    t = tasks.get(task_id)
    if not t:
        return jsonify({"error": "task not found"}), 404
    return jsonify({
        'id': t['id'],
        'status': t.get('status'),
        'progress': t.get('progress'),
        'files': t.get('files'),
        'error': t.get('error')
    })


@app.route("/downloads/<path:filename>")
def download_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)


@app.route("/list_downloads")
def list_downloads():
    files = sorted(os.listdir(DOWNLOAD_DIR))
    return jsonify({'files': files})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
