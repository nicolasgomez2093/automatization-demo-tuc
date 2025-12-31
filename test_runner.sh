#!/bin/bash

echo "🧪 Running Backend Tests..."
echo "================================"

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run tests
pytest tests/ -v --tb=short

# Clean up test database
rm -f test.db

echo ""
echo "✅ Tests completed!"
