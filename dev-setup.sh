# Create venv if not already present
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate the desired venv
source venv/bin/activate

python3 -m pip install --editable .[dev] --upgrade

pre-commit install
