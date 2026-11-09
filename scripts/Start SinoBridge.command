#!/bin/bash
# Double-click on macOS. Never sends files to cloud by itself.
set -e
cd "$(dirname "$0")/.."
echo "SinoBridge — Dịch sách trên máy của bạn"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Cần Python 3.10+ từ python.org hoặc Homebrew trước khi chạy."
  read -r -p "Nhấn Enter để đóng..."
  exit 1
fi
if [ ! -f ".venv/.sinobridge-ready" ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -e '.[all]' || {
    echo "Không cài được thư viện, kiểm tra kết nối mạng / Python rồi thử lại."
    read -r -p "Nhấn Enter để đóng..."
    exit 1
  }
  touch ".venv/.sinobridge-ready"
fi
.venv/bin/python -m sinobridge.webapp --open
