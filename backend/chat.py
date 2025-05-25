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

load_dotenv()

if not os.environ.get("GOOGLE_API_KEY"):
  os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")

model = init_chat_model("gemini-2.5-flash-preview-05-20", model_provider="google_genai")

async def call_model(state: MessagesState):
    response = await model.ainvoke(state["messages"])
    return {"messages": response}

system_message = """
You are an assistant who takes in pdf 
content as input and prepares questions and answers on the 
pdf and return it. Additionally also solve any other queries 
from the user
"""

# Define a new graph
workflow = StateGraph(state_schema=MessagesState)


# Define the function that calls the model
def call_model(state: MessagesState):
    response = model.invoke(state["messages"])
    return {"messages": response}


# Define the (single) node in the graph
workflow.add_edge(START, "model")
workflow.add_node("model", call_model)

# Add memory
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

def parse_messages(input_messages, pdf_id):
    pdf_content = get_pdf_text_by_id(pdf_id)["text_content"]
    output_messages = []
    output_messages.append(SystemMessage(content=system_message))
    output_messages.append(SystemMessage(content=f"Here is the pdf content: \n{pdf_content}\n"))
    for message in input_messages:
        if message["role"] == "ai":
            output_messages.append(AIMessage(content=message["content"]))
        elif message["role"] == "user":
            output_messages.append(HumanMessage(content=message["content"]))
    return output_messages  # Add this return statement

async def send_msg(input_messages, config):
    # output = await app.ainvoke({"messages": input_messages}, config)
    # return output["messages"][-1]

    for chunk, metadata in app.stream(
        {"messages": input_messages},
        config,
        stream_mode="messages",
    ):
        if isinstance(chunk, AIMessage):  # Filter to just model responses
            yield chunk.content
