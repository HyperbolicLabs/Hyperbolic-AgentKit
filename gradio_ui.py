import os
import gradio as gr
import asyncio
from chatbot import initialize_agent
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from utils import format_ai_message_content
from datetime import datetime

async def chat_with_agent(message, history):
    # Initialize agent if not already done
    if not hasattr(chat_with_agent, "agent"):
        agent_executor, config, twitter_api_wrapper, knowledge_base = await initialize_agent()
        chat_with_agent.agent = agent_executor
        chat_with_agent.config = config

    runnable_config = RunnableConfig(
        recursion_limit=chat_with_agent.config["configurable"]["recursion_limit"],
        configurable={
            "thread_id": chat_with_agent.config["configurable"]["thread_id"],
            "checkpoint_ns": "chat_mode",
            "checkpoint_id": str(datetime.now().timestamp())
        }
    )
    
    messages = []
    yield messages
    # Process message with agent
    async for chunk in chat_with_agent.agent.astream(
        {"messages": [HumanMessage(content=message)]},
        runnable_config
    ):
        if "agent" in chunk:
            print("agent in chunk")
            response = chunk["agent"]["messages"][0].content
            messages.append(dict(
                role="assistant",
                content=format_ai_message_content(response, format_mode="markdown")
            ))
            print(messages)
            yield messages
        elif "tools" in chunk:
            print("tools in chunk")
            tool_message = str(chunk["tools"]["messages"][0].content)
            messages.append(dict(
                role="assistant",
                content=tool_message,
                metadata={"title": "🛠️ Tool Call"}
            ))
            print(messages)
            yield messages

def create_ui():
    # Create the Gradio interface
    # gr.Markdown("# Hyperbolic AgentKit")
    # gr.Markdown("""
    # Welcome to the Hyperbolic AgentKit interface! This AI agent can help you with:
    # - Compute Operations (via Hyperbolic)
    # - Blockchain Operations (via CDP)
    # - Social Media Management
    # """)
    
    # Create a custom chatbot with message styling
    custom_chatbot = gr.Chatbot(
        label="Agent",
        type="messages",
        height=600,
        show_copy_button=True,
        avatar_images=(
            None,
            "https://em-content.zobj.net/source/twitter/53/robot-face_1f916.png"
        ),
        render_markdown=True
    )
    
    demo = gr.ChatInterface(
        chat_with_agent,
        chatbot=custom_chatbot,
        type="messages",
        title="Chat with Hyperbolic Agent",
        description="Ask questions about blockchain, compute resources, or social media management.",
        examples=[
            "What GPU resources are available?",
            "How can I deploy a new token?",
            "Check the current balance",
            "Show me the available compute options"
        ],
        # retry_btn=None,
        # undo_btn=None,
        # clear_btn="Clear Chat",
        fill_height=True,
        fill_width=True,
    )

    return demo

if __name__ == "__main__":
    # Create and launch the UI
    demo = create_ui()
    demo.queue()
    demo.launch(share=True) 