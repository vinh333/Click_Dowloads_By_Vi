import os
import unicodedata
import threading
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, error
from PIL import Image
import io
import tkinter as tk
from tkinter import filedialog, messagebox, Label, Button


# Xoá dấu tiếng Việt khỏi tên file
def remove_vietnamese_accents(text):
    text = unicodedata.normalize("NFD", text)
    return "".join(char for char in text if unicodedata.category(char) != "Mn")


# Resize ảnh thumbnail gốc (nếu có)
def resize_image_bytes(image_data, size=(128, 128)):
    image = Image.open(io.BytesIO(image_data))
    image = image.convert("RGB")
    image = image.resize(size, Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


# Xử lý từng file mp3: đổi tên + resize thumbnail nếu có
def process_mp3_file(folder_path, filename):
    name, ext = os.path.splitext(filename)
    new_name = remove_vietnamese_accents(name) + ext

    old_path = os.path.join(folder_path, filename)
    new_path = os.path.join(folder_path, new_name)

    renamed = False
    if new_name != filename:
        if not os.path.exists(new_path):
            os.rename(old_path, new_path)
            renamed = True
        else:
            return "trùng tên", new_name

    # Dù tên đổi hay không, dùng đường dẫn mới
    file_path = new_path if renamed else old_path

    # Resize thumbnail nếu có
    try:
        audio = MP3(file_path, ID3=ID3)
        if audio.tags is None:
            return "thiếu ID3", new_name

        apic_tags = audio.tags.getall("APIC")
        if not apic_tags:
            return "không có thumbnail", new_name

        original_apic = apic_tags[0]
        resized_data = resize_image_bytes(original_apic.data)

        audio.tags.delall("APIC")
        audio.tags.add(
            APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=resized_data)
        )
        audio.save()
        return "xong", new_name
    except Exception as e:
        return f"lỗi: {e}", new_name


# Xử lý toàn bộ thư mục
def process_folder(folder_path, btn):
    btn.config(state="disabled")
    renamed = 0
    resized = 0
    skipped = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".mp3"):
            result, name = process_mp3_file(folder_path, filename)
            if result == "xong":
                renamed += 1
                resized += 1
            elif result == "trùng tên":
                skipped.append(name + " (trùng)")
            elif result == "không có thumbnail":
                skipped.append(name + " (thiếu thumbnail)")
            elif result == "thiếu ID3":
                skipped.append(name + " (không có ID3 tag)")
            else:
                skipped.append(name + f" ({result})")

    msg = f"✅ Đã xử lý {renamed} file MP3 (đổi tên & resize thumbnail).\n"
    if skipped:
        msg += f"\n⚠️ {len(skipped)} file bị bỏ qua hoặc lỗi:\n" + "\n".join(skipped)
    messagebox.showinfo("🎯 Kết quả", msg)
    btn.config(state="normal")


# GUI chọn thư mục và chạy xử lý trên thread
def choose_folder_and_process():
    folder_path = filedialog.askdirectory(title="📁 Chọn thư mục chứa file .mp3")
    if folder_path:
        threading.Thread(
            target=process_folder, args=(folder_path, btn), daemon=True
        ).start()


# GUI
root = tk.Tk()
root.title("MP3 Tối Ưu Cho PSP – Xoá dấu & Fix thumbnail")
root.geometry("500x240")

Label(
    root,
    text="🎧 Công cụ xoá dấu tên file & resize thumbnail MP3\nChuẩn hoá toàn bộ để chép vào PSP",
    font=("Arial", 12),
).pack(pady=20)

btn = Button(
    root,
    text="📂 Chọn thư mục và bắt đầu xử lý",
    font=("Arial", 12),
    command=choose_folder_and_process,
)
btn.pack(pady=10)

root.mainloop()
