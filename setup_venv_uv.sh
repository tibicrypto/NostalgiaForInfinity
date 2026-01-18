#!/bin/bash

# Script to create virtual environment and install freqtrade with hyperopt dependencies using uv

echo "Creating virtual environment with uv..."
uv venv

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing freqtrade..."
uv pip install freqtrade

echo "Installing hyperopt dependencies..."
uv pip install -r requirements-hyperopt.txt

echo "Setup complete! Virtual environment created and dependencies installed."
echo "To activate the environment in future sessions, run: source .venv/bin/activate"