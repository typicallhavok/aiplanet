import sqlite3
import fitz
import hashlib
import time
import uuid
import os
from datetime import datetime

# Initialize SQLite database with separate tables
def init_db():
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    
    # Create metadata table
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
    
    # Create content table with foreign key reference
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pdf_content (
        pdf_id INTEGER PRIMARY KEY,
        text_content TEXT,
        FOREIGN KEY (pdf_id) REFERENCES pdf_metadata(id) ON DELETE CASCADE
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS threads (
        thread_id TEXT PRIMARY KEY,
        user_id TEXT,
        pdf_id INTEGER,
        FOREIGN KEY (pdf_id) REFERENCES pdf_content(pdf_id) on DELETE CASCADE
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        user_id TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

def extract_text_from_pdf(file_path):
    """Extract text content from a PDF file using PyMuPDF."""
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
    """Store PDF data in separate metadata and content tables."""
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
    Create a new thread and associate it with a user if provided.
    The thread_id is generated using the current time and user_id.
    Returns the thread_id.
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
    Create a new user with a unique user_id.
    Returns the user_id.
    """
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    
    # Generate a unique user_id
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
    Retrieve the extracted text content of a PDF by its ID.
    
    Args:
        pdf_id (int): The ID of the PDF in the database.
        
    Returns:
        dict: A dictionary containing the PDF's metadata and text content.
        
    Raises:
        Exception: If the PDF with the given ID is not found or another error occurs.
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