import os
import torch
from unsloth import FastLanguageModel
from transformers import TrainingArguments
from trl import SFTTrainer
from datasets import load_dataset
from datetime import datetime

def log_progress(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] 🐰 {msg}")

def format_instruction(example):
    """Format the instruction, input, and output into a single text string."""
    # Format: <s>[INST] instruction + input [/INST] output </s>
    instruction = example["instruction"]
    input_text = example["input"]
    output = example["output"]
    
    if input_text:
        prompt = f"{instruction}\n{input_text}"
    else:
        prompt = instruction
        
    # Format for Mistral chat template
    example["text"] = f"<s>[INST] {prompt} [/INST] {output}</s>"
    return example

def fine_tune():
    log_progress("🚀 Starting fine-tuning process...")
    
    # Load and format dataset
    dataset = load_dataset("json", data_files={"train": "training_data.jsonl"})["train"]
    dataset = dataset.map(format_instruction)
    
    print("Dataset features:", dataset.features)
    print("First formatted example:", dataset[0]["text"][:200] + "...")
    
    # Configure model loading with explicit dtypes
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/mistral-7b-v0.3-bnb-4bit",
        max_seq_length=2048,
        load_in_4bit=True,
        quantization_config={
            "load_in_4bit": True,
            "bnb_4bit_compute_dtype": torch.bfloat16
        }
    )
    
    # Add LoRA adapters with explicit dtype
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing=True,
    )
    
    # Training arguments with mixed precision settings
    training_args = TrainingArguments(
        output_dir="./finetuned_model",
        num_train_epochs=3,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        logging_steps=1,
        optim="adamw_8bit",
        bf16=True,  # Use bfloat16 precision
        torch_compile=False,  # Disable torch compile for stability
    )
    
    # Initialize trainer with the correct dataset field
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        dataset_text_field="text",  # Now using the formatted text field
        args=training_args,
        tokenizer=tokenizer,
        max_seq_length=2048,
        packing=False,
    )
    
    # Train
    log_progress("🏃 Training model...")
    trainer.train()
    
    # Save the model
    log_progress("💾 Saving fine-tuned model...")
    # Save model to a specific directory
    output_dir = os.path.join(os.getcwd(), "finetuned_model")
    os.makedirs(output_dir, exist_ok=True)
    trainer.save_model(output_dir)
    
    # Force sync the saved files
    if os.path.exists(output_dir):
        # Save a marker file to verify directory contents
        with open(os.path.join(output_dir, "model_saved.txt"), "w") as f:
            f.write("Model saved successfully")
    
    log_progress("✨ Fine-tuning complete!")
    return {"status": "success", "model_path": output_dir}

if __name__ == "__main__":
    result = fine_tune()
    print(f"Model saved to: {result['model_path']}")