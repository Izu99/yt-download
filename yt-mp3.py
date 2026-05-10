#!/usr/bin/env python3
import customtkinter as ctk
import subprocess
import threading
import os
import re

SAVE_DIR = os.path.expanduser("~/Music/YouTube-MP3")
os.makedirs(SAVE_DIR, exist_ok=True)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YouTube MP3 Downloader")
        self.geometry("560x520")
        self.resizable(False, False)

        self._build_ui()

    def _build_ui(self):
        # Header
        ctk.CTkLabel(
            self, text="YouTube MP3 Downloader",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(24, 4))

        ctk.CTkLabel(
            self, text="Paste a YouTube link and hit Download",
            font=ctk.CTkFont(size=13), text_color="gray"
        ).pack(pady=(0, 16))

        # URL entry
        url_frame = ctk.CTkFrame(self, fg_color="transparent")
        url_frame.pack(fill="x", padx=30)

        ctk.CTkLabel(url_frame, text="YouTube URL", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        self.url_entry = ctk.CTkEntry(
            url_frame, placeholder_text="https://youtu.be/...",
            height=40, font=ctk.CTkFont(size=13)
        )
        self.url_entry.pack(fill="x", pady=(4, 0))

        # Save folder row
        folder_frame = ctk.CTkFrame(self, fg_color="transparent")
        folder_frame.pack(fill="x", padx=30, pady=(8, 0))
        ctk.CTkLabel(folder_frame, text="Save to:", font=ctk.CTkFont(size=11), text_color="gray").pack(side="left")
        ctk.CTkLabel(folder_frame, text=SAVE_DIR, font=ctk.CTkFont(size=11), text_color="#4fc3f7").pack(side="left", padx=6)

        # Download button
        self.btn = ctk.CTkButton(
            self, text="Download MP3", height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#e53935", hover_color="#b71c1c",
            command=self._start_download
        )
        self.btn.pack(padx=30, pady=16, fill="x")

        # Progress bar
        self.progress = ctk.CTkProgressBar(self, height=10)
        self.progress.pack(padx=30, fill="x")
        self.progress.set(0)

        # Status label
        self.status_var = ctk.StringVar(value="Ready")
        ctk.CTkLabel(
            self, textvariable=self.status_var,
            font=ctk.CTkFont(size=11), text_color="gray"
        ).pack(pady=(6, 4))

        # Log box
        self.log = ctk.CTkTextbox(
            self, height=160, font=ctk.CTkFont(family="Courier", size=10),
            fg_color="#0d0d0d", text_color="#b0bec5", state="disabled"
        )
        self.log.pack(padx=30, pady=(0, 20), fill="x")

    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            self.status_var.set("Please paste a YouTube URL first.")
            return

        self.btn.configure(state="disabled", text="Downloading...")
        self.progress.set(0)
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.status_var.set("Starting...")
        self._clear_log()

        threading.Thread(target=self._run, args=(url,), daemon=True).start()

    def _run(self, url):
        try:
            cmd = [
                "yt-dlp", "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "-o", os.path.join(SAVE_DIR, "%(title)s.%(ext)s"),
                url,
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                self.after(0, self._append_log, line)

                pct_match = re.search(r"(\d+\.\d+)%", line)
                if pct_match:
                    pct = float(pct_match.group(1)) / 100
                    self.after(0, self._set_progress, pct, line.strip())

            proc.wait()
            self.after(0, self._done, proc.returncode == 0)

        except FileNotFoundError:
            self.after(0, self._append_log, "ERROR: yt-dlp not found. Run: pip install yt-dlp")
            self.after(0, self._done, False)

    def _set_progress(self, pct, label):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(pct)
        self.status_var.set(label)

    def _done(self, success):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(1 if success else 0)
        self.btn.configure(state="normal", text="Download MP3")
        if success:
            self.status_var.set(f"Done!  Saved to {SAVE_DIR}")
            self.url_entry.delete(0, "end")
        else:
            self.status_var.set("Download failed — check the log below.")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _append_log(self, line):
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")


if __name__ == "__main__":
    App().mainloop()
