from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import time
import logging

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(f"Request: {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
            
            # Log response time
            process_time = time.time() - start_time
            logger.info(f"Response: {response.status_code} ({process_time:.3f}s)")
            
            return response
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for static files
        if request.url.path.startswith("/static"):
            return await call_next(request)
        
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean old entries
        self.requests = {
            ip: times for ip, times in self.requests.items()
            if current_time - times[-1] < self.window_seconds
        }
        
        # Check rate limit
        if client_ip in self.requests:
            times = self.requests[client_ip]
            if len(times) >= self.max_requests:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please try again later."},
                )
            times.append(current_time)
        else:
            self.requests[client_ip] = [current_time]
        
        return await call_next(request)


def setup_middleware(app):
    """Setup all middleware for the application."""
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)
