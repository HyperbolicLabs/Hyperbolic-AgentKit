import os
import gradio as gr
import asyncio
from chatbot import initialize_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from base_utils.utils import format_ai_message_content
from datetime import datetime

# Global variables to store initialized agent and config
agent = None
agent_config = None

async def chat_with_agent(message, history):
    global agent, agent_config
    
    messages = []
    if history:
        print("History:", history)
        # Iterate through the flat list of message dictionaries
        for msg_dict in history: 
            if isinstance(msg_dict, dict) and 'role' in msg_dict and 'content' in msg_dict:
                role = msg_dict['role']
                content = msg_dict['content']
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    # Pass the content as is; Langchain can handle AIMessage content
                    messages.append(AIMessage(content=content)) 
            elif isinstance(msg_dict, (list, tuple)) and len(msg_dict) == 2:
                 # Fallback for older Gradio history format (just in case)
                 user_msg, ai_msg = msg_dict
                 if user_msg:
                     messages.append(HumanMessage(content=user_msg))
                 if ai_msg:
                     messages.append(AIMessage(content=ai_msg))
            else:
                print(f"Skipping unexpected history item: {msg_dict}")


    # Add the current user message
    messages.append(HumanMessage(content=message))
    
    print("Final messages being sent to agent:", messages) 
    
    runnable_config = RunnableConfig(
        recursion_limit=agent_config["configurable"]["recursion_limit"],
        configurable={
            "thread_id": agent_config["configurable"]["thread_id"],
            "checkpoint_ns": "chat_mode",
            "checkpoint_id": str(datetime.now().timestamp()) # Keep checkpointing per interaction
        }
    )
    
    current_turn_messages = [] 
    
    async for chunk in agent.astream(
        {"messages": messages}, 
        runnable_config
    ):
        if "agent" in chunk:
            print("agent in chunk")
            response_content = chunk["agent"]["messages"][0].content
            formatted_content = format_ai_message_content(response_content, format_mode="markdown")
            current_turn_messages.append(formatted_content) 
            print("Yielding agent response:", current_turn_messages)
            yield "\n\n".join(current_turn_messages) # Join with double newline for better separation

        elif "tools" in chunk:
            print("tools in chunk")
            tool_message = str(chunk["tools"]["messages"][0].content)
            formatted_content = f"**🛠️ Tool Call:**\n```\n{tool_message}\n```" 
            current_turn_messages.append(formatted_content)
            print("Yielding tool response:", current_turn_messages)
            yield "\n\n".join(current_turn_messages) # Join with double newline

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