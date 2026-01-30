# Backend API (FastAPI)

## Overview
Backend API for the Data Insight Platform, providing endpoints for user authentication, file management, data processing, and visualization.

## Getting Started

### Installation
```bash
pip install -r requirements.txt
```

### Running the Application
```bash
# Development mode
uvicorn main:app --host 0.0.0.0 --port 3001 --reload

# Or using Python directly
python main.py
```

### API Endpoints
- `GET /` - Root endpoint with API information
- `GET /health` - Health check endpoint
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation

## Port
The application runs on port 3001 by default.

## Dependencies
- FastAPI: Web framework
- Uvicorn: ASGI server
