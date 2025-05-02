echo -e "⚙️ Activate Python virtual environment"
source .venv/bin/activate

echo -e "⚙️ Setting up environment variables..."
export PYTHONPATH=.
set -o allexport
source .env
set +o allexport

echo -e "🚀 Starting API server..."
fastapi run fb_auto_post/api/endpoints/json_dummy.py --host 0.0.0.0 --port 8000
