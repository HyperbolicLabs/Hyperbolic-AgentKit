import os
import torch
from unsloth import FastLanguageModel, is_bfloat16_supported
from transformers import TrainingArguments
from trl import SFTTrainer
from datasets import load_dataset
from datetime import datetime

def log_progress(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] 🐰 {msg}")

def format_chat(example):
    """Format the chat messages into a single text string."""
    messages = example["messages"]
    
    # Format for Mistral chat template
    formatted_messages = []
    for msg in messages:
        if msg["role"] == "system":
            # System message goes at the start
            formatted_messages.insert(0, f"<s>[INST] {msg['content']} [/INST]")
        elif msg["role"] == "user":
            formatted_messages.append(f"<s>[INST] {msg['content']} [/INST]")
        elif msg["role"] == "assistant":
            formatted_messages.append(f"{msg['content']}</s>")
    
    example["text"] = " ".join(formatted_messages)
    return example

def fine_tune():
    log_progress("🚀 Starting fine-tuning process...")
    
    # Load and format dataset
    dataset = load_dataset("json", data_files={"train": "training_data.jsonl"})["train"]
    
    # Model configuration
    max_seq_length = 4096  # Increased for longer context
    dtype = None  # Auto-detect optimal dtype
    load_in_4bit = True
    
    # Configure model loading with explicit dtypes
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/mistral-7b-v0.3-bnb-4bit",
        max_seq_length=max_seq_length,
        dtype=dtype,
        load_in_4bit=load_in_4bit
    )
    
    # Set the chat template for Mistral
    tokenizer.chat_template = """{% for message in messages %}
    {% if message['role'] == 'user' %}
    {{ '<s>[INST] ' + message['content'] + ' [/INST]' }}
    {% elif message['role'] == 'assistant' %}
    {{ message['content'] + '</s>' }}
    {% elif message['role'] == 'system' %}
    {{ '<s>[INST] ' + message['content'] + ' [/INST]' }}
    {% endif %}
    {% endfor %}"""
    
    # Add LoRA adapters with optimized settings
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", 
                       "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,  # Optimized setting
        bias="none",     # Optimized setting
        use_gradient_checkpointing="unsloth",  # Uses 30% less VRAM
        random_state=3407,
        use_rslora=False,
        loftq_config=None
    )
    
    # Training arguments with mixed precision settings
    training_args = TrainingArguments(
        output_dir="./finetuned_model",
        num_train_epochs=3,
        per_device_train_batch_size=1,  # Reduced for longer sequences
        gradient_accumulation_steps=4,
        warmup_steps=5,
        learning_rate=2e-4,
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        # Use appropriate precision based on hardware
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        torch_compile=False,  # Disable torch compile for stability
        seed=3407
    )
    
    # Initialize trainer
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        args=training_args,
        tokenizer=tokenizer,
        max_seq_length=max_seq_length,
        dataset_num_proc=2,
        packing=False
    )
    
    # Train
    log_progress("🏃 Training model...")
    trainer_stats = trainer.train()
    
    # Save the model
    log_progress("💾 Saving fine-tuned model...")
    output_dir = "./finetuned_model"
    
    # Save model and tokenizer
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    # Optionally save in 8-bit GGUF format
    try:
        model.save_pretrained_gguf(output_dir, tokenizer, quantization_method=["q8_0"])
    except Exception as e:
        print(f"Note: GGUF export failed (this is optional): {e}")
    
    return trainer_stats

if __name__ == "__main__":
    result = fine_tune()