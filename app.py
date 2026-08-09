import os
import threading
import queue
import uuid
import sys
import shutil
import subprocess
import time
from flask import Flask, request, jsonify, send_from_directory
from yt_dlp import YoutubeDL

app = Flask(__name__, template_folder=".", static_folder="static")

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
COOKIE_FILE = os.path.join(BASE_DIR, "cookies.txt")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

tasks = {}
task_queue = queue.Queue()

# --- Helpers: Language Mapping ---
ISO_LANG_MAP = {
    'English': 'en', 'Hindi': 'hi', 'Spanish': 'es', 'French': 'fr',
    'German': 'de', 'Japanese': 'ja', 'Korean': 'ko', 'Russian': 'ru',
    'Portuguese': 'pt', 'Arabic': 'ar', 'Bengali': 'bn', 'Tamil': 'ta',
    'Telugu': 'te', 'Malayalam': 'ml', 'Marathi': 'mr', 'Italian': 'it',
    'Turkish': 'tr', 'Indonesian': 'id', 'Thai': 'th', 'Vietnamese': 'vi',
    'Chinese': 'zh', 'Chinese (Simplified)': 'zh-Hans', 'Chinese (Traditional)': 'zh-Hant',
    'Urdu': 'ur', 'Punjabi': 'pa', 'Gujarati': 'gu', 'Kannada': 'kn',
}

def normalize_lang_name(name):
    clean = (name or '').strip()
    if clean in ISO_LANG_MAP:
        return clean, ISO_LANG_MAP[clean]
    for k, v in ISO_LANG_MAP.items():
        if v.lower() == clean.lower():
            return k, v
    return clean, clean.lower()

def _language_from_format(f):
    lang = (
        f.get('language')
        or (f.get('audio_track', {}) or {}).get('id')
        or f.get('lang')
        or 'und'
    )
    if isinstance(lang, dict):
        lang = lang.get('id') or lang.get('lang') or 'und'
    return lang

# --- LOGIC: FIND EXACT AUDIO FORMAT INFOS ---
def get_best_audio_infos(info_dict, selected_langs):
    formats = info_dict.get('formats', [])
    selected_infos = []

    audio_formats = [
        f for f in formats
        if f.get('vcodec') == 'none' and (f.get('acodec') and f.get('acodec') != 'none')
    ]

    for lang_choice in selected_langs:
        _, target_iso = normalize_lang_name(lang_choice)
        candidates = []
        for f in audio_formats:
            raw_lang = _language_from_format(f)
            _, file_iso = normalize_lang_name(raw_lang)
            match = False
            if file_iso == target_iso:
                match = True
            elif (target_iso in ['default', 'original', 'und']) and (file_iso in ['und', 'none', None, '']):
                match = True
            if match:
                candidates.append(f)
        
        if not candidates:
            continue

        def sort_key(f):
            abr = f.get('abr') or 0
            ext = f.get('ext', '')
            ext_score = 10 if ext == 'm4a' else 0
            return (abr, ext_score)

        candidates.sort(key=sort_key, reverse=True)
        best = candidates[0]
        selected_infos.append({
            'lang_name': lang_choice,
            'iso': target_iso,
            'id': best['format_id'],
            'ext': best.get('ext', 'm4a')
        })

    return selected_infos

# --- CLI HELPERS ---
def select_subtitles_cli(info_dict):
    subs = info_dict.get('subtitles', {})
    auto_subs = info_dict.get('automatic_captions', {})

    if not subs and not auto_subs:
        print("\n[CLI Info] No subtitles found.")
        return [], False

    print("\n" + "="*60)
    print("    AVAILABLE SUBTITLES")
    print("="*60)

    menu_map = {}
    counter = 1

    if subs:
        print("--- Official ---")
        for lang, details in subs.items():
            name = details[0].get('name', lang)
            print(f" {counter}. {name} [{lang}]")
            menu_map[counter] = {'code': lang, 'auto': False}
            counter += 1

    if auto_subs:
        print("--- Auto-Generated ---")
        for lang, details in auto_subs.items():
            name = details[0].get('name', lang)
            print(f" {counter}. {name} (Auto) [{lang}]")
            menu_map[counter] = {'code': lang, 'auto': True}
            counter += 1

    print("-" * 60)
    print("Enter numbers separated by commas (e.g. '1, 3').")
    print("Press ENTER to skip subtitles.")
    choice = input("Your Choice > ").strip()

    if not choice:
        return [], False

    final_langs = []
    write_auto = False

    try:
        indices = [int(x.strip()) for x in choice.split(',')]
        for idx in indices:
            if idx in menu_map:
                item = menu_map[idx]
                final_langs.append(item['code'])
                if item['auto']:
                    write_auto = True
    except ValueError:
        return [], False

    return list(set(final_langs)), write_auto

