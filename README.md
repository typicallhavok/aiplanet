# AI planet
**Full-stack application that allows users to upload PDF documents and ask questions regarding the content of these documents**
Heres a [demo](https://drive.google.com/file/d/1gGq_EMKyZp-JlWxku7_eEDYRfKPBOGX3/view?usp=sharing)

## Data Flow

1.  **User Authentication**
    
    -   On first visit, a new user is created and assigned a JWT token
    -   Token is stored as an HTTP-only cookie
    -   Subsequent requests include token validation
2.  **PDF Management Flow**
    
    -   User uploads a PDF via the Navbar component
    -   Backend validates, processes, and stores the file
    -   PDF metadata is returned to frontend and displayed in dropdown
    -   User selects a PDF from the dropdown to set context for questions
3.  **Chat Interaction Flow**
    
    -   User enters a question about the selected PDF
    -   Request is sent to backend with current message history and PDF ID
    -   Backend retrieves PDF content as context for the AI
    -   AI generates a response based on PDF content and conversation history
    -   Response is streamed back to frontend for real-time display
    -   Messages are displayed with appropriate styling and markdown formatting

## Security Considerations

-   JWT-based authentication with HTTP-only cookies
-   Environment-specific security settings (production vs. development)
-   CORS configuration to control cross-origin requests
-   Content type validation for file uploads
-   Thread ownership validation to prevent unauthorized access
# API Routes Documentation

## Authentication and Session Management

### `GET /`
- **Purpose**: Authentication endpoint for user session management
- **Authentication**: Optional (creates new user if not authenticated)
- **Response**: User details with authentication status
- **Actions**:
  - Creates new users when no token exists
  - Validates existing tokens
  - Issues JWT tokens in HTTP-only cookies

## System Status

### `GET /health`
- **Purpose**: Simple health check endpoint for monitoring
- **Authentication**: None
- **Response**: Basic health status object `{"health": "ok"}`
- **Use case**: System monitoring and uptime verification

## PDF Management

### `POST /upload`
- **Purpose**: Upload and process PDF documents
- **Authentication**: Required
- **Parameters**: PDF file (multipart/form-data)
- **Response**: PDF details including ID, metadata, and text preview
- **Actions**:
  - Validates PDF file type
  - Extracts text from PDF
  - Stores file on disk and metadata in database

### `GET /pdfs`
- **Purpose**: Retrieve all PDFs for the authenticated user
- **Authentication**: Required
- **Response**: List of PDF metadata objects
- **Use case**: Display available documents in UI

### `GET /pdfs/{pdf_id}`
- **Purpose**: Get metadata for a specific PDF by ID
- **Authentication**: None (but typically used with authenticated sessions)
- **Parameters**: 
  - `pdf_id`: ID of the PDF to retrieve
  - `include_content` (optional query param): Whether to include extracted text content
- **Response**: PDF metadata object
- **Error**: 404 if PDF not found

### `GET /pdfs/{pdf_id}/content`
- **Purpose**: Get only the extracted text content of a specific PDF
- **Authentication**: None (but typically used with authenticated sessions)
- **Parameters**: `pdf_id`: ID of the PDF to retrieve content for
- **Response**: Object containing PDF ID and text content
- **Error**: 404 if PDF or content not found

## Chat Functionality

### `POST /query`
- **Purpose**: Main chatbot interaction endpoint
- **Authentication**: Required
- **Headers**: 
  - `X-Thread-Id` (optional): ID of existing conversation thread
- **Body**: JSON with:
  - `messages`: Array of conversation messages
  - `pdf_id` (optional): ID of PDF to use as context
- **Response**: Streaming response with AI-generated text
- **Response Headers**:
  - `X-Thread-Id`: ID of the conversation thread
  - `X-Thread-Created`: Set to "true" if a new thread was created
- **Actions**:
  - Creates or validates conversation threads
  - Processes messages with AI using PDF context
  - Returns streaming response for real-time display

## API Security Features

- JWT-based authentication with HTTP-only cookies
- CORS configuration to allow specific frontend origins
- Environment-specific security settings (production vs development)
- Content-type validation for uploads
- Conversation thread ownership validation

## API Response Formats

- **Regular Endpoints**: Standard JSON responses
- **Chat Endpoint**: Server-sent events stream (`text/event-stream`)
- **Error Responses**: HTTP exceptions with status codes and detail messages

## Common Headers

- **Authentication**: Provided via `auth_token` cookie
- **Thread Management**: `X-Thread-Id` header for conversation continuity
- **Streaming Responses**: Standard headers for SSE (Server-Sent Events)
  - `Cache-Control: no-cache`
  - `Connection: keep-alive`

# Setup
## Backend: `cd backend`
### Setup a python environment:
```
python -m venv venv
```
- on Windows:
```
.\venv\Scripts\activate
```
- on linux:
```
source venv/bin/activate
```
### **Install the requirements**
```
pip install -r requirements.txt
```
### **Setup Environment variables**
.env
```
GOOGLE_API_KEY=<your_gemini_api_key>
SESSION_SECRET_KEY=<your_jwt_secret>
FRONTEND_URL1=<frontend_urls>
FRONTEND_URL2=<frontend_urls>
FRONTEND_URL3=<frontend_urls>
ENVIRONMENT=<development_or_production>
```
### **Run the server**
```
fastapi dev main.py
```
## Frontend: `cd frontend`
### **Install the requirements**
```
npm install -g yarn
yarn install
```
### **Build the server**
```
yarn build
```
### **Setup Environment variables**
.env
```
BACKEND_URL=<your_backend_url>
```
### **run the server**
```
yarn dev
```
