#!/bin/bash

# Create main project directory
mkdir -p oauth_service/{oauth_service,tests,examples}

# Create package subdirectories
cd oauth_service/oauth_service
mkdir -p {core,platforms,routes,models,utils}

# Create __init__.py files
touch __init__.py
touch {core,platforms,routes,models,utils}/__init__.py

# Create necessary directories for data
mkdir -p ../../data/.keys

# Set permissions for keys directory
chmod 700 ../../data/.keys

# Create test directories
cd ../tests
mkdir -p {core,platforms,routes,models,utils}

echo "Project structure created successfully!"
echo "Next steps:"
echo "1. Copy all the provided files to their respective directories"
echo "2. Run 'pip install -e .' from the project root"
echo "3. Create and configure your .env file"
echo "4. Initialize the database"