def select_audio_cli(info_dict):
    formats = info_dict.get('formats', [])
    audio_candidates = [
        f for f in formats
        if f.get('vcodec') == 'none' and (f.get('acodec') and f.get('acodec') != 'none')
    ]

    langs_set = set()
    for f in audio_candidates:
        raw = _language_from_format(f)
        disp, _ = normalize_lang_name(raw)
        langs_set.add(disp)

    if not langs_set:
        print("\n[CLI Info] No distinct audio languages found. Using automatic best selection.")
        return [], []

    print("\n" + "="*60)
    print("    AVAILABLE AUDIO LANGUAGES (Select Multiple)")
    print("="*60)
    menu_map = {}
    counter = 1
    sorted_langs = sorted(list(langs_set))

    for lang_name in sorted_langs:
        print(f" {counter}. {lang_name}")
        menu_map[counter] = lang_name
        counter += 1

    print("-" * 60)
    print("Enter numbers separated by commas to MERGE (e.g. '1, 2' for Dual/Multiple Audio).")
    print("Press ENTER for Best Default Audio only.")
    choice = input("Your Choice > ").strip()

    if not choice:
        return [], []

    selected_langs = []
    try:
        indices = [int(x.strip()) for x in choice.split(',')]
        for idx in indices:
            if idx in menu_map:
                selected_langs.append(menu_map[idx])
    except ValueError:
        return [], []

    return selected_langs, sorted_langs

# --- Custom logger ---
class YTDLPLogger:
    def debug(self, msg):
        pass
    def info(self, msg):
        if msg:
            print(msg)
    def warning(self, msg):
        if not msg: return
        low = msg.lower()
        if 'impersonation' in low and 'no impersonate target' in low:
            return
        print("[yt-dlp warning]", msg, file=sys.stderr)
    def error(self, msg):
        print("[yt-dlp error]", msg, file=sys.stderr)

# --- WORKER HELPERS ---
def progress_hook(d, task_id):
    task = tasks.get(task_id)
    if not task: return

    status = d.get('status')
    if status == 'downloading':
        percent = d.get('_percent_str', '').strip()
        total = d.get('_total_bytes_str') or d.get('_total_bytes_str_est') or d.get('total_bytes') or ''
        speed = d.get('_speed_str', '') or d.get('speed') or ''
        eta = d.get('_eta_str', '') or d.get('eta') or ''
        comp = d.get('filename') or (d.get('info_dict') or {}).get('title', '') or task.get('url', '')
        print(f"[{task_id}] {d.get('status')} | {comp} | {percent} | {total} | {speed} | ETA {eta}")
        try:
            p = float(percent.replace('%',''))
        except Exception:
            p = 0.0
        task['progress'] = {
            'status': 'downloading',
            'percent': p,
            'eta': eta,
            'speed': speed,
            'message': f"Downloading {comp} {percent}"
        }
    elif status == 'finished':
        filename = d.get('filename') or (d.get('info_dict') or {}).get('title', '')
        print(f"[{task_id}] finished downloading: {filename}")
        task['progress'] = {
            'status': 'processing',
            'percent': 100,
            'message': f"Finished {filename}"
        }

