import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import yt_dlp
import threading
import os
import re
import unicodedata
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error
from PIL import Image
import io
from concurrent.futures import ThreadPoolExecutor

# ====== CẤU HÌNH MẦC ĐỊNH ======
default_download_path = os.path.join(os.path.expanduser("~"), "Downloads")
if not os.path.exists(default_download_path):
    os.makedirs(default_download_path)

download_folder = default_download_path
playlist_videos = []
video_vars = []
quality = "192"


# ====== HÀM BỚ DẤU ======
def remove_accents(input_str):
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


# ====== HÀM CHỌN THƯ MỤC ======
def choose_folder():
    global download_folder
    folder = filedialog.askdirectory()
    if folder:
        download_folder = folder
        folder_label.config(text=f"📁 Lưu tại: {download_folder}")


# ====== CẤP NHẬT TIẾN TRÌNH ======
def update_progress(msg, color="blue"):
    progress_label.config(text=msg, fg=color)


# ====== PHÂN TÍCH PLAYLIST ======
def analyze_playlist():
    url = entry_url.get()
    if not url:
        messagebox.showwarning("Thiếu URL", "Vui lòng nhập URL playlist YouTube.")
        return
    update_progress("🔍 Đang phân tích playlist...", "orange")

    def run_analysis():
        try:
            ydl_opts = {
                "quiet": True,
                "extract_flat": False,
                "skip_download": True,
                "ignoreerrors": True,
                "no_warnings": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                playlist_info = ydl.extract_info(url, download=False, process=True)
                global playlist_videos, video_vars

                if playlist_info.get("_type") == "playlist":
                    entries = playlist_info.get("entries", [])
                    if not entries:
                        update_progress("❌ Không tìm thấy video nào.", "red")
                        return

                    playlist_title = re.sub(
                        r'[\\/:*?"<>|]', "_", playlist_info.get("title", "playlist")
                    )

                    def extract_entry(entry):
                        try:
                            return {"id": entry.get("id"), "title": entry.get("title")}
                        except:
                            return None

                    with ThreadPoolExecutor(max_workers=6) as executor:
                        results = list(executor.map(extract_entry, entries))

                    playlist_videos = [v for v in results if v]

                else:
                    playlist_title = re.sub(
                        r'[\\/:*?"<>|]', "_", playlist_info.get("title", "video")
                    )
                    playlist_videos = [
                        {"id": playlist_info["id"], "title": playlist_info["title"]}
                    ]

                subfolder_entry.delete(0, tk.END)
                subfolder_entry.insert(0, playlist_title)

                video_vars = []
                for widget in scrollable_frame.winfo_children():
                    widget.destroy()

                for v in playlist_videos:
                    var = tk.BooleanVar(value=True)
                    cb = tk.Checkbutton(
                        scrollable_frame,
                        text=v["title"],
                        variable=var,
                        anchor="w",
                        justify="left",
                        wraplength=560,
                    )
                    cb.pack(anchor="w", padx=5)
                    video_vars.append(var)

                update_progress(f"✅ Tìm thấy {len(playlist_videos)} video.", "green")

        except Exception:
            update_progress("❌ Lỗi phân tích playlist.", "red")

    threading.Thread(target=run_analysis).start()


# ====== TẢI AUDIO VÀ THUMBNAIL ======
def download_audio_and_thumbnail(video, target_folder):
    import urllib.request

    title = video["title"]
    if remove_diacritics_var.get():
        title = remove_accents(title)

    safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)
    filename_base = os.path.join(target_folder, safe_title)
    mp3_file = f"{filename_base}.mp3"
    video_url = f"https://www.youtube.com/watch?v={video['id']}"

    current_dir = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_dir = os.path.join(
        current_dir, "ffmpeg", "ffmpeg-7.1.1-essentials_build", "bin"
    )

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{filename_base}.%(ext)s",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": quality,
            }
        ],
        "writethumbnail": True,
        "quiet": True,
        "ignoreerrors": True,
        "no_warnings": True,
        "ffmpeg_location": ffmpeg_dir,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
    except Exception:
        return None

    thumb_path = None
    for ext in ["webp", "jpg"]:
        test_path = f"{filename_base}.{ext}"
        if os.path.exists(test_path):
            thumb_path = test_path
            break

    if not thumb_path:
        try:
            thumb_url = f"https://img.youtube.com/vi/{video['id']}/maxresdefault.jpg"
            fallback_path = f"{filename_base}.jpg"
            urllib.request.urlretrieve(thumb_url, fallback_path)
            if os.path.exists(fallback_path):
                thumb_path = fallback_path
        except:
            pass

    return (mp3_file, thumb_path, title)


