# Create venv if not already present
if [ ! -d "venv" ]; then
    python3 -m pip install virtualenv
    python3 -m virtualenv venv
fi

# Activate the desired venv
source venv/bin/activate

python3 -m pip install --editable .[dev] --upgrade

pre-commit install
