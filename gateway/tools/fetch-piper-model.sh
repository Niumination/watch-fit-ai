#!/usr/bin/env bash
# Unduh model suara Bahasa Indonesia untuk Piper TTS (self-host, gratis).
# Hasil: models/id_ID-news.onnx (~60 MB) + berkas .json di sampingnya.
set -euo pipefail

DEST="${1:-models}"
mkdir -p "$DEST"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/id/id_ID/news_tts/medium"

echo "Mengunduh model piper id_ID (news_tts medium)..."
curl -fL --retry 3 -o "$DEST/id_ID-news.onnx" \
    "$BASE/id_ID-news_tts-medium.onnx"
curl -fL --retry 3 -o "$DEST/id_ID-news.onnx.json" \
    "$BASE/id_ID-news_tts-medium.onnx.json"

ls -la "$DEST"/id_ID-news.onnx*
echo "OK — set PIPER_MODEL=models/id_ID-news.onnx dan TTS_BACKEND=piper"
