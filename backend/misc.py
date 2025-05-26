import sqlite3
import fitz  # PyMuPDF library for PDF processing
import hashlib
import time
import uuid
import os
from datetime import datetime

def init_db():
    """
    Initializes the SQLite database schema with tables for:
    1. PDF metadata - stores file information and ownership
    2. PDF content - stores extracted text separate from metadata for efficiency
    3. Threads - stores conversation threads between users and AI
    4. Users - stores unique user identifiers
    
    Uses foreign key constraints to maintain referential integrity between tables.
    """
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    
    # Create metadata table for PDF file information
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pdf_metadata (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        upload_date TEXT NOT NULL,
        content_type TEXT NOT NULL,
        file_size INTEGER,
        user_id TEXT
    )
    ''')
    
    # Create content table with foreign key reference to metadata
    # This separation allows efficient storage and retrieval of large text content
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pdf_content (
        pdf_id INTEGER PRIMARY KEY,
        text_content TEXT,
        FOREIGN KEY (pdf_id) REFERENCES pdf_metadata(id) ON DELETE CASCADE
    )
    ''')

    # Create threads table to track conversation sessions between users and AI
    # Each thread is associated with a specific user and PDF context
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS threads (
        thread_id TEXT PRIMARY KEY,
        user_id TEXT,
        pdf_id INTEGER,
        FOREIGN KEY (pdf_id) REFERENCES pdf_content(pdf_id) on DELETE CASCADE
    )
    ''')

    # Create users table to store unique user identifiers
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        user_id TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

def extract_text_from_pdf(file_path):
    """
    Extracts all text content from a PDF file using PyMuPDF (fitz).
    
    Processes each page of the PDF and concatenates the extracted text.
    Provides detailed error information if extraction fails.
    
    Args:
        file_path (str): Path to the PDF file to process
        
    Returns:
        str: Extracted text content from all pages
        
    Raises:
        Exception: If PDF processing fails with detailed error message
    """
    text = ""
    try:
        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        raise Exception(f"Error extracting text: {str(e)}")

def store_pdf_data(filename, file_path, content_type, text_content, file_size, user_id):
    """
    Stores PDF data across multiple database tables in a transactional manner.
    
    Uses a two-step process:
    1. Insert basic metadata information
    2. Insert the extracted text content with a reference to the metadata
    
    Uses transactions to ensure data consistency across tables.
    
    Args:
        filename (str): Original name of the uploaded file
        file_path (str): Path where the file is stored on disk
        content_type (str): MIME type of the file (should be application/pdf)
        text_content (str): Extracted text content from the PDF
        file_size (int): Size of the file in bytes
        user_id (str): Identifier of the user who uploaded the file
        
    Returns:
        int: The ID of the newly created PDF entry
        
    Raises:
        Exception: If database operations fail, transaction is rolled back
    """
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    upload_date = datetime.now().isoformat()
    
    try:
        # First insert metadata
        cursor.execute('''
        INSERT INTO pdf_metadata (filename, file_path, upload_date, content_type, file_size, user_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (filename, file_path, upload_date, content_type, file_size, user_id))
        
        pdf_id = cursor.lastrowid
        
        # Then insert content with the same ID
        cursor.execute('''
        INSERT INTO pdf_content (pdf_id, text_content)
        VALUES (?, ?)
        ''', (pdf_id, text_content))
        
        conn.commit()
        return pdf_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def create_thread(user_id):
    """
    Creates a new conversation thread and associates it with a user.
    
    Thread IDs are generated using a combination of timestamp and user ID 
    to ensure uniqueness while maintaining traceability.
    
    Args:
        user_id (str): Identifier of the user who owns this thread
        
    Returns:
        str: The newly generated thread ID
        
    Raises:
        Exception: If database operations fail, transaction is rolled back
    """
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    
    # Generate a thread ID using current timestamp and user_id
    timestamp = int(time.time() * 1000)  # Current time in milliseconds
    
    if user_id:
        # Combine timestamp and user_id to create a deterministic but unique ID
        thread_seed = f"{timestamp}-{user_id}"
        thread_id = hashlib.md5(thread_seed.encode()).hexdigest()
    else:
        # If no user_id, just use UUID with timestamp
        thread_id = f"{timestamp}-{uuid.uuid4().hex[:8]}"
    
    try:
        cursor.execute('''
        INSERT INTO threads (thread_id, user_id)
        VALUES (?, ?)
        ''', (thread_id, user_id))
        
        conn.commit()
        return thread_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def create_user():
    """
    Creates a new user with a unique identifier.
    
    Generates a UUID for the user and assigns a sequential numeric ID
    for database efficiency.
    
    Returns:
        str: The newly generated user ID (UUID format)
        
    Raises:
        Exception: If database operations fail, transaction is rolled back
    """
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    
    # Generate a unique user_id using UUID
    user_id = uuid.uuid4().hex
    
    try:
        # Get the next available id
        cursor.execute('SELECT MAX(id) FROM users')
        result = cursor.fetchone()
        next_id = 1 if result[0] is None else result[0] + 1
        
        # Insert the new user
        cursor.execute('''
        INSERT INTO users (id, user_id)
        VALUES (?, ?)
        ''', (next_id, user_id))
        
        conn.commit()
        return user_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_pdf_text_by_id(pdf_id):
    """
    Retrieves PDF text content and metadata by ID from the database.
    
    Implements a fallback mechanism:
    1. First checks if text content exists in the database
    2. If not, attempts to extract it from the original file
    3. Stores the extracted text for future use
    
    This approach optimizes for subsequent retrievals while handling cases
    where content may not have been stored initially.
    
    Args:
        pdf_id (int): The ID of the PDF in the database
        
    Returns:
        dict: Dictionary containing PDF metadata and text content
        
    Raises:
        Exception: If PDF not found or extraction/storage fails
    """
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    
    try:
        # First check if the PDF exists in metadata
        cursor.execute('''
        SELECT id, filename, file_path, upload_date, content_type, file_size
        FROM pdf_metadata WHERE id = ?
        ''', (pdf_id,))
        
        metadata_row = cursor.fetchone()
        if not metadata_row:
            raise Exception(f"PDF with ID {pdf_id} not found")
        
        # Get the PDF content
        cursor.execute('SELECT text_content FROM pdf_content WHERE pdf_id = ?', (pdf_id,))
        content_row = cursor.fetchone()
        
        if not content_row:
            # If no content is found, we might need to extract it
            metadata = {
                "id": metadata_row[0],
                "filename": metadata_row[1],
                "file_path": metadata_row[2],
                "upload_date": metadata_row[3],
                "content_type": metadata_row[4],
                "file_size": metadata_row[5],
                "text_content": None
            }
            
            # Try to extract text if we have a file path
            if metadata["file_path"] and os.path.exists(metadata["file_path"]):
                text_content = extract_text_from_pdf(metadata["file_path"])
                
                # Store the extracted text in database for future use
                cursor.execute('''
                INSERT INTO pdf_content (pdf_id, text_content)
                VALUES (?, ?)
                ''', (pdf_id, text_content))
                
                conn.commit()
                metadata["text_content"] = text_content
            
            return metadata
        
        # Return both metadata and content
        return {
            "id": metadata_row[0],
            "filename": metadata_row[1],
            "file_path": metadata_row[2],
            "upload_date": metadata_row[3],
            "content_type": metadata_row[4],
            "file_size": metadata_row[5],
            "text_content": content_row[0]
        }
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()