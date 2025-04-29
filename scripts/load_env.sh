echo "Activate Python virtual environment"
source .venv/bin/activate

echo "Setting up environment variables..."
export PYTHONPATH=.
set -o allexport
source .env
set +o allexport
