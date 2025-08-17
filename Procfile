web: gunicorn --bind 0.0.0.0:$PORT app:app --timeout 180 --workers 2 --worker-class sync --max-requests 1000 --max-requests-jitter 100
