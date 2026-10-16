#!/bin/zsh
set -e
cd -- "${0:A:h}"
if [[ -f .env ]]; then
  CLIP_PYTHON=${CLIP_PYTHON:-$(sed -n 's/^CLIP_PYTHON=//p' .env | tail -1)}
fi
TASK_PYTHON=${CLIP_PYTHON/#\~/$HOME}
if [[ -z "$TASK_PYTHON" && -x .venv/bin/python3 ]]; then
  TASK_PYTHON=.venv/bin/python3
fi
TASK_PYTHON=${TASK_PYTHON:-$(command -v python3 || true)}
if [[ -z "$TASK_PYTHON" || ! -x "$TASK_PYTHON" ]]; then
  print '未找到 Python 3，请先安装 Python。'
  read -r '?按回车关闭'
  exit 1
fi
if ! "$TASK_PYTHON" -c 'import yt_dlp' 2>/dev/null; then
  print '当前 Python 未安装 yt-dlp。请按 README 安装 requirements.txt 后重试。'
  read -r '?按回车关闭'
  exit 1
fi
"$TASK_PYTHON" server.py
