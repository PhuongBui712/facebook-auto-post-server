echo "Activate Python virtual environment"
source .venv/bin/activate

echo "Setting up environment variables..."
export PYTHONPATH=.
set -o allexport
source .env
set +o allexport

echo "Starting API server..."
fastapi run fb_auto_post/api/endpoints/dummy.py --host 0.0.0.0 --port 8000
