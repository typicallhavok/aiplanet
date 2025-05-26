import getpass
import os
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, trim_messages, BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from typing import Sequence
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from misc import get_pdf_text_by_id

# Load environment variables from .env file
load_dotenv()

# Prompt for API key if not provided in environment variables
if not os.environ.get("GOOGLE_API_KEY"):
  os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")

# Initialize the LLM model - using Google's Gemini model
model = init_chat_model("gemini-2.5-flash-preview-05-20", model_provider="google_genai")

# Async function to call the model with the current state's messages
async def call_model(state: MessagesState):
    """
    Async wrapper for model invocation - invokes the LLM with the current message history
    
    Args:
        state: Current message state containing conversation history
        
    Returns:
        dict: Updated message state with model's response
    """
    response = await model.ainvoke(state["messages"])
    return {"messages": response}

# System message that provides instructions to the AI model
system_message = """
You are an assistant who takes in pdf 
content as input and prepares questions and answers on the 
pdf and return it. Additionally also solve any other queries 
from the user
"""

# Define a workflow graph using LangGraph for message handling
workflow = StateGraph(state_schema=MessagesState)

# Define the synchronous function that calls the model
def call_model(state: MessagesState):
    """
    Synchronous model invocation function - processes messages and returns model's response
    
    Args:
        state: Current message state containing conversation history
        
    Returns:
        dict: Updated message state with model's response
    """
    response = model.invoke(state["messages"])
    return {"messages": response}

# Configure the graph workflow
workflow.add_edge(START, "model")  # Define starting point
workflow.add_node("model", call_model)  # Add model node for processing

# Add memory to persist conversation state between calls
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

def parse_messages(input_messages, pdf_id):
    """
    Transforms frontend message format to the format expected by the LLM
    
    Key operations:
    1. Retrieves PDF content from the database
    2. Adds system instructions to guide the model's behavior
    3. Converts message roles (user/ai) to LangChain message types
    
    Args:
        input_messages: List of messages from the frontend (user/ai)
        pdf_id: ID of the PDF to reference in the conversation
        
    Returns:
        list: Properly formatted messages for the LLM
    """
    # Get PDF content from database
    pdf_content = get_pdf_text_by_id(pdf_id)["text_content"]
    
    # Initialize output message list with system instructions
    output_messages = []
    output_messages.append(SystemMessage(content=system_message))
    output_messages.append(SystemMessage(content=f"Here is the pdf content: \n{pdf_content}\n"))
    
    # Convert each message to the appropriate LangChain message type
    for message in input_messages:
        if message["role"] == "ai":
            output_messages.append(AIMessage(content=message["content"]))
        elif message["role"] == "user":
            output_messages.append(HumanMessage(content=message["content"]))
            
    return output_messages

async def send_msg(input_messages, config):
    """
    Sends processed messages to the model and streams responses back
    
    Implements streaming to provide real-time responses to the frontend
    
    Args:
        input_messages: List of properly formatted messages for the model
        config: Configuration dictionary containing thread ID and other settings
        
    Yields:
        str: Content chunks from the model's response for streaming
    """
    # Note: Commented out code shows non-streaming implementation
    # output = await app.ainvoke({"messages": input_messages}, config)
    # return output["messages"][-1]

    # Stream response chunks to enable real-time display in frontend
    for chunk, metadata in app.stream(
        {"messages": input_messages},
        config,
        stream_mode="messages",
    ):
        if isinstance(chunk, AIMessage):  # Filter to just model responses
            yield chunk.content