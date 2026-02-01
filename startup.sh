#!/bin/bash

# Initialize database and start the server
echo "Initializing database..."
python -c "from app.db import init_db; init_db(); print('Database initialized successfully!')"

# Import existing sources if they don't exist
echo "Importing sources..."
python -m app.import_sources

echo "Starting server..."
python -m app.run_server
