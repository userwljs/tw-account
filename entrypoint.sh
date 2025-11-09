#!/usr/bin/sh
export TW_ACCOUNT_DATA_PATH=/data
cd /code || exit
if [ -n "$PROXY_HEADERS" ]; then
    uvicorn app:app --proxy-headers --host 0.0.0.0 --port "${BACKEND_PORT:-"8000"}"
else
    uvicorn app:app --host 0.0.0.0 --port "${BACKEND_PORT:-"8000"}"
fi
