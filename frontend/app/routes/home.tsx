import type { Route } from "./+types/home";
import { useState, useEffect, useRef } from "react";
import axios from "axios";
import Navbar from "../components/Navbar";
import ReactMarkdown from "react-markdown";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

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

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    //fetch userid
    axios.get(`${BACKEND_URL}/`, { withCredentials: true })
  }, []);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handlePdfSelect = (pdf: PDF | null) => {
    setSelectedPdf(pdf);
    // Optionally add a system message indicating the PDF change
    if (pdf) {
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: `PDF changed to: ${pdf.filename}. How can I help you with this document?`
        }
      ]);
    }
  };

  const handleSubmit = async (e: React.MouseEvent<HTMLButtonElement> | React.KeyboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    // Check if a PDF is selected
    if (!selectedPdf) {
      setError("Please select a PDF first");
      return;
    }

    const userMessage: Message = { role: "user", content: inputValue };

    // Add user message to the chat
    setMessages(prevMessages => [...prevMessages, userMessage]);
    setInputValue("");
    setIsLoading(true);
    setError(null);

    try {
      // Prepare headers for the request
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream' // Explicitly request SSE format
      };

      if (threadId) {
        headers["X-Thread-Id"] = threadId;
      }

      // Create a new message array that includes the user message we just added
      const currentMessages = [...messages, userMessage];

      // Get the stream response
      const response = await fetch(`${BACKEND_URL}/query`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          messages: currentMessages,
          pdf_id: selectedPdf.id
        }),
        credentials: 'include'
      });
      console.log("Response headers:", response);

      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}: ${await response.text()}`);
      }

      // Get thread ID from headers if it exists
      const responseThreadId = response.headers.get("X-Thread-Id");
      if (responseThreadId) {
        setThreadId(responseThreadId);
      }

      // Create a new message for the AI response
      const aiMessage: Message = { role: "assistant", content: "" };
      setMessages(prevMessages => [...prevMessages, aiMessage]);

      // Process the streaming response
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();

        if (done) break;

        if (value) {
          const textChunk = decoder.decode(value, { stream: true });

          // Update the latest AI message with the new content
          setMessages(prevMessages => {
            const updatedMessages = [...prevMessages];
            const lastMessageIndex = updatedMessages.length - 1;
            const lastMessage = updatedMessages[lastMessageIndex];

            if (lastMessage.role === "assistant") {
              // Create new message object to ensure state update triggers
              updatedMessages[lastMessageIndex] = {
                ...lastMessage,
                content: lastMessage.content + textChunk
              };
            }

            return updatedMessages;
          });
        }
      }
    } catch (err) {
      console.error("Error querying the chatbot:", err);
      const errorMessage = err instanceof Error ? err.message : "An unknown error occurred";
      setError(errorMessage);

      // Add error message
      setMessages(prevMessages => [
        ...prevMessages,
        {
          role: "assistant",
          content: "Sorry, I encountered an error. Please try again or check your connection."
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <Navbar onPdfSelect={handlePdfSelect} selectedPdf={selectedPdf} />

      <div className="container mx-auto flex-grow p-4 flex flex-col">
        {/* Chat container with fixed dimensions and scrolling */}
        <div className="flex-grow max-w-3xl mx-auto w-full flex flex-col border border-gray-200 rounded-lg shadow-md">
          {/* Messages area with scrolling */}
          <div className="flex-grow overflow-y-auto p-4 max-h-[70vh]">
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
            {isLoading && (
              <div className="bg-gray-100 mr-auto max-w-[80%] mb-4 p-3 rounded-lg">
                {/* <p className="text-sm font-bold mb-1">Assistant</p> */}
                <div className="flex space-x-2">
                  <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce"></div>
                  <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Fixed input area at the bottom */}
          <div className="border-t border-gray-200 p-3">
            {error && (
              <div className="mb-1">
                <p className="text-red-500 text-sm">{error}</p>
              </div>
            )}
            <form onSubmit={(e) => { e.preventDefault(); handleSubmit(e as unknown as React.KeyboardEvent<HTMLInputElement>); }}>
              <div className="relative">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSubmit(e)}
                  className={`w-full border-2 border-gray-200 py-2 px-4 pr-12 rounded-lg focus:outline-none focus:border-primary ${!selectedPdf ? "bg-gray-400" : ""}`}
                  placeholder={selectedPdf ? "Ask about the PDF..." : "Select a PDF first..."}
                  disabled={isLoading || !selectedPdf}
                />
                {!selectedPdf && (
                  <div className="absolute left-4 top-30 -translate-y-1/2 text-red-500 text-sm">
                    Please select a PDF first
                  </div>
                )}
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
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;