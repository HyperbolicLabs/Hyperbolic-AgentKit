import json
import os
import sys
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

def run_inference(prompt):
    # Ensure CUDA is available and initialized
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available")
    
    # Force CUDA initialization
    torch.cuda.init()
    
    # Print CUDA info for debugging
    print(f"CUDA Device: {torch.cuda.get_device_name()}")
    print(f"CUDA Version: {torch.version.cuda}")
    
    # Always use the finetuned model directory for inference
    model_dir = os.path.abspath("./finetuned_model")
    
    try:
        # Load base model and tokenizer
        model = AutoModelForCausalLM.from_pretrained(
            model_dir,
            torch_dtype=torch.float16,
            device_map="auto"
        )
        tokenizer = AutoTokenizer.from_pretrained(model_dir)
        
        # Prepare input
        test_prompt = f"<s>[INST] {prompt} [/INST]"
        inputs = tokenizer(test_prompt, return_tensors="pt").to(model.device)
        
        # Generate
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.7,
                top_p=0.95,
                do_sample=True
            )
        
        # Decode output
        generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Format output
        output = {
            "prompt": prompt,
            "response": generated_text
        }
        
        # Save and print results
        with open("inference_output.json", "w") as f:
            json.dump(output, f, indent=2)
            
        print("\n=== Test Inference Results ===")
        print(f"Prompt: {output['prompt']}")
        print(f"Response: {output['response']}")
        print("============================\n")
        
        return output
        
    except Exception as e:
        print(f"Error during inference: {str(e)}")
        raise

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_inference.py \"your prompt here\"")
        sys.exit(1)
    
    prompt = sys.argv[1]
    run_inference(prompt)