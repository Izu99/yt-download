#!/usr/bin/env python3
import customtkinter as ctk
import subprocess
import threading
import os
import re

AUDIO_DIR = os.path.expanduser("~/Music/YouTube-MP3")
VIDEO_DIR = os.path.expanduser("~/Videos/YouTube")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

AUDIO_QUALITIES = ["320 kbps", "192 kbps", "128 kbps"]
VIDEO_QUALITIES = ["Best available", "1080p", "720p", "480p", "360p"]

# --no-playlist only strips the list from a watch?v=...&list=... URL; a bare
# playlist?list=... URL still grabs everything, so pin it with --playlist-items.
PLAYLIST_MODES = {
    # Works for both a bare playlist?list=... URL and a watch?v=...&list=... one.
    "First item only":        ["--yes-playlist", "--playlist-items", "1"],
    # Only meaningful on watch?v=...&list=... — grabs the linked video, not item 1.
    "Just the linked video":  ["--no-playlist"],
    "Whole playlist":         ["--yes-playlist"],
    "Custom range…":          None,  # filled from the items entry
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ---- Design palette --------------------------------------------------------
# One place for every colour so the whole UI stays visually consistent.
BG       = "#0e0f13"   # window background
CARD     = "#171a21"   # main content card
FIELD    = "#20242e"   # inputs / dropdowns / segmented track
BORDER   = "#2b3038"   # hairline borders
TEXT     = "#e8eaed"   # primary text
MUTED    = "#8b929e"   # secondary / helper text
ACCENT   = "#4f9cff"   # blue accents (labels, focus, links)
BRAND    = "#ff3b30"   # YouTube red — primary action
BRAND_HI = "#d32f2f"   # red hover
NEUTRAL  = "#2b3038"   # secondary button
NEUTRAL_HI = "#363c46"
LOG_BG   = "#0b0c0f"
SUCCESS  = "#3ddc84"   # completion highlight (green)
SUCCESS_BG = "#12351f"
ERROR    = "#ff5a4d"   # failure highlight (red)
ERROR_BG = "#3a1512"

PAD = 26  # shared horizontal padding inside the card

CORNER = 12


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Downloader")
        self.geometry("580x780")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self.proc = None
        self.cancelled = False

        self._build_ui()

    # ---- UI helpers --------------------------------------------------------

    def _section_label(self, parent, text):
        """Small muted upper-case caption above a control."""
        return ctk.CTkLabel(
            parent, text=text.upper(),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=MUTED, anchor="w",
        )

    # ---- UI ----------------------------------------------------------------

    def _build_ui(self):
        # Everything lives inside one rounded card so the window edge breathes.
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=18, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # ---- Header -------------------------------------------------------
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=PAD, pady=(22, 2))

        # Red accent chip next to the title for a bit of brand identity.
        ctk.CTkLabel(
            header, text="  ▶  ", font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=BRAND, text_color="#ffffff", corner_radius=8,
        ).pack(side="left")
        ctk.CTkLabel(
            header, text="YouTube Downloader",
            font=ctk.CTkFont(size=21, weight="bold"), text_color=TEXT,
        ).pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            card, text="Paste a link, pick a format, hit Download.",
            font=ctk.CTkFont(size=13), text_color=MUTED,
        ).pack(anchor="w", padx=PAD + 2, pady=(0, 16))

        # ---- Mode switch --------------------------------------------------
        self.mode = ctk.StringVar(value="Audio (MP3)")
        ctk.CTkSegmentedButton(
            card, values=["Audio (MP3)", "Video (MP4)"],
            variable=self.mode, command=self._on_mode_change,
            height=40, corner_radius=CORNER,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=FIELD, unselected_color=FIELD,
            selected_color=BRAND, selected_hover_color=BRAND_HI,
            unselected_hover_color=NEUTRAL,
        ).pack(padx=PAD, fill="x")

        # ---- URL entry ----------------------------------------------------
        url_frame = ctk.CTkFrame(card, fg_color="transparent")
        url_frame.pack(fill="x", padx=PAD, pady=(16, 0))
        self._section_label(url_frame, "YouTube URL").pack(anchor="w")
        self.url_entry = ctk.CTkEntry(
            url_frame, placeholder_text="https://youtu.be/…",
            height=42, corner_radius=CORNER, font=ctk.CTkFont(size=13),
            fg_color=FIELD, border_color=BORDER, border_width=1,
        )
        self.url_entry.pack(fill="x", pady=(6, 0))
        self.url_entry.bind("<Return>", lambda _e: self._start_download())

        # ---- Quality picker ----------------------------------------------
        quality_frame = ctk.CTkFrame(card, fg_color="transparent")
        quality_frame.pack(fill="x", padx=PAD, pady=(12, 0))
        self._section_label(quality_frame, "Quality").pack(anchor="w")
        self.quality = ctk.CTkOptionMenu(
            quality_frame, values=AUDIO_QUALITIES, height=38,
            corner_radius=CORNER, font=ctk.CTkFont(size=13),
            fg_color=FIELD, button_color=NEUTRAL, button_hover_color=NEUTRAL_HI,
        )
        self.quality.pack(fill="x", pady=(6, 0))

        # ---- Extras -------------------------------------------------------
        self.embed_meta = ctk.CTkCheckBox(
            card, text="Embed thumbnail + metadata",
            font=ctk.CTkFont(size=12), text_color=TEXT,
            fg_color=BRAND, hover_color=BRAND_HI,
            border_color=BORDER, corner_radius=6,
        )
        self.embed_meta.select()
        self.embed_meta.pack(anchor="w", padx=PAD, pady=(14, 0))

        # ---- Playlist handling -------------------------------------------
        pl_frame = ctk.CTkFrame(card, fg_color="transparent")
        pl_frame.pack(fill="x", padx=PAD, pady=(12, 0))
        self._section_label(pl_frame, "Playlist links").pack(anchor="w")

        pl_row = ctk.CTkFrame(pl_frame, fg_color="transparent")
        pl_row.pack(fill="x", pady=(6, 0))
        self.playlist_mode = ctk.CTkOptionMenu(
            pl_row, values=list(PLAYLIST_MODES), height=38,
            corner_radius=CORNER, font=ctk.CTkFont(size=13),
            fg_color=FIELD, button_color=NEUTRAL, button_hover_color=NEUTRAL_HI,
            command=self._on_playlist_mode_change,
        )
        self.playlist_mode.pack(side="left", fill="x", expand=True)
        self.items_entry = ctk.CTkEntry(
            pl_row, placeholder_text="1-5,8", width=120, height=38,
            corner_radius=CORNER, font=ctk.CTkFont(size=13), state="disabled",
            fg_color=FIELD, border_color=BORDER, border_width=1,
        )
        self.items_entry.pack(side="left", padx=(10, 0))

        # ---- Save folder row (own subtle strip) --------------------------
        folder_frame = ctk.CTkFrame(card, fg_color=FIELD, corner_radius=CORNER)
        folder_frame.pack(fill="x", padx=PAD, pady=(16, 0))
        ctk.CTkLabel(
            folder_frame, text="Save to", font=ctk.CTkFont(size=11, weight="bold"),
            text_color=MUTED,
        ).pack(side="left", padx=(12, 6), pady=8)
        self.folder_var = ctk.StringVar(value=AUDIO_DIR)
        ctk.CTkLabel(
            folder_frame, textvariable=self.folder_var,
            font=ctk.CTkFont(size=11), text_color=ACCENT,
        ).pack(side="left")
        ctk.CTkButton(
            folder_frame, text="Open", width=60, height=26, corner_radius=8,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=NEUTRAL, hover_color=NEUTRAL_HI, command=self._open_folder,
        ).pack(side="right", padx=8, pady=6)

        # ---- Action buttons ----------------------------------------------
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=PAD, pady=(16, 0))
        self.btn = ctk.CTkButton(
            btn_row, text="Download MP3", height=46, corner_radius=CORNER,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=BRAND, hover_color=BRAND_HI, command=self._start_download,
        )
        self.btn.pack(side="left", fill="x", expand=True)
        self.cancel_btn = ctk.CTkButton(
            btn_row, text="Cancel", width=96, height=46, corner_radius=CORNER,
            font=ctk.CTkFont(size=13, weight="bold"), state="disabled",
            fg_color=NEUTRAL, hover_color=NEUTRAL_HI, command=self._cancel,
        )
        self.cancel_btn.pack(side="left", padx=(10, 0))

        # ---- Progress + status -------------------------------------------
        self.progress = ctk.CTkProgressBar(
            card, height=8, corner_radius=6, progress_color=BRAND, fg_color=FIELD,
        )
        self.progress.pack(padx=PAD, pady=(18, 0), fill="x")
        self.progress.set(0)

        self.status_var = ctk.StringVar(value="Ready")
        self.status_label = ctk.CTkLabel(
            card, textvariable=self.status_var,
            font=ctk.CTkFont(size=11), text_color=MUTED,
        )
        self.status_label.pack(pady=(8, 6))

        # ---- Log box ------------------------------------------------------
        self.log = ctk.CTkTextbox(
            card, height=150, corner_radius=CORNER,
            font=ctk.CTkFont(family="DejaVu Sans Mono", size=10),
            fg_color=LOG_BG, text_color="#9aa4b2", border_color=BORDER,
            border_width=1, state="disabled",
        )
        self.log.pack(padx=PAD, pady=(0, PAD), fill="both", expand=True)

        # Colour tags for highlighted result banners in the log. CTkTextbox
        # wraps a plain tk.Text, so drive tags through the underlying widget.
        self.log._textbox.tag_config(
            "success", foreground=SUCCESS, background=SUCCESS_BG,
            selectbackground=SUCCESS_BG, spacing1=4, spacing3=4,
        )
        self.log._textbox.tag_config(
            "error", foreground=ERROR, background=ERROR_BG,
            selectbackground=ERROR_BG, spacing1=4, spacing3=4,
        )

    def _is_video(self):
        return self.mode.get().startswith("Video")

    def _on_mode_change(self, _value=None):
        if self._is_video():
            self.quality.configure(values=VIDEO_QUALITIES)
            self.quality.set(VIDEO_QUALITIES[0])
            self.folder_var.set(VIDEO_DIR)
            self.btn.configure(text="Download Video")
        else:
            self.quality.configure(values=AUDIO_QUALITIES)
            self.quality.set(AUDIO_QUALITIES[0])
            self.folder_var.set(AUDIO_DIR)
            self.btn.configure(text="Download MP3")

    def _on_playlist_mode_change(self, value):
        if value == "Custom range…":
            self.items_entry.configure(state="normal")
            self.items_entry.focus()
        else:
            self.items_entry.configure(state="disabled")

    def _open_folder(self):
        subprocess.Popen(["xdg-open", self.folder_var.get()])

    # ---- download ----------------------------------------------------------

    def _build_cmd(self, url):
        save_dir = self.folder_var.get()
        mode = self.playlist_mode.get()

        if mode == "Custom range…":
            items = self.items_entry.get().strip()
            if not items:
                raise ValueError("Enter a range like 1-5,8 — or pick another playlist option.")
            playlist_args = ["--yes-playlist", "--playlist-items", items]
        else:
            playlist_args = PLAYLIST_MODES[mode]

        # Only fan out into a per-playlist subfolder when more than one item can
        # land; a single file shouldn't get its own directory.
        if mode in ("Whole playlist", "Custom range…"):
            out = os.path.join(save_dir, "%(playlist_title)s", "%(playlist_index)s - %(title)s.%(ext)s")
        else:
            out = os.path.join(save_dir, "%(title)s.%(ext)s")

        cmd = ["yt-dlp", "--newline", "-o", out] + playlist_args

        if self._is_video():
            height = re.match(r"(\d+)p", self.quality.get())
            if height:
                h = height.group(1)
                fmt = f"bv*[height<={h}]+ba/b[height<={h}]"
            else:
                fmt = "bv*+ba/b"
            cmd += ["-f", fmt, "--merge-output-format", "mp4"]
            if self.embed_meta.get():
                cmd += ["--embed-thumbnail", "--embed-metadata"]
        else:
            # yt-dlp's --audio-quality takes a VBR level (0-9) or a bitrate like
            # "192K"; feed it the bitrate straight from the dropdown.
            kbps = self.quality.get().split()[0]
            cmd += ["-x", "--audio-format", "mp3", "--audio-quality", f"{kbps}K"]
            if self.embed_meta.get():
                cmd += ["--embed-thumbnail", "--embed-metadata"]

        cmd.append(url)
        return cmd

    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            self.status_var.set("Please paste a YouTube URL first.")
            return

        # Built up front so a bad playlist range reports in the UI rather than
        # blowing up on the worker thread with the buttons stuck disabled.
        try:
            cmd = self._build_cmd(url)
        except ValueError as e:
            self.status_var.set(str(e))
            return

        self.cancelled = False
        self.btn.configure(state="disabled", text="Downloading...")
        self.cancel_btn.configure(state="normal")
        self.progress.set(0)
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.status_label.configure(text_color=MUTED)
        self.status_var.set("Starting...")
        self._clear_log()

        threading.Thread(target=self._run, args=(cmd,), daemon=True).start()

    def _cancel(self):
        self.cancelled = True
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.status_var.set("Cancelling…")

    def _run(self, cmd):
        try:
            self.after(0, self._append_log, "$ " + " ".join(cmd) + "\n")

            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )

            for line in self.proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                self.after(0, self._append_log, line)

                # ffmpeg re-encodes Opus -> MP3 and muxes video+audio without
                # emitting progress, so the UI would otherwise sit frozen at
                # 100% for the whole conversion.
                if line.startswith("[ExtractAudio]"):
                    self.after(0, self._set_busy, "Converting to MP3 — this takes a while on long tracks…")
                    continue
                if line.startswith("[Merger]"):
                    self.after(0, self._set_busy, "Merging video + audio…")
                    continue
                if line.startswith(("[EmbedThumbnail]", "[Metadata]")):
                    self.after(0, self._set_busy, "Writing tags…")
                    continue

                pct_match = re.search(r"(\d+\.\d+)%", line)
                if pct_match:
                    pct = float(pct_match.group(1)) / 100
                    self.after(0, self._set_progress, pct, line.strip())

            self.proc.wait()
            self.after(0, self._done, self.proc.returncode == 0)

        except FileNotFoundError:
            self.after(0, self._append_log, "ERROR: yt-dlp not found. Run: pip install yt-dlp")
            self.after(0, self._done, False)

    def _set_busy(self, message):
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.status_var.set(message)

    def _set_progress(self, pct, label):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(pct)
        self.status_var.set(label)

    def _done(self, success):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(1 if success else 0)
        self.cancel_btn.configure(state="disabled")
        self.btn.configure(
            state="normal",
            text="Download Video" if self._is_video() else "Download MP3",
        )
        if self.cancelled:
            self.status_label.configure(text_color=MUTED)
            self.status_var.set("Cancelled.")
        elif success:
            folder = self.folder_var.get()
            self.status_label.configure(text_color=SUCCESS)
            self.status_var.set(f"✓  Done — saved to {folder}")
            # Highlighted completion banner so a finished download is obvious
            # at a glance amid the yt-dlp log noise.
            self._append_log("", )
            self._append_log(f"  ✓  DOWNLOAD COMPLETE  —  saved to {folder}  ", "success")
            self.url_entry.delete(0, "end")
        else:
            self.status_label.configure(text_color=ERROR)
            self.status_var.set("✗  Download failed — check the log below.")
            self._append_log("", )
            self._append_log("  ✗  DOWNLOAD FAILED  —  see the log above  ", "error")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _append_log(self, line, tag=None):
        self.log.configure(state="normal")
        if tag:
            self.log._textbox.insert("end", line + "\n", tag)
        else:
            self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")


if __name__ == "__main__":
    App().mainloop()