def _convert_thumbnail_to_jpeg(src_path):
    if not src_path or not os.path.exists(src_path):
        return None
    ext = os.path.splitext(src_path)[1].lower()
    if ext in ('.jpg', '.jpeg'):
        return src_path
    dst = os.path.splitext(src_path)[0] + '.jpg'
    try:
        subprocess.run(['ffmpeg', '-y', '-i', src_path, dst], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(dst):
            return dst
    except Exception:
        return None
    return None

def _escape_ffmeta_value(val):
    if val is None: return ''
    if not isinstance(val, str): val = str(val)
    val = val.replace('\\', '\\\\').replace('=', '\\=').replace(';', '\\;').replace('#', '\\#')
    val = val.replace('\x00', '').replace('\r', '').replace('\n', '\\n')
    return val

def _write_ffmetadata_from_info(info, path):
    """
    Writes expanded metadata to FFMETADATA file.
    Covers: Channel, Publisher, Genre, Fingerprint, Description, Keywords,
    Dates, Counts (Like, Dislike, Comment, Sub, View), IDs, Handler.
    """
    try:
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(";FFMETADATA1\n")
            def write_tag(k, v):
                if v is None: return
                v2 = _escape_ffmeta_value(v)
                if v2 != '': fh.write(f"{k}={v2}\n")

            # Basic Info
            write_tag('title', info.get('title'))
            write_tag('artist', info.get('uploader') or info.get('uploader_id')) # Channel Name / Artist
            write_tag('album_artist', info.get('channel')) # Channel Name alternative
            write_tag('album', info.get('channel') or info.get('uploader')) 
            write_tag('publisher', info.get('uploader') or info.get('channel')) # Publisher
            
            # URLs & IDs
            write_tag('purl', info.get('webpage_url'))
            write_tag('video_fingerprint', info.get('id')) # Video fingerprint (ID)
            write_tag('uploader_id', info.get('uploader_id')) # Uploader ID / Handler
            write_tag('handler_name', info.get('uploader_id')) # Handler Name
            write_tag('channel_id', info.get('channel_id'))

            # Description & Genre
            description = info.get('description') or ''
            if description:
                write_tag('description', description) # Entire description details
                write_tag('comment', description)
                write_tag('synopsis', description)
            
            category = ''
            if info.get('categories'):
                category = ','.join(info.get('categories')) if isinstance(info.get('categories'), list) else str(info.get('categories'))
            write_tag('genre', category) # Video Genre

            # Keywords
            tags = info.get('tags') or []
            if tags:
                tag_str = ','.join(tags) if isinstance(tags, list) else str(tags)
                write_tag('keywords', tag_str) # Video keywords

            # Date
            upload_date = info.get('upload_date') or ''
            if upload_date and len(upload_date) == 8:
                try:
                    date_formatted = f"{upload_date[0:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
                    write_tag('date', date_formatted) # Date of upload
                    write_tag('creation_time', date_formatted)
                except:
                    write_tag('date', upload_date)
            elif upload_date:
                write_tag('date', upload_date)

            # Statistics (Counts)
            write_tag('view_count', info.get('view_count'))
            write_tag('like_count', info.get('like_count'))
            write_tag('dislike_count', info.get('dislike_count')) # Usually None but mapped
            write_tag('comment_count', info.get('comment_count'))
            write_tag('subscriber_count', info.get('channel_follower_count')) # Channel subscriber counts

            # Technical / Flags
            write_tag('age_limit', info.get('age_limit'))
            write_tag('is_live', info.get('is_live'))
            write_tag('language', info.get('language') or info.get('lang'))

            # Chapters
            chapters = info.get('chapters') or []
            for ch in chapters:
                start_ms = int(float(ch.get('start_time', 0)) * 1000)
                end_ms = int(float(ch.get('end_time', 0)) * 1000)
                title_ch = ch.get('title', '')
                fh.write("[CHAPTER]\n")
                fh.write("TIMEBASE=1/1000\n")
                fh.write(f"START={start_ms}\n")
                fh.write(f"END={end_ms}\n")
                if title_ch:
                    safe_title = _escape_ffmeta_value(title_ch)
                    fh.write(f"title={safe_title}\n")
        return True
    except Exception:
        try:
            if os.path.exists(path): os.remove(path)
        except: pass
        return False

# --- WORKER LOGIC ---
def worker():
    while True:
        task_id = task_queue.get()
        if task_id is None: break

        task = tasks.get(task_id)
        if not task:
            task_queue.task_done()
            continue

        temp_files = []
        subtitle_files = []
        thumbnail_file = None
        ffmetadata_file = None

        try:
            task['status'] = 'processing'
            url = task['url']
            choice = task['choice']

            print(f"\n[Task {task_id}] Fetching Metadata...", flush=True)

            meta_opts = {
                'quiet': True,
                'no_warnings': True,
                'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
                'remote_components': ['ejs:github'],
                'logger': YTDLPLogger(),
            }

            with YoutubeDL(meta_opts) as ydl_meta:
                info = ydl_meta.extract_info(url, download=False)

            final_title = info.get('title', 'video')
            clean_title = "".join([c for c in final_title if c.isalnum() or c in (' ', '-', '_')]).strip()

            ffmetadata_file = os.path.join(DOWNLOAD_DIR, f"{task_id}_ffmetadata.txt")
            has_ffmetadata = _write_ffmetadata_from_info(info, ffmetadata_file)
            if not has_ffmetadata and os.path.exists(ffmetadata_file):
                try: os.remove(ffmetadata_file)
                except: pass
                ffmetadata_file = None

            print("\n" + "!"*50)
            print(" WAITING FOR INPUT: CHECK TERMINAL NOW ")
            print("!"*50)

            selected_subs, write_auto = select_subtitles_cli(info)
            selected_audio_langs, _ = select_audio_cli(info)

            print(f"\n[Task {task_id}] Starting Sequential Download & Merge...")

            # --- 1. DOWNLOAD VIDEO TRACK ONLY ---
            print(f"--> Phase 1: Downloading Video Track...")
            
            # --- FIX: FORCE H.264/AVC TO PREVENT VLC CRASHES ---
            # Prioritizes H.264 (avc1) codec. Falls back to others only if H.264 is missing.
            if choice == 'best':
                video_fmt = "bestvideo[vcodec^=avc]/bestvideo[vcodec^=h264]/bestvideo"
            elif str(choice).isdigit():
                video_fmt = f"bestvideo[height<={choice}][vcodec^=avc]/bestvideo[height<={choice}][vcodec^=h264]/bestvideo[height<={choice}]"
            else:
                video_fmt = "bestvideo[vcodec^=avc]/bestvideo"

            vid_filename = f"{task_id}_video"
            vid_opts = {
                'format': video_fmt,
                'outtmpl': os.path.join(DOWNLOAD_DIR, f"{vid_filename}.%(ext)s"),
                'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
                'writethumbnail': True,
                'progress_hooks': [lambda d: progress_hook(d, task_id)],
                'quiet': False,
                'remote_components': ['ejs:github'],
                'logger': YTDLPLogger(),
                'retries': 10,
                'concurrent_fragment_downloads': 10,
                'socket_timeout': 30,
            }

            with YoutubeDL(vid_opts) as ydl:
                info_v = ydl.extract_info(url, download=True)
                vid_ext = info_v.get('ext', 'mp4')
                actual_vid_path = os.path.join(DOWNLOAD_DIR, f"{vid_filename}.{vid_ext}")
                temp_files.append(actual_vid_path)
                
                # find thumbnail
                for f in os.listdir(DOWNLOAD_DIR):
                    if f.startswith(vid_filename) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        thumbnail_file = os.path.join(DOWNLOAD_DIR, f)
                        break
                if not thumbnail_file:
                    for f in os.listdir(DOWNLOAD_DIR):
                        if f.startswith(clean_title) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                            thumbnail_file = os.path.join(DOWNLOAD_DIR, f)
                            break

            # --- 2. DOWNLOAD SUBTITLES ---
            if selected_subs:
                print("--> Downloading selected subtitles...")
                sub_opts = {
                    'writesubtitles': True,
                    'writeautomaticsub': write_auto,
                    'subtitleslangs': selected_subs,
                    'subtitlesformat': 'srt',
                    'skip_download': True,
                    'outtmpl': os.path.join(DOWNLOAD_DIR, f"{task_id}_subs.%(ext)s"),
                    'quiet': False,
                    'remote_components': ['ejs:github'],
                    'logger': YTDLPLogger(),
                }
                with YoutubeDL(sub_opts) as ydl_sub:
                    try:
                        ydl_sub.download([url])
                        for f in os.listdir(DOWNLOAD_DIR):
                            if f.startswith(f"{task_id}_subs") and f.endswith('.srt'):
                                subtitle_files.append(os.path.join(DOWNLOAD_DIR, f))
                    except Exception:
                        subtitle_files = []

            # --- 3. SELECT AUDIO TRACKS AND DOWNLOAD ---
            audio_files_map = []
            if not selected_audio_langs:
                selected_audio_langs = ["Default"]

            audio_jobs = get_best_audio_infos(info, selected_audio_langs)
            if not audio_jobs and "Default" in selected_audio_langs:
                audio_jobs.append({'id': 'bestaudio', 'lang_name': 'Original', 'iso': 'eng', 'ext': 'm4a'})

            for idx, job in enumerate(audio_jobs):
                print(f"--> Phase 2.{idx+1}: Downloading Audio ({job['lang_name']})...")
                aud_filename = f"{task_id}_audio_{idx}"
                aud_opts = {
                    'format': job['id'],
                    'outtmpl': os.path.join(DOWNLOAD_DIR, f"{aud_filename}.%(ext)s"),
                    'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
                    'progress_hooks': [lambda d: progress_hook(d, task_id)],
                    'quiet': False,
                    'remote_components': ['ejs:github'],
                    'logger': YTDLPLogger(),
                    'retries': 10,
                    'concurrent_fragment_downloads': 10,
                    'socket_timeout': 30,
                }
                with YoutubeDL(aud_opts) as ydl_aud:
                    ydl_aud.download([url])
                    expected_ext = job.get('ext', None)
                    found = None
                    for f in os.listdir(DOWNLOAD_DIR):
                        if f.startswith(aud_filename + "."):
                            found = os.path.join(DOWNLOAD_DIR, f)
                            break
                    if not found and expected_ext:
                        candidate = os.path.join(DOWNLOAD_DIR, f"{aud_filename}.{expected_ext}")
                        if os.path.exists(candidate):
                            found = candidate
                    if found and os.path.exists(found):
                        temp_files.append(found)
                        audio_files_map.append({
                            'path': found,
                            'iso': job['iso'],
                            'title': job['lang_name']
                        })
                    else:
                        print(f"[Warning] Could not locate downloaded audio file for job {job}")

            # --- 4. PREPARE THUMBNAIL ---
            jpeg_thumb = None
            if thumbnail_file and os.path.exists(thumbnail_file):
                jpeg_thumb = _convert_thumbnail_to_jpeg(thumbnail_file)
                if not jpeg_thumb and thumbnail_file.lower().endswith(('.jpg', '.jpeg')):
                    jpeg_thumb = thumbnail_file

            # --- 5. MERGE USING FFMPEG ---
            print(f"--> Phase 3: Merging {1 + len(audio_files_map)} tracks with ffmpeg...")
            task['progress']['message'] = "Merging All Tracks..."

            output_filename = f"{clean_title}.mkv"
            output_path = os.path.join(DOWNLOAD_DIR, output_filename)

            cmd = ['ffmpeg', '-y', '-fflags', '+genpts', '-i', actual_vid_path]

            for aud in audio_files_map:
                cmd.extend(['-i', aud['path']])

            for sub in subtitle_files:
                cmd.extend(['-i', sub])

            metadata_input_index = None
            if ffmetadata_file and os.path.exists(ffmetadata_file):
                cmd.extend(['-f', 'ffmetadata', '-i', ffmetadata_file])
                metadata_input_index = 1 + len(audio_files_map) + len(subtitle_files)

            if metadata_input_index is not None:
                cmd.extend(['-map_metadata', str(metadata_input_index)])
                cmd.extend(['-map_chapters', str(metadata_input_index)])
            else:
                cmd.extend(['-map_metadata', '0'])
                cmd.extend(['-map_chapters', '0'])

            cmd.extend(['-map', '0:v:0'])
            cmd.extend(['-metadata:s:v:0', 'title=Video'])

            for i, aud in enumerate(audio_files_map):
                input_index = i + 1
                cmd.extend(['-map', f'{input_index}:a:0'])
                cmd.extend([f'-metadata:s:a:{i}', f'language={aud["iso"]}'])
                cmd.extend([f'-metadata:s:a:{i}', f'title={aud["title"]}'])

            for j, sub in enumerate(subtitle_files):
                input_index = 1 + len(audio_files_map) + j
                cmd.extend(['-map', f'{input_index}:0'])
                lang_meta = 'und'
                try:
                    base = os.path.basename(sub)
                    parts = base.split('.')
                    if len(parts) >= 3:
                        maybe_lang = parts[-2]
                        _, iso = normalize_lang_name(maybe_lang)
                        lang_meta = iso
                except: pass
                cmd.extend([f'-metadata:s:s:{j}', f'language={lang_meta}'])

            cmd.extend(['-c:v', 'copy', '-c:a', 'copy', '-c:s', 'copy'])
            cmd.extend(['-avoid_negative_ts', 'make_zero'])

            if jpeg_thumb and os.path.exists(jpeg_thumb):
                cmd.extend(['-attach', jpeg_thumb, '-metadata:s:t:0', 'mimetype=image/jpeg'])

            cmd.append(output_path)

            print(f"Executing: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)

            # --- 6. CLEANUP ---
            print("--> Phase 4: Cleanup")
            for f in temp_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass
            for s in subtitle_files:
                if os.path.exists(s):
                    try:
                        os.remove(s)
                    except:
                        pass
            if thumbnail_file and os.path.exists(thumbnail_file) and thumbnail_file != jpeg_thumb:
                try:
                    os.remove(thumbnail_file)
                except:
                    pass
            if jpeg_thumb and os.path.exists(jpeg_thumb):
                try:
                    os.remove(jpeg_thumb)
                except:
                    pass
            if ffmetadata_file and os.path.exists(ffmetadata_file):
                try:
                    os.remove(ffmetadata_file)
                except:
                    pass

            task['status'] = 'done'
            task['progress'] = {
                'status': 'finished',
                'percent': 100,
                'message': 'Download Complete'
            }
            task['files'] = [output_filename]

        except Exception as e:
            err_msg = str(e)
            print(f"Task Error: {err_msg}", flush=True)
            task['status'] = 'error'
            task['error'] = err_msg
            if "Sign in" in err_msg or "cookies" in err_msg.lower():
                if 'progress' not in task:
                    task['progress'] = {}
                task['progress']['error'] = 'youtube_requires_cookies'
            
            # cleanup on error
            for f in temp_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass
            for s in subtitle_files:
                if os.path.exists(s):
                    try:
                        os.remove(s)
                    except:
                        pass
            if thumbnail_file and os.path.exists(thumbnail_file):
                try:
                    os.remove(thumbnail_file)
                except:
                    pass
            if ffmetadata_file and os.path.exists(ffmetadata_file):
                try:
                    os.remove(ffmetadata_file)
                except:
                    pass

        finally:
            task_queue.task_done()

threading.Thread(target=worker, daemon=True).start()

# --- ROUTES ---
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/start_download", methods=["POST"])
def start_download():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'id': task_id,
        'url': url,
        'mode': data.get("mode", "single"),
        'choice': data.get("choice", "best"),
        'status': 'queued',
        'progress': {'status': 'queued', 'message': 'Initializing...'},
        'files': []
    }
    task_queue.put(task_id)
    return jsonify({"task_id": task_id})

@app.route("/task_status/<task_id>")
def task_status(task_id):
    t = tasks.get(task_id)
    if not t:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({
        'id': t['id'],
        'status': t.get('status'),
        'progress': t.get('progress'),
        'error': t.get('error'),
        'files': t.get('files')
    })

@app.route("/downloads/<path:filename>")
def download_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

@app.route("/list_downloads")
def list_downloads():
    try:
        files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f)) and not f.endswith('.part')]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(DOWNLOAD_DIR, x)), reverse=True)
        return jsonify({'files': files})
    except:
        return jsonify({'files': []})

if __name__ == "__main__":
    app.run(debug=False, port=5000)
