# High-Level Design (HLD) and Low-Level Design (LLD) 

Based on the code provided in the attachments, I can create a comprehensive design overview of the AI Planet application. This appears to be a web application that allows users to interact with PDF documents using AI capabilities.

## High-Level Design (HLD)

### System Architecture
The application follows a client-server architecture with:

1. **Frontend**: React-based web application built with:
   - React Router for navigation
   - Tailwind CSS for styling
   - TypeScript for type safety

2. **Backend**: Python-based API server providing:
   - PDF document management
   - Chat functionality with LLM integration
   - File upload/storage capabilities

3. **Data Storage**:
   - SQLite database (`chat_database.db`) for storing chat histories and PDF metadata
   - File system storage for PDF documents (in `uploads/` directory)

### Main Features
1. PDF Document Management
   - Upload PDFs
   - Select from available PDFs

2. AI Chat Interface
   - Contextual conversation based on selected PDF
   - Chat history preservation
   - Markdown rendering of responses

## Low-Level Design (LLD)

### Frontend Component Structure

```
frontend/
│
├── app/                    # Main application code
│   ├── app.css            # Global styles
│   ├── root.tsx           # Root component and layout
│   ├── routes.ts          # Route definitions
│   │
│   ├── components/        # Reusable UI components
│   │   ├── Logo.tsx       # AI Planet logo component
│   │   ├── Navbar.tsx     # Navigation and PDF selection
│   │   └── ChatBubbles.tsx # Chat message display
│   │
│   └── routes/           # Page components
│       └── home.tsx      # Main chat interface
│
├── public/               # Static assets
│
└── build/                # Compiled application
    ├── client/           # Client-side bundles
    └── server/           # Server-side rendering code
```

### Backend Component Structure

```
backend/
│
├── main.py              # Main API entry point
├── chat.py              # Chat processing logic and LLM integration
├── misc.py              # Utility functions
├── requirements.txt     # Dependencies
│
└── uploads/             # PDF storage directory
```

### Data Models

#### PDF Document Model
```typescript
interface PDF {
    id: string;
    filename: string;
    file_size: number;
    upload_date?: string;
}
```

#### Chat Message Model
```typescript
interface Message {
    role: "user" | "ai" | "assistant";
    content: string;
}
```

### Key Frontend Components

#### 1. Navbar Component
- **Responsibility**: Navigation, PDF selection/upload
- **Key Functions**:
  - `fetchPdfs()`: Gets available PDFs from backend
  - `handleFileChange()`: Handles PDF file selection
  - `handleUploadPDF()`: Uploads PDFs to backend
  - `handleSelectPdf()`: Sets the active PDF for chat

#### 2. Chat Interface
- **Responsibility**: Chat message display and interaction
- **Key Functions**:
  - `handleSubmit()`: Sends user messages to backend
  - `handlePdfSelect()`: Updates the active PDF
  - `handleStopGeneration()`: Cancels ongoing LLM responses

### Responsive Design
The application has responsive design considerations:
- Mobile detection
- Different UI layouts for mobile vs desktop
- Adaptive component sizing

### Data Flow

1. **PDF Upload Flow**:
   - User selects PDF file through file input
   - Frontend sends file to backend via multipart form data
   - Backend saves PDF to `uploads/` directory
   - Backend extracts text content and stores metadata in database
   - Updated PDF list is returned to frontend

2. **Chat Conversation Flow**:
   - User selects PDF from dropdown
   - User enters message in chat input
   - Frontend sends message and PDF ID to backend
   - Backend:
     - Retrieves PDF content
     - Processes message with LLM using PDF as context
     - Returns AI response to frontend
   - Frontend displays the response in chat interface
