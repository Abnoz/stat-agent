#!/bin/bash

echo "🚀 Commercial License Analysis System - Docker Setup"
echo "=================================================="

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker with Compose plugin."
    exit 1
fi

if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.docker .env
    echo "⚠️  Please edit .env file with your Azure OpenAI credentials before continuing!"
    echo "   Required variables:"
    echo "   - AZURE_OPENAI_ENDPOINT"
    echo "   - AZURE_OPENAI_API_KEY"
    echo "   - AZURE_OPENAI_DEPLOYMENT_NAME"
    echo ""
    read -p "Press Enter after updating .env file..."
fi

if [ ! -f "Commercial_Licenses.xlsx" ]; then
    echo "❌ Commercial_Licenses.xlsx not found in current directory."
    echo "   Please place your Excel file in the current directory."
    exit 1
fi

echo "🏗️  Building Docker images..."
docker compose build

echo "🗄️  Starting PostgreSQL database..."
docker compose up -d postgres

echo "⏳ Waiting for database to be ready..."
sleep 10

echo "📊 Importing commercial license data..."
docker compose --profile import up importer

echo "🚀 Starting the API backend..."
docker compose up -d backend

echo ""
echo "✅ Setup complete!"
echo ""
echo "🌐 API is available at: http://localhost:8000"
echo "📋 API Documentation: http://localhost:8000/docs"
echo "🗄️  PostgreSQL is available at: localhost:5432"
echo ""
echo "📝 Example API usage:"
echo "curl -X POST 'http://localhost:8000/query' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"question\": \"How many licenses are there?\", \"chart_type\": \"auto\"}'"
echo ""
echo "🛑 To stop all services: docker compose down"
echo "🔄 To restart: docker compose up -d" 