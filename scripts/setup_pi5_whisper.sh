#!/usr/bin/env bash
set -euo pipefail

MODEL_SIZE="${BUDDYBOT_VOICE_LOCAL_WHISPER_MODEL:-tiny}"
DEVICE="${BUDDYBOT_VOICE_LOCAL_WHISPER_DEVICE:-cpu}"
COMPUTE_TYPE="${BUDDYBOT_VOICE_LOCAL_WHISPER_COMPUTE_TYPE:-int8}"

echo "[whisper] installing faster-whisper"
pip3 install --quiet --break-system-packages faster-whisper 2>/dev/null || pip3 install --quiet faster-whisper

echo "[whisper] preloading model: ${MODEL_SIZE} (${DEVICE}/${COMPUTE_TYPE})"
python3 - "$MODEL_SIZE" "$DEVICE" "$COMPUTE_TYPE" <<'PY'
import sys

from faster_whisper import WhisperModel

model_size, device, compute_type = sys.argv[1:4]
WhisperModel(model_size, device=device, compute_type=compute_type)
print(f"[whisper] ready: {model_size} ({device}/{compute_type})")
PY

echo "[whisper] done"
