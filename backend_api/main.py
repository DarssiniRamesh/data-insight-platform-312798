from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# PUBLIC_INTERFACE
def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    app = FastAPI(
        title="Data Insight Platform API",
        description="Backend API for data upload, processing, and visualization",
        version="1.0.0"
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify exact origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


app = create_app()


# PUBLIC_INTERFACE
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint returning a welcome message.
    
    Returns:
        dict: Welcome message with API information
    """
    return {
        "message": "Data Insight Platform API",
        "version": "1.0.0",
        "status": "running"
    }


# PUBLIC_INTERFACE
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for monitoring.
    
    Returns:
        dict: Health status
    """
    return {"status": "ok"}


# PUBLIC_INTERFACE
@app.get("/healthz", tags=["Health"])
async def healthz():
    """
    Alternative health check endpoint for Kubernetes-style monitoring.
    
    Returns:
        dict: Health status
    """
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001, reload=False)
