#!/usr/bin/env python3
"""Download a YouTube video and save it as MP4.

Usage:
1) Run the script.
2) Paste a YouTube URL when prompted.
3) The video is downloaded as .mp4 in the selected output folder.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
	from yt_dlp import YoutubeDL
except ImportError:
	print("Missing dependency: yt-dlp")
	print("Install it with: pip install yt-dlp")
	sys.exit(1)


def _build_ydl_opts(output_dir: Path, prefer_android_client: bool = False) -> dict:
	"""Build yt-dlp options tuned for stable MP4 downloads."""
	player_clients = ["android", "web"] if prefer_android_client else ["web", "android"]

	return {
		# Prefer MP4-friendly formats while allowing a safe fallback.
		"format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/18/b",
		"outtmpl": str(output_dir / "%(title)s.%(ext)s"),
		"merge_output_format": "mp4",
		"noplaylist": True,
		"quiet": False,
		"retries": 10,
		"fragment_retries": 10,
		"extractor_args": {
			"youtube": {
				"player_client": player_clients,
			}
		},
	}


def download_youtube_mp4(url: str, output_dir: Path) -> None:
	"""Download a YouTube URL and save it as an MP4 file."""
	output_dir.mkdir(parents=True, exist_ok=True)

	try:
		with YoutubeDL(_build_ydl_opts(output_dir=output_dir, prefer_android_client=False)) as ydl:
			ydl.download([url])
		print(f"Downloaded successfully to: {output_dir.resolve()}")
	except Exception as exc:
		if "403" in str(exc):
			print("First attempt got HTTP 403. Retrying with alternate YouTube client...")
			try:
				with YoutubeDL(_build_ydl_opts(output_dir=output_dir, prefer_android_client=True)) as ydl:
					ydl.download([url])
				print(f"Downloaded successfully to: {output_dir.resolve()}")
				return
			except Exception as retry_exc:
				exc = retry_exc

		print("Download failed.")
		print("If ffmpeg is missing, install it (macOS: brew install ffmpeg).")
		print("Also update tools: pip install -U yt-dlp and use Python 3.10+.")
		print(f"Reason: {exc}")
		sys.exit(1)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Download YouTube videos as MP4")
	parser.add_argument(
		"url",
		nargs="?",
		help="YouTube video URL. If not provided, script will ask for it.",
	)
	parser.add_argument(
		"-o",
		"--output",
		default="downloads",
		help="Output folder (default: downloads)",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	url = args.url or input("Paste YouTube URL: ").strip()

	if not url:
		print("No URL provided.")
		sys.exit(1)

	download_youtube_mp4(url=url, output_dir=Path(args.output))


if __name__ == "__main__":
	main()
