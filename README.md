# Universal-Media-Downloader#

🚀 Universal Media Downloader

<p align="left">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" />
  <img src="https://img.shields.io/badge/Node.js-339933?style=for-the-badge&logo=nodedotjs&logoColor=white" />
  <img src="https://img.shields.io/badge/FFmpeg-007808?style=for-the-badge&logo=ffmpeg&logoColor=white" />
  <img src="https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white" />
</p>

A powerful, full-stack, multithreaded media downloading tool that bypasses the limitations of standard video-downloading websites. Built with a Flask backend and a clean web UI, it allows you to download high-resolution videos (even 2+ hour long files) from YouTube, Twitter, Instagram, and Facebook with total control over video quality, audio streams, subtitles, and metadata.

> **Note:** This is a standalone application that runs on your local machine, not a hosted website. 

---

## ✨ Features

* **Unrestricted & High-Speed:** Handles massive video files completely for free, without throttling.
* **Total Video Control:** Downloads at your exact chosen resolution (4K, 2K, 1080p, etc.), cleanly muxing the highest quality streams.
* **Advanced Subtitles:** Allows selection of specific subtitle languages, or merging multiple subtitle tracks into the same file.
* **Custom Audio Mapping:** Choose to extract default audio, dubbed tracks, or merge multiple audio tracks together.
* **Rich Metadata & Chapters:** Automatically scrapes and embeds the creator's name, artist, upload date, subscriber count, and like count. Injects interactive **Chapters** directly into the final timeline.
* **Native Thumbnails:** Embeds the high-res video thumbnail as the file icon.
* **Playlist Support:** Built to handle and iterate through full playlist queues.
* **MKV Output:** Everything is beautifully packaged into an `.mkv` container to preserve multiple streams without quality loss.
* **Real-Time CLI & UI Tracking:** The backend terminal provides precise timestamped progress, which is mirrored in real-time to the web UI.

---

## 🛠️ Prerequisites & Dependencies

To run this tool locally, your system must have the following dependencies installed. 

1. **[Python (3.8+)](https://www.python.org/downloads/)**
   * *Why?* The core backend server (`app.py`) is written in Python using Flask.
2. **[FFmpeg](https://ffmpeg.org/download.html)**
   * *Why?* FFmpeg is the industry standard for multimedia processing. YouTube stores high-quality video and audio as separate tracks. This project uses FFmpeg to precisely merge (mux) the video, audio, and subtitle tracks together into a single file without losing quality. **Ensure FFmpeg is added to your system's PATH.**
3. **[Node.js](https://nodejs.org/en/download/)**
   * *Why?* Video platforms frequently update their backend authorization algorithms. They serve complex JavaScript puzzles to verify you aren't a bot. Node.js is required to efficiently solve these JS challenges before fetching video packets.
4. **Browser Extension: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/ccpbcnalfobbraiijhggfbnbkfkfcdbh)**
   * *Why?* To bypass throttling and age-restrictions, this tool mimics an authenticated user. You must export your YouTube session cookies in Netscape format and save them in the project folder.

---

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/subhromitra2004/universal-media-downloader.git]
   cd universal-media-downloader
<img width="990" height="375" alt="image" src="https://github.com/user-attachments/assets/8cab0d90-f73e-4e62-9864-8573e0c8a1c6" />

<img width="912" height="370" alt="image" src="https://github.com/user-attachments/assets/99a44443-4b7c-4022-aa6b-fa3da660007e" />

<img width="906" height="360" alt="image" src="https://github.com/user-attachments/assets/ad4c08b4-1231-4e00-96b5-87bd247d5701" />

📦 universal-media-downloader

 ┣ 📂 downloads/         # Output directory for your final MKV files
 
 ┣ 📂 static/
 
 ┃ ┗ 📜 style.css        # Clean, modern UI styling
 
 ┣ 📜 app.py             # Main Flask backend and threaded worker logic
 
 ┣ 📜 index.html         # Frontend interface
 
 ┣ 📜 install.bat        # Dependency installation script
 
 ┣ 📜 run.bat            # Server startup and browser launch script
 
 ┗ 📜 cookies.txt        # Your exported authentication file
 

 ⚠️ Important Disclaimer

 Remember that YouTube and other video hosting platforms regularly update their backend policies and algorithms to prevent users from downloading video content using automated code.

It is highly probable that this project might be working today, but may break tomorrow. No need to worry—the project didn't become useless! Just open your CLI and update the core extraction engine by running:

Bash:

pip install -U yt-dlp


Some Screenshots taken while downloading a youtube video using this tool :

<img width="1280" height="614" alt="image" src="https://github.com/user-attachments/assets/7c5844b5-4ce0-4b80-a0ab-284cd9a2dad5" />

<img width="1280" height="686" alt="image" src="https://github.com/user-attachments/assets/763a7463-9e5c-410a-baf7-fa009e237783" />







   

   
