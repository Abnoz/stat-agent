# 🐳 Commercial License Analysis System - Docker Deployment

This guide will help you deploy the Commercial License Analysis System using Docker containers.

## 📋 Prerequisites

- Docker (version 20.10+)
- Docker Compose plugin (included in modern Docker installations)
- Your `Commercial_Licenses.xlsx` file
- Azure OpenAI credentials

## 🚀 Quick Start

1. **Clone/Download the project and navigate to the directory**
2. **Place your Excel file** in the project root as `Commercial_Licenses.xlsx`
3. **Run the setup script:**
   ```bash
   chmod +x docker-setup.sh
   ./docker-setup.sh
   ```
4. **Update the `.env` file** with your Azure OpenAI credentials when prompted

## 🏗️ Manual Setup

### 1. Environment Configuration

Create a `.env` file from the template:
```bash
cp .env.docker .env
```

Edit `.env` with your Azure OpenAI credentials:
```env
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT_NAME=your-gpt-model-deployment
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### 2. Build and Start Services

```bash
# Build the application image
docker compose build

# Start the database
docker compose up -d postgres

# Wait for database to be ready (about 10 seconds)
sleep 10

# Import the Excel data (one-time operation)
docker compose --profile import up importer

# Start the API backend
docker compose up -d backend
```

## 🎯 Services Overview

### 🗄️ PostgreSQL Database
- **Container**: `commercial_license_db`
- **Port**: `5432`
- **Database**: `commercial_licenses`
- **User**: `postgres`
- **Password**: `postgres123`

### 🚀 FastAPI Backend
- **Container**: `commercial_license_api`
- **Port**: `8000`
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/

### 📊 Data Importer
- **Container**: `commercial_license_importer`
- **Purpose**: One-time data import from Excel to PostgreSQL
- **Profile**: `import` (only runs when explicitly requested)

## 🔧 Management Commands

### Start Services
```bash
docker compose up -d
```

### Stop Services
```bash
docker compose down
```

### View Logs
```bash
# All services
docker compose logs

# Specific service
docker compose logs backend
docker compose logs postgres
```

### Restart Services
```bash
docker compose restart backend
```

### Re-import Data
```bash
docker compose --profile import up importer
```

### Access Database
```bash
docker exec -it commercial_license_db psql -U postgres -d commercial_licenses
```

## 📡 API Usage

### Basic Query
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "How many licenses are there?", "chart_type": "auto"}'
```

### Arabic Query
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "كم عدد التراخيص الفعالة؟", "chart_type": "pie"}'
```

### Get Examples
```bash
curl -X GET "http://localhost:8000/examples"
```

## 🛠️ Troubleshooting

### Database Connection Issues
```bash
# Check if database is running
docker compose ps postgres

# Check database logs
docker compose logs postgres

# Restart database
docker compose restart postgres
```

### API Issues
```bash
# Check API logs
docker compose logs backend

# Restart API
docker compose restart backend
```

### Data Import Issues
```bash
# Check if Excel file exists
ls -la Commercial_Licenses.xlsx

# Re-run import
docker compose --profile import up importer

# Check import logs
docker compose --profile import logs importer
```

### Reset Everything
```bash
# Stop all services
docker compose down

# Remove volumes (this will delete all data!)
docker compose down -v

# Rebuild and restart
docker compose build
docker compose up -d postgres
sleep 10
docker compose --profile import up importer
docker compose up -d backend
```

## 📊 Monitoring

### Check Service Status
```bash
docker compose ps
```

### Monitor Resource Usage
```bash
docker stats
```

### Database Health
```bash
curl -X GET "http://localhost:8000/database/tables"
```

## 🔐 Security Notes

- Default PostgreSQL credentials are for development only
- Change default passwords in production
- Ensure Azure OpenAI API keys are kept secure
- Consider using Docker secrets for production deployments

## 📂 Volume Mounts

- **Database Data**: `postgres_data` volume for persistent PostgreSQL data
- **Excel File**: `./Commercial_Licenses.xlsx` mounted read-only to containers

## 🌐 Network Configuration

- **Network**: `commercial_network` (bridge driver)
- **Internal Communication**: Services communicate using container names
- **External Access**: Only ports 8000 (API) and 5432 (PostgreSQL) are exposed

## 🚀 Production Considerations

1. **Use proper secrets management**
2. **Set up SSL/TLS certificates**
3. **Configure proper backup strategy**
4. **Set resource limits**
5. **Use health checks**
6. **Configure logging aggregation**
7. **Set up monitoring and alerting** 