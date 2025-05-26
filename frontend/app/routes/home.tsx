import type { Route } from "./+types/home";
import { useState, useEffect, useRef } from "react";
import axios from "axios";
import Navbar from "../components/Navbar";
import ReactMarkdown from "react-markdown";

// Backend URL configuration from environment variables with fallback
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

// Type definitions for PDF and message objects
interface PDF {
  id: number;
  filename: string;
  file_size: number;
  upload_date: string;
  content_type: string;
}

interface Message {
  role: "user" | "assistant" | "ai";
  content: string;
}

const App: React.FC = () => {
  // State management for chat functionality
  const [inputValue, setInputValue] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hello! I'm your AI assistant. Upload a PDF and ask me questions about it."
    }
  ]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedPdf, setSelectedPdf] = useState<PDF | null>(null);
  const [pageLoading, setPageLoading] = useState<boolean>(true);
  
  // PDF-specific chat history storage using useRef for persistence between renders
  const pdfChatHistory = useRef<Record<number, {messages: Message[], threadId: string | null}>>({});
  
  // Refs for scrolling and handling request cancellation
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortController = useRef<AbortController | null>(null);

  // Initial API connection check on component mount
  useEffect(() => {
    const checkConnection = async () => {
      let response = false;
      while (!response) {
        try {
          const res = await axios.get(`${BACKEND_URL}/`, { withCredentials: true });
          response = res.status === 200;
          if (response) {
            const health = await axios.get(`${BACKEND_URL}/health`, { withCredentials: true });
            if (health.status == 200) {
              setPageLoading(false);
            } else {
              console.error("Failed to connect, retrying...");
              await new Promise(resolve => setTimeout(resolve, 2000));
            }
          }
        } catch (error) {
          console.error("Connection check failed, retrying...", error);
          await new Promise(resolve => setTimeout(resolve, 2000));
        }
      }
    }
    checkConnection();
  }, []);

  // Auto-scroll to the latest message when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Modified handler for when user selects a PDF from the Navbar component
  const handlePdfSelect = (pdf: PDF | null) => {
    // Save current conversation if there's a selected PDF
    if (selectedPdf && messages.length > 1) {
      pdfChatHistory.current[selectedPdf.id] = {
        messages: [...messages],
        threadId: threadId
      };
    }
    
    setSelectedPdf(pdf);
    
    if (pdf) {
      // Check if we have previous conversation for this PDF
      const previousChat = pdfChatHistory.current[pdf.id];
      
      if (previousChat) {
        // Restore previous conversation
        setMessages(previousChat.messages);
        setThreadId(previousChat.threadId);
      } else {
        // Start new conversation for this PDF
        setMessages([
          {
            role: "assistant",
            content: `PDF selected: ${pdf.filename}. How can I help you with this document?`
          }
        ]);
        setThreadId(null); // Reset thread ID for new conversation
      }
    } else {
      // Reset to default when no PDF is selected
      setMessages([
        {
          role: "assistant",
          content: "Hello! I'm your AI assistant. Upload a PDF and ask me questions about it."
        }
      ]);
      setThreadId(null);
    }
  };

  // Handler to stop AI response generation when user clicks the stop button
  const handleStopGeneration = () => {
    if (abortController.current) {
      abortController.current.abort();
      abortController.current = null;
    }

    setIsLoading(false);

    setMessages(prevMessages => {
      const updatedMessages = [...prevMessages];
      const lastMessageIndex = updatedMessages.length - 1;
      const lastMessage = updatedMessages[lastMessageIndex];

      if (lastMessage.role === "assistant") {
        updatedMessages[lastMessageIndex] = {
          ...lastMessage,
          content: lastMessage.content + "\n\n_Generation stopped by user_"
        };
      }

      return updatedMessages;
    });
  };

  // Main handler for submitting user queries to the backend
  const handleSubmit = async (e: React.MouseEvent<HTMLButtonElement> | React.KeyboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    if (!selectedPdf) {
      setError("Please select a PDF first");
      return;
    }

    const userMessage: Message = { role: "user", content: inputValue };

    // Add user message to chat history and reset input
    setMessages(prevMessages => [...prevMessages, userMessage]);
    setInputValue("");
    setIsLoading(true);
    setError(null);

    try {
      // Create abort controller for cancellation support
      abortController.current = new AbortController();

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
      };

      // Include thread ID if available for conversation continuity
      if (threadId) {
        headers["X-Thread-Id"] = threadId;
      }

      const currentMessages = [...messages, userMessage];

      // Send query to backend with streaming response
      const response = await fetch(`${BACKEND_URL}/query`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          messages: currentMessages,
          pdf_id: selectedPdf.id
        }),
        credentials: 'include',
        signal: abortController.current.signal
      });

      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}: ${await response.text()}`);
      }

      // Capture thread ID from response headers for conversation continuity
      const responseThreadId = response.headers.get("X-Thread-Id");
      if (responseThreadId) {
        setThreadId(responseThreadId);
        
        // Also update the thread ID in our PDF history
        if (selectedPdf) {
          pdfChatHistory.current[selectedPdf.id] = {
            messages: pdfChatHistory.current[selectedPdf.id]?.messages || [...messages, userMessage],
            threadId: responseThreadId
          };
        }
      }

      // Add empty assistant message to be populated with streaming content
      const aiMessage: Message = { role: "assistant", content: "" };
      setMessages(prevMessages => [...prevMessages, aiMessage]);

      // Process streaming response using ReadableStream API
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();

        if (done) break;

        if (value) {
          const textChunk = decoder.decode(value, { stream: true });

          // Append each chunk to the last message
          setMessages(prevMessages => {
            const updatedMessages = [...prevMessages];
            const lastMessageIndex = updatedMessages.length - 1;
            const lastMessage = updatedMessages[lastMessageIndex];

            if (lastMessage.role === "assistant") {
              updatedMessages[lastMessageIndex] = {
                ...lastMessage,
                content: lastMessage.content + textChunk
              };
              
              // Also update the message in our PDF history
              if (selectedPdf) {
                const currentHistory = pdfChatHistory.current[selectedPdf.id] || { messages: updatedMessages, threadId };
                pdfChatHistory.current[selectedPdf.id] = {
                  ...currentHistory,
                  messages: updatedMessages
                };
              }
            }

            return updatedMessages;
          });
        }
      }
    } catch (err) {
      // Handle abort errors differently than other errors
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }

      console.error("Error querying the chatbot:", err);
      const errorMessage = err instanceof Error ? err.message : "An unknown error occurred";
      setError(errorMessage);

      setMessages(prevMessages => [
        ...prevMessages,
        {
          role: "assistant",
          content: "Sorry, I encountered an error. Please try again or check your connection."
        }
      ]);
    } finally {
      // Reset loading state and abort controller if request completed normally
      if (abortController.current?.signal.aborted === false) {
        abortController.current = null;
        setIsLoading(false);
      }
    }
  };

  if (pageLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen flex-col">
        <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-primary" />
        <div className="text-2xl mt-20">Note: Initial connection might take some time to load</div>
        <div className="text-2xl">Please enable third party cookies</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen">
      {/* Navbar component with PDF selection functionality */}
      <Navbar onPdfSelect={handlePdfSelect} selectedPdf={selectedPdf} />

      <div className="container mx-auto flex-grow p-4 flex flex-col">
        <div className="flex-grow max-w-4xl min-w-[320px] mx-auto w-full flex flex-col border border-gray-200 rounded-lg shadow-md">
          {/* Chat message container with automatic scrolling */}
          <div className="flex-grow overflow-y-auto p-4 lg:max-h-[79vh] sm:max-h-[70vh] md:max-h-[65vh]">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`mb-4 p-3 rounded-lg ${message.role === "user"
                  ? "bg-blue-100 ml-auto max-w-[80%]"
                  : "bg-gray-100 mr-auto max-w-[80%]"
                  }`}
              >
                <p className="text-sm font-bold capitalize mb-1">{message.role === "ai" ? "assistant" : message.role}</p>
                <div className="markdown-content prose prose-sm max-w-none">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>
              </div>
            ))}
            {/* Loading indicator shows while waiting for AI response */}
            {isLoading && (
              <div className="bg-gray-100 mr-auto max-w-[80%] mb-4 p-3 rounded-lg">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce"></div>
                  <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input form for user queries */}
          <div className="border-t border-gray-200 p-3">
            {/* Error display area */}
            {error && (
              <div className="mb-2">
                <p className="text-red-500 text-sm">{error}</p>
              </div>
            )}
            <form onSubmit={(e) => { e.preventDefault(); handleSubmit(e as unknown as React.KeyboardEvent<HTMLInputElement>); }}>
              {/* PDF selection warning */}
              {!selectedPdf && (
                <div className="relative flex items-center text-red-500 text-sm">
                  Please select a PDF first
                </div>
              )}
              <div className="relative flex items-center">
                {/* User input field with conditional validation */}
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSubmit(e)}
                  className={`w-full border-2 border-gray-200 py-2 px-4 pr-12 rounded-lg focus:outline-none focus:border-primary ${!selectedPdf ? "bg-gray-100" : ""}`}
                  placeholder={selectedPdf ? "Ask about the PDF..." : "Select a PDF first..."}
                  disabled={isLoading || !selectedPdf}
                />

                {/* Dynamically show stop or send button based on loading state */}
                {isLoading ? (
                  <button
                    type="button"
                    onClick={handleStopGeneration}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-red-500 hover:text-red-700 focus:outline-none"
                    aria-label="Stop generation"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24">
                      <path d="M6 6h12v12H6z" fill="currentColor" />
                    </svg>
                  </button>
                ) : (
                  <button
                    type="submit"
                    onClick={handleSubmit}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 hover:text-primary focus:outline-none disabled:opacity-50"
                    disabled={isLoading || !inputValue.trim() || !selectedPdf}
                    aria-label="Send message"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24">
                      <g fill={inputValue.trim() && !isLoading && selectedPdf ? "#1976d2" : "#141414"} fillRule="nonzero">
                        <path d="m3.45559904 3.48107721 3.26013002 7.74280879c.20897233.4963093.20897233 1.0559187 0 1.552228l-3.26013002 7.7428088 18.83130296-8.5189228zm-.74951511-1.43663117 20.99999997 9.49999996c.3918881.1772827.3918881.7338253 0 .911108l-20.99999997 9.5c-.41424571.1873968-.8433362-.2305504-.66690162-.6495825l3.75491137-8.9179145c.10448617-.2481546.10448617-.5279594 0-.776114l-3.75491137-8.9179145c-.17643458-.41903214.25265591-.83697933.66690162-.64958246z" />
                        <path d="m6 12.5v-1h16.5v1z" />
                      </g>
                    </svg>
                  </button>
                )}
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;