from typing import Union
import os
from datetime import datetime, timedelta
import sqlite3
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import chat
import jwt
from dotenv import load_dotenv
from misc import init_db, extract_text_from_pdf, store_pdf_data, create_thread, create_user
from contextlib import asynccontextmanager

# Load environment variables from .env file
load_dotenv()
# Determine if we're in production environment to set appropriate security settings
is_prod = os.environ.get("ENVIRONMENT") == "production"

app = FastAPI()
# Initialize database on application startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan event handler that runs at application startup and shutdown.
    
    This async context manager:
    1. Executes init_db() when the server starts to ensure database tables exist
    2. Yields control back to FastAPI to run the application
    3. Can perform cleanup when the server shuts down (after the yield)
    
    The @asynccontextmanager decorator transforms this function into a proper
    asynchronous context manager that FastAPI can use for startup/shutdown events.
    
    Args:
        app: FastAPI application instance
    
    Yields:
        None: Control is yielded to FastAPI during the application's lifetime
    """
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

# Get JWT secret key from environment or use default
SECRET_KEY = os.environ.get("SESSION_SECRET_KEY") or "secret"
# Configure frontend URLs for CORS
FRONTEND_URL1 = os.environ.get("FRONTEND_URL1") or "http://localhost:5173"
FRONTEND_URL2 = os.environ.get("FRONTEND_URL2")
FRONTEND_URL3 = os.environ.get("FRONTEND_URL3")
 
# Configure CORS allowed origins based on environment variables
allowed_origins = []
allowed_origins.append("http://localhost:5173")  # Default development URL
if FRONTEND_URL1:
    allowed_origins.append(FRONTEND_URL1)
if FRONTEND_URL2:
    allowed_origins.append(FRONTEND_URL2)
if FRONTEND_URL3:
    allowed_origins.append(FRONTEND_URL3)
allowed_origins = list(set(allowed_origins))  # Remove duplicates

# Set up CORS middleware to allow frontend to connect to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint - handles user authentication via JWT tokens
@app.get("/")
async def token(request: Request):
    """
    Authentication endpoint that:
    1. Creates new users if no token exists in cookies
    2. Validates existing tokens and returns user details
    3. Issues JWT token stored in an HTTP-only cookie for session management
    
    Returns:
        JSONResponse: Response containing user details and authentication status
    """
    token = request.cookies.get("auth_token")
    if not token:
        # Create new user and token if no token exists
        user_id = create_user()
        payload = {
            "user": user_id,
            "exp": datetime.now() + timedelta(days=30)
        }
        new_token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        response = JSONResponse(content={"message": "New user created", "user_id": user_id})
        # Set secure cookie with authentication token
        response.set_cookie(
            key="auth_token",
            value=new_token,
            httponly=True,  # Prevents JavaScript access to cookie
            max_age=30*24*60*60,  # 30 days
            secure=is_prod,  # HTTPS only in production
            samesite="None" if is_prod else "Lax"  # Cross-site cookie handling
        )
        return response
    else:
        try:
            # Validate existing token
            decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = decoded["user"]
            # Check if user has existing chat threads
            conn = sqlite3.connect('chat_database.db')
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, thread_id FROM threads WHERE user_id = ?', (user_id,))
            if not cursor.fetchone():
                return JSONResponse(content={"user_id": user_id, "message": "Existing user"})
            conn.close()
            return JSONResponse(content={"user_id": user_id, "message": "Existing user with threads"})
        except:
            raise HTTPException(status_code=401, detail="Could not validate token")

# Simple health check endpoint for monitoring
@app.get("/health")
async def health():
    """
    Health check endpoint to verify API is running.
    
    Returns:
        dict: Simple health status
    """
    return {"health": "ok"}

# PDF upload endpoint
@app.post("/upload")
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    """
    Handles PDF file uploads:
    1. Validates user authentication via token
    2. Checks that file is a valid PDF
    3. Stores file on disk
    4. Extracts text content from PDF
    5. Saves PDF metadata and text content to database
    
    Args:
        request: The HTTP request containing auth token
        file: The uploaded PDF file
    
    Returns:
        JSONResponse: Response containing PDF details including a preview of extracted text
        
    Raises:
        HTTPException: For authentication, file type, or processing errors
    """
    # Validate file type
    if not file.content_type == "application/pdf":
        raise HTTPException(400, detail="Only PDF files are allowed")
    
    # Check authentication
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = decoded["user"]
    except:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    # Ensure upload directory exists
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    file_path = os.path.join(upload_dir, file.filename)
    
    try:
        # Save file to disk
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        # Get file size and extract text content
        file_size = os.path.getsize(file_path)
        extracted_text = extract_text_from_pdf(file_path)
        if not extracted_text:
            raise HTTPException(500, detail="pdf file has no text content")
        
        # Store PDF metadata and content in database
        pdf_id = store_pdf_data(
            filename=file.filename,
            file_path=file_path,
            content_type=file.content_type,
            text_content=extracted_text,
            file_size=file_size,
            user_id=user_id
        )
        
        # Return PDF details with text preview
        return JSONResponse(
            content={
                "id": pdf_id,
                "filename": file.filename,
                "content_type": file.content_type,
                "file_path": file_path,
                "file_size": file_size,
                "message": "PDF uploaded successfully",
                "text_preview": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
            },
            status_code=200
        )
    except Exception as e:
        raise HTTPException(500, detail=f"Error processing PDF: {str(e)}")

# Get all PDFs for the authenticated user
@app.get("/pdfs")
async def get_all_pdfs(request: Request):
    """
    Retrieves all PDFs uploaded by the authenticated user.
    
    Args:
        request: The HTTP request containing auth token
    
    Returns:
        dict: List of PDF metadata for the user
    
    Raises:
        HTTPException: For authentication errors
    """
    # Check authentication
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = decoded["user"]
    except:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    # Query database for user's PDFs
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, filename, file_path, upload_date, content_type, file_size 
    FROM pdf_metadata WHERE user_id = ?
    ''', (user_id,))
    
    pdfs = []
    for row in cursor.fetchall():
        pdf = {
            "id": row[0],
            "filename": row[1],
            "file_path": row[2],
            "upload_date": row[3],
            "content_type": row[4],
            "file_size": row[5]
        }
        pdfs.append(pdf)
    
    conn.close()
    return {"pdfs": pdfs}

# Get a specific PDF by ID
@app.get("/pdfs/{pdf_id}")
async def get_pdf_by_id(pdf_id: int, include_content: bool = False):
    """
    Retrieves metadata for a specific PDF by ID, with optional text content.
    
    Args:
        pdf_id: The ID of the PDF to retrieve
        include_content: Whether to include the extracted text content
    
    Returns:
        dict: PDF metadata and optionally text content
        
    Raises:
        HTTPException: If PDF not found
    """
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, filename, file_path, upload_date, content_type, file_size 
    FROM pdf_metadata WHERE id = ?
    ''', (pdf_id,))
    
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, detail=f"PDF with ID {pdf_id} not found")
    
    pdf = {
        "id": row[0],
        "filename": row[1],
        "file_path": row[2],
        "upload_date": row[3],
        "content_type": row[4],
        "file_size": row[5]
    }
    
    # Include text content if requested
    if include_content:
        cursor.execute('SELECT text_content FROM pdf_content WHERE pdf_id = ?', (pdf_id,))
        content_row = cursor.fetchone()
        if content_row:
            pdf["text_content"] = content_row[0]
    
    conn.close()
    return pdf

# Get just the text content of a specific PDF
@app.get("/pdfs/{pdf_id}/content")
async def get_pdf_content(pdf_id: int):
    """
    Retrieves only the extracted text content for a specific PDF.
    
    Args:
        pdf_id: The ID of the PDF to retrieve content for
        
    Returns:
        dict: PDF ID and text content
        
    Raises:
        HTTPException: If PDF or content not found
    """
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM pdf_metadata WHERE id = ?', (pdf_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(404, detail=f"PDF with ID {pdf_id} not found")
    
    cursor.execute('SELECT text_content FROM pdf_content WHERE pdf_id = ?', (pdf_id,))
    content_row = cursor.fetchone()
    if not content_row:
        conn.close()
        raise HTTPException(404, detail=f"Content for PDF with ID {pdf_id} not found")
    
    conn.close()
    return {"pdf_id": pdf_id, "text_content": content_row[0]}

# Main chat query endpoint with streaming response
@app.post("/query")
async def query_chatbot(request: Request):
    """
    Main endpoint for chatbot interaction:
    1. Authenticates user
    2. Creates or retrieves conversation thread
    3. Processes messages with the AI
    4. Returns AI response as a streaming event
    
    Features:
    - Thread persistence across sessions
    - Streaming response for real-time display
    - PDF context for relevant answers
    
    Args:
        request: The HTTP request containing auth token, thread ID and messages
        
    Returns:
        StreamingResponse: AI response streamed as text chunks
        
    Raises:
        HTTPException: For authentication or processing errors
    """
    token = request.cookies.get("auth_token")
    thread_created = False
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    try:
        # Authenticate user and get or create thread
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = decoded["user"]
        thread_id = request.headers.get("X-Thread-Id")
        body = await request.json()
        pdf_id = body.get("pdf_id")
        
        if not thread_id:
            # Create new thread if none provided
            thread_id = create_thread(user_id)
            thread_created = True
        else:
            # Validate thread belongs to user
            conn = sqlite3.connect('chat_database.db')
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, thread_id, pdf_id FROM threads WHERE thread_id = ?', (thread_id,))
            thread_row = cursor.fetchone()
            if not thread_row or thread_row[0] != user_id:
                raise HTTPException(status_code=401, detail="Unauthorized")
            pdf_id = thread_row[2]
            conn.close()
    except:
        raise HTTPException(status_code=401, detail="Could not validate token")
    
    # Process messages and prepare chat context
    messages = body.get("messages", [])
    parsed_messages = chat.parse_messages(messages, pdf_id)
    config = {"configurable": {"thread_id": thread_id}}
    
    # Create streaming response with proper headers
    response = StreamingResponse(
        chat.send_msg(parsed_messages, config),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Thread-Id": thread_id
        }
    )

    if thread_created:
        response.headers["X-Thread-Created"] = "true"
    return response