#!/usr/bin/env python3
"""
FastAPI Application for RAG Pipeline

This module provides a FastAPI application that serves both the frontend and
the API endpoints for the RAG pipeline.
"""

import os
import sys
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uuid
from dotenv import load_dotenv
from datetime import datetime

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from insurance_rag import InsuranceRAG

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="RAG Pipeline",
    description="RAG pipeline with frontend and API endpoints",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Mount static files
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Set up templates
templates = Jinja2Templates(directory="src/templates")

# Pydantic models for request and response
class QueryRequest(BaseModel):
    query: str
    stream: bool = True
    session_id: Optional[str] = None

class SetupRequest(BaseModel):
    data_dir: Optional[str] = None

class ConversationResponse(BaseModel):
    id: str
    query: str
    response: str
    timestamp: str
    search_results: List[Dict[str, Any]]

# Store active sessions
active_sessions = {}

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    Serve the frontend.
    
    Args:
        request: FastAPI request
        
    Returns:
        Rendered HTML template
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/setup")
async def setup_pipeline(request: SetupRequest):
    """
    Set up the RAG pipeline.
    
    Args:
        request: Setup request with optional data directory
        
    Returns:
        Setup results
    """
    try:
        ir = InsuranceRAG()
        result = ir.setup_rag_pipeline(request.data_dir)
        return {
            "status": "success",
            "message": "RAG pipeline setup complete",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/query")
async def query(request: QueryRequest):
    """
    Process a query with a non-streaming response.
    
    Args:
        request: Query request with query text and session ID
        
    Returns:
        Query response
    """
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        # Instantiate InsuranceRAG and process the query
        ir = InsuranceRAG()
        response = ir.perform_rag(request.query, stream=False)
        
        # Store the session
        active_sessions[session_id] = {
            "query": request.query,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
        
        return {
            "status": "success",
            "session_id": session_id,
            "response": response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/query/stream")
async def query_stream(request: QueryRequest):
    """
    Process a query with a streaming response.
    
    Args:
        request: Query request with query text and session ID
        
    Returns:
        Streaming response
    """
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        # Instantiate InsuranceRAG and create a generator for the streaming response
        ir = InsuranceRAG()
        response_generator = ir.perform_rag(request.query, stream=True)
        
        async def stream_generator():
            full_response = ""
            for chunk in response_generator:
                full_response += chunk
                yield f"data: {chunk}\n\n"
            
            # Store the session
            active_sessions[session_id] = {
                "query": request.query,
                "response": full_response,
                "timestamp": datetime.now().isoformat()
            }
        
        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conversations/{session_id}")
async def get_conversation(session_id: str):
    """
    Get a conversation by session ID.
    
    Args:
        session_id: Session ID
        
    Returns:
        Conversation details
    """
    try:
        # Check if the session is in memory
        if session_id in active_sessions:
            return active_sessions[session_id]
        
        # Return a 404 response with a more descriptive message
        return JSONResponse(
            status_code=404,
            content={"detail": f"Conversation with ID {session_id} not found"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conversations")
async def get_conversations(limit: int = 10):
    """
    Get recent conversations.
    
    Args:
        limit: Maximum number of conversations to return
        
    Returns:
        List of recent conversations
    """
    try:
        # Return recent conversations from active sessions
        return list(active_sessions.values())[:limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)