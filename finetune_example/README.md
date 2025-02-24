# Quickstart
Demo video: https://www.loom.com/share/13dfa667db9f496188df284cb15c392b?sid=397e07f7-fb69-472e-8f93-29abea759ce8

* It is recommended to rent a GPU from the Hyperbolic web app first to simplify the agent flow, but this is optional.

## Setup
0. Make sure all the installation steps in the main README are completed.
1. First, set up the following REQUIRED env variables:
```
ANTHROPIC_API_KEY=
CDP_API_KEY_NAME=
CDP_API_KEY_PRIVATE_KEY=

HYPERBOLIC_API_KEY=

SSH_PRIVATE_KEY_PATH=/path/to/your/.ssh/id_rsa

LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=
```

2. Boot up the chatbot gradio interface:
```
poetry run python gradio_ui.py
```

3. Type in the following prompt in the chatbot interface:
```
Run a fine tuning task using Mistral 7b using get_gpu_status first
```

4. Check your console logs and also SSH into your remote GPU instance to track the progress of the fine tuning task.
```
ssh ubuntu@<your-instance-ip> -p XXXXX
cd finetune_example
ls
```

5. Once the fine tuning task is complete, you will see a "success" message in the chatbot interface.

6. You can now use the fine tuned model for inference in your remote GPU instance by running:
```
source venv/bin/activate
python3 test_inference.py "Your prompt here"
```

7. You can also edit the finetune.py script or training_data.jsonl file by running:
```
nano finetune.py
nano training_data.jsonl
```

8. You can reinitiate another fine tuning task using your newly updated parameters (or another base model) by running:
```
export FINE_TUNE_MODEL="unsloth/mistral-7b-v0.3-bnb-4bit"
python3 finetune.py 
```

or you can just ask the Hyperbolic agent through the chat interface to do it for you.

9. You can delete the finetuned model in your remote GPU instance by running:
```
rm -rf finetuned_model
```

* Support for syncing the finetuned model back to your local machine is coming soon.

