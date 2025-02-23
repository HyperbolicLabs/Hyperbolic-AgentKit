import os
import gradio as gr
import asyncio
from chatbot import initialize_agent
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from utils import format_ai_message_content
from datetime import datetime

# Global variables to store initialized agent and config
agent = None
agent_config = None

async def chat_with_agent(message, history):
    global agent, agent_config
    
    # Convert history into messages format that the agent expects
    messages = []
    if history:
        print("History:", history)  # Debug print
        for msg in history:
            if isinstance(msg, dict):
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg.get("role") == "assistant":
                    messages.append({"role": "assistant", "content": msg["content"]})
    
    # Add the current message
    messages.append(HumanMessage(content=message))
    
    print("Final messages:", messages)  # Debug print
    
    runnable_config = RunnableConfig(
        recursion_limit=agent_config["configurable"]["recursion_limit"],
        configurable={
            "thread_id": agent_config["configurable"]["thread_id"],
            "checkpoint_ns": "chat_mode",
            "checkpoint_id": str(datetime.now().timestamp())
        }
    )
    
    response_messages = []
    yield response_messages
    # Process message with agent
    async for chunk in agent.astream(
        {"messages": messages},  # Pass the full message history
        runnable_config
    ):
        if "agent" in chunk:
            print("agent in chunk")
            response = chunk["agent"]["messages"][0].content
            response_messages.append(dict(
                role="assistant",
                content=format_ai_message_content(response, format_mode="markdown")
            ))
            print(response_messages)
            yield response_messages
        elif "tools" in chunk:
            print("tools in chunk")
            tool_message = str(chunk["tools"]["messages"][0].content)
            response_messages.append(dict(
                role="assistant",
                content=tool_message,
                metadata={"title": "🛠️ Tool Call"}
            ))
            print(response_messages)
            yield response_messages

def create_ui():
    # Create the Gradio interface
    with gr.Blocks(title="Hyperbolic AgentKit", fill_height=True) as demo:
        # gr.Markdown("# Hyperbolic AgentKit")
        # gr.Markdown("""
        # Welcome to the Hyperbolic AgentKit interface! This AI agent can help you with:
        # - Compute Operations (via Hyperbolic)
        # - Blockchain Operations (via CDP)
        # - Social Media Management
        # """)
        
        # Create a custom chatbot with message styling
        # custom_chatbot = gr.Chatbot(
        #     label="Agent",
        #     type="messages",
        #     height=600,
        #     show_copy_button=True,
        #     avatar_images=(
        #         None,
        #         "https://em-content.zobj.net/source/twitter/53/robot-face_1f916.png"
        #     ),
        #     render_markdown=True
        # )
        
        gr.ChatInterface(
            chat_with_agent,
            # chatbot=custom_chatbot,
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

async def main():
    global agent, agent_config
    # Initialize agent before creating UI
    print("Initializing agent...")
    agent_executor, config, runnable_config = await initialize_agent()
    agent = agent_executor
    agent_config = config
    
    # Create and launch the UI
    print("Starting Gradio UI...")
    demo = create_ui()
    demo.queue()
    demo.launch(share=True)

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main()) 