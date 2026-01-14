"""
Main FastAPI application.
Minimal API surface - only what's needed for a self-serve app.

Endpoints:
- /content/today - Get today's content (core feature)
- /subscription/* - Billing management (self-serve)
- /user/* - Profile management (minimal)
- /webhooks/stripe - Stripe webhook handler
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create app
app = FastAPI(
    title="Cleaning Shorts API",
    description="Self-serve content generator for cleaning businesses",
    version="1.0.0",
    docs_url="/docs" if os.environ.get("APP_ENV") == "development" else None,
    redoc_url=None,
)

# CORS - configure for your frontend domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local dev
        "https://cleanclip.app",  # Production (update this)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "version": "1.0.0"}


# Import and include routers
from .routes import content, subscriptions, webhooks, users

app.include_router(content.router, prefix="/content", tags=["content"])
app.include_router(subscriptions.router, prefix="/subscription", tags=["subscription"])
app.include_router(users.router, prefix="/user", tags=["user"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
