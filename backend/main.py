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

load_dotenv()
app = FastAPI()
SECRET_KEY = os.getenv("SESSION_SECRET_KEY") or "secret"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Node frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()

@app.get("/")
async def token(request: Request):
    token = request.cookies.get("auth_token")
    if not token:
        user_id = create_user()

        payload = {
            "user": user_id,
            "exp": datetime.utcnow() + timedelta(days=30)
        }
        new_token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        response = JSONResponse(content={"message": "New user created", "user_id": user_id})

        response.set_cookie(
            key="auth_token",
            value=new_token,
            httponly=True,
            max_age=30*24*60*60,
            secure=False,
            samesite="lax"
        )
        
        return response
    else:
        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = decoded["user"]
            conn = sqlite3.connect('chat_database.db')
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, thread_id FROM threads WHERE user_id = ?', (user_id,))
            if not cursor.fetchone():
                # User exists but has no threads yet - still valid
                return JSONResponse(content={"user_id": user_id, "message": "Existing user"})
            conn.close()
            return JSONResponse(content={"user_id": user_id, "message": "Existing user with threads"})
        except:
            raise HTTPException(status_code=401, detail="Could not validate token")

@app.get("/health")
async def health():
    return {"health": "ok"}

@app.post("/upload")
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    if not file.content_type == "application/pdf":
        raise HTTPException(400, detail="Only PDF files are allowed")
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = decoded["user"]
    except:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    file_path = os.path.join(upload_dir, file.filename)
    
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        file_size = os.path.getsize(file_path)
        extracted_text = extract_text_from_pdf(file_path)
        
        # Store in database using the new schema
        pdf_id = store_pdf_data(
            filename=file.filename,
            file_path=file_path,
            content_type=file.content_type,
            text_content=extracted_text,
            file_size=file_size,
            user_id=user_id
        )
        
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

@app.get("/pdfs")
async def get_all_pdfs(request:Request):
    """Retrieve all PDF metadata records (without content)."""
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = decoded["user"]
    except:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

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

@app.get("/pdfs/{pdf_id}")
async def get_pdf_by_id(pdf_id: int, include_content: bool = False):
    """
    Retrieve a specific PDF record by ID.
    Query parameter include_content determines whether to include text content.
    """
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    
    # Get metadata
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
    
    # Get content if requested
    if include_content:
        cursor.execute('SELECT text_content FROM pdf_content WHERE pdf_id = ?', (pdf_id,))
        content_row = cursor.fetchone()
        if content_row:
            pdf["text_content"] = content_row[0]
    
    conn.close()
    return pdf

@app.get("/pdfs/{pdf_id}/content")
async def get_pdf_content(pdf_id: int):
    """Dedicated endpoint just for retrieving the PDF content."""
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    
    # Verify PDF exists
    cursor.execute('SELECT id FROM pdf_metadata WHERE id = ?', (pdf_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(404, detail=f"PDF with ID {pdf_id} not found")
    
    # Get content
    cursor.execute('SELECT text_content FROM pdf_content WHERE pdf_id = ?', (pdf_id,))
    content_row = cursor.fetchone()
    if not content_row:
        conn.close()
        raise HTTPException(404, detail=f"Content for PDF with ID {pdf_id} not found")
    
    conn.close()
    return {"pdf_id": pdf_id, "text_content": content_row[0]}

@app.post("/query")
async def query_chatbot(request: Request):
    token = request.cookies.get("auth_token")
    thread_created=False
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = decoded["user"]
        thread_id = request.headers.get("X-Thread-Id")
        body = await request.json()
        pdf_id = body.get("pdf_id")
        if not thread_id:
            thread_id = create_thread(user_id)
            thread_created = True
        else:
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
    
    messages = body.get("messages", [])
    parsed_messages = chat.parse_messages(messages, pdf_id)
    config = {"configurable": {"thread_id": thread_id}}
    
    # Improve streaming response with appropriate headers and chunk size
    response = StreamingResponse(
        chat.send_msg(parsed_messages, config),
        media_type="text/event-stream",  # Use SSE format for smoother streaming
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Thread-Id": thread_id
        }
    )

    if thread_created:
        response.headers["X-Thread-Created"] = "true"
    # response = await chat.send_msg(parsed_messages, config)
    return response