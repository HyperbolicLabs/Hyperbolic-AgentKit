USE_FINETUNE_TOOLS=true

LANGCHAIN keys need to be set in .env file

SSH_PRIVATE_KEY_PATH make sure to have RSA


Rent a GPU from Hyperbolic

"Run a fine tuning task using Mistral 7b using get_gpu_status first"

the env variables you NEED to set are 
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

USE_FINETUNE_TOOLS=true
```