# ====== NHÚNG ẢNH VÀO MP3 (CHUẨN PSP) ======
def embed_thumbnail(mp3_path, thumb_path, title):
    if not mp3_path or not thumb_path:
        return
    try:
        if thumb_path.endswith(".webp"):
            jpg_path = thumb_path.replace(".webp", ".jpg")
            try:
                im = Image.open(thumb_path).convert("RGB")
                im.save(jpg_path, "JPEG")
                os.remove(thumb_path)
                thumb_path = jpg_path
            except:
                return

        im = Image.open(thumb_path).convert("RGB")
        im = im.resize((128, 128))
        byte_io = io.BytesIO()
        im.save(byte_io, format="JPEG")
        image_data = byte_io.getvalue()

        audio = MP3(mp3_path, ID3=ID3)
        try:
            audio.add_tags()
        except error:
            pass

        audio.tags.delall("APIC")
        audio.tags.add(
            APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=image_data)
        )
        audio.save()

        update_progress(f"✅ Nhúng xong: {title}", "green")
    except:
        update_progress(f"❌ Lỗi nhúng ảnh: {title}", "red")


# ====== TẢI VIDEO ĐÃ CHỌN ======
def download_selected():
    url = entry_url.get()
    if not url or not playlist_videos:
        messagebox.showwarning(
            "Thiếu dữ liệu", "Vui lòng nhập URL và phân tích playlist trước."
        )
        return

    selected = [v for v, check in zip(playlist_videos, video_vars) if check.get()]
    if not selected:
        messagebox.showinfo("Không có video", "Bạn chưa chọn video nào để tải.")
        return

    custom_subfolder = subfolder_entry.get().strip()
    if not custom_subfolder:
        messagebox.showwarning("Thiếu thư mục", "Vui lòng nhập tên subfolder.")
        return

    safe_subfolder = re.sub(
        r'[\\/:*?"<>|\s]+$', "", re.sub(r'[\\/:*?"<>|]', "_", custom_subfolder)
    )
    target_folder = os.path.join(download_folder, safe_subfolder)
    try:
        os.makedirs(target_folder, exist_ok=True)
    except Exception as e:
        update_progress(f"❌ Lỗi thư mục: {str(e)}", "red")
        return

    btn_download.config(state=tk.DISABLED)

    def threaded_download():
        download_results = []
        for idx, v in enumerate(selected, 1):
            update_progress(
                f"⬇️ [{idx}/{len(selected)}] Đang tải: {v['title']}", "orange"
            )
            result = download_audio_and_thumbnail(v, target_folder)
            if result:
                download_results.append(result)

        update_progress("🖼️ Đang nhúng thumbnail...", "blue")
        with ThreadPoolExecutor(max_workers=3) as pool2:
            pool2.map(lambda args: embed_thumbnail(*args), download_results)

        update_progress("🎉 Hoàn tất tất cả!", "green")
        btn_download.config(state=tk.NORMAL)

    threading.Thread(target=threaded_download).start()


# ====== GIAO DIỆN GUI ======
app = tk.Tk()
app.title("YouTube Playlist to MP3 Downloader")
app.geometry("620x720")
app.resizable(False, False)

tk.Label(app, text="🎵 Nhập link playlist YouTube:", font=("Arial", 12)).pack(pady=5)
entry_url = tk.Entry(app, width=75)
entry_url.pack(pady=5)

btn_folder = tk.Button(
    app, text="📂 Chọn thư mục lưu", font=("Arial", 10), command=choose_folder
)
btn_folder.pack(pady=5)

folder_label = tk.Label(app, text=f"📁 Lưu tại: {download_folder}", font=("Arial", 10))
folder_label.pack(pady=2)

frame_quality = tk.Frame(app)
tk.Label(frame_quality, text="🎷 Chọn chất lượng:", font=("Arial", 10)).pack(
    side="left", padx=5
)
quality_box = ttk.Combobox(
    frame_quality, values=["128", "192", "256", "320"], state="readonly", width=5
)
quality_box.set("192")
quality_box.pack(side="left")
frame_quality.pack(pady=5)

tk.Label(app, text="📂 Tên thư mục con:", font=("Arial", 10)).pack(pady=3)
subfolder_entry = tk.Entry(app, width=40)
subfolder_entry.pack(pady=2)

remove_diacritics_var = tk.BooleanVar(value=False)
tk.Checkbutton(app, text="🅰️ Bỏ dấu tên bài hát", variable=remove_diacritics_var).pack(
    pady=2
)

tk.Button(
    app, text="🔍 Phân tích playlist", font=("Arial", 11), command=analyze_playlist
).pack(pady=8)

list_container = tk.Frame(app)
list_container.pack(fill="both", expand=True, padx=10, pady=5)

canvas = tk.Canvas(list_container, width=580, height=250)
scrollbar = tk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
scrollable_frame = tk.Frame(canvas)

scrollable_frame.bind(
    "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)
canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)
canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

btn_download = tk.Button(
    app, text="⬇️ Tải video đã chọn", font=("Arial", 11), command=download_selected
)
btn_download.pack(pady=10)

progress_label = tk.Label(app, text="", font=("Courier", 10), fg="blue")
progress_label.pack(pady=5)

app.mainloop()
