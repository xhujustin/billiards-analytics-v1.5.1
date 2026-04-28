"""
推論腳本 - 使用已訓練的 LoRA 模型進行推論。

支持原始 LoRA 權重推論和合併量化模型推論。
"""

import torch
from pathlib import Path
from typing import Optional

try:
    from unsloth import FastLanguageModel
except ImportError:
    print("Warning: unsloth not installed. Install with: pip install unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git")
    FastLanguageModel = None

from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


class InferenceEngine:
    """推論引擎 - 使用微調後的模型進行推論。"""
    
    def __init__(
        self,
        model_path: str,
        lora_path: Optional[str] = None,
        use_quantized: bool = False,
        max_seq_length: int = 2048,
    ):
        """
        初始化推論引擎。
        
        Args:
            model_path: 基礎模型路徑或合併模型路徑
            lora_path: LoRA 權重路徑（如果模型未合併）
            use_quantized: 是否使用 4-bit 量化
            max_seq_length: 最大序列長度
        """
        self.model_path = model_path
        self.lora_path = lora_path
        self.use_quantized = use_quantized
        self.max_seq_length = max_seq_length
        
        self.model = None
        self.tokenizer = None
        
    def load_model(self):
        """加載模型和分詞器。"""
        print(f"Loading model from {self.model_path}...")
        
        # 加載分詞器
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        
        # 加載模型
        if self.use_quantized:
            # 使用 4-bit 量化加載
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                load_in_4bit=True,
                torch_dtype=torch.bfloat16,
                bnb_4bit_compute_dtype=torch.bfloat16,
                device_map="auto",
            )
        else:
            # 使用 FP16 加載
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                torch_dtype=torch.bfloat16,
                device_map="auto",
            )
        
        # 如果指定了 LoRA 路徑，則加載 LoRA 權重
        if self.lora_path:
            print(f"Loading LoRA weights from {self.lora_path}...")
            self.model = PeftModel.from_pretrained(
                self.model,
                self.lora_path,
                torch_dtype=torch.bfloat16,
            )
        
        self.model.eval()
        print("Model loaded successfully")
        
        return self.model, self.tokenizer
    
    def generate(
        self,
        prompt: str,
        max_length: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.95,
        top_k: int = 50,
    ) -> str:
        """
        生成文本。
        
        Args:
            prompt: 輸入提示語
            max_length: 最大生成長度
            temperature: 采樣溫度
            top_p: Top-P 采樣參數
            top_k: Top-K 采樣參數
            
        Returns:
            生成的文本
        """
        if self.model is None:
            self.load_model()
        
        # 編碼輸入
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            max_length=self.max_seq_length,
            truncation=True,
        ).to(self.model.device)
        
        # 生成
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_length=max_length,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        
        # 解碼輸出
        generated_text = self.tokenizer.decode(
            outputs[0],
            skip_special_tokens=True,
        )
        
        # 移除提示語，只保留生成部分
        response = generated_text[len(prompt):].strip()
        
        return response
    
    def chat(
        self,
        messages: list,
        max_length: int = 512,
        temperature: float = 0.7,
    ) -> str:
        """
        對話推論模式。
        
        Args:
            messages: 對話列表，格式 [{"role": "user", "content": "..."}, ...]
            max_length: 最大生成長度
            temperature: 采樣溫度
            
        Returns:
            模型回複
        """
        if self.model is None:
            self.load_model()
        
        # 格式化為聊天提示語
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt += f"{role}: {content}\n"
        
        prompt += "assistant: "
        
        return self.generate(prompt, max_length, temperature)


def main():
    """示例使用代碼。"""
    
    # 方案 1: 使用合併的模型（推薦用於推論）
    print("=" * 60)
    print("Option 1: Using merged model")
    print("=" * 60)
    
    inference = InferenceEngine(
        model_path="./merged_model",
        use_quantized=True,  # 使用 4-bit 量化
    )
    inference.load_model()
    
    # 生成推論
    prompt = "台球比賽中的重要技巧是什麼？"
    response = inference.generate(prompt, max_length=256)
    print(f"\nPrompt: {prompt}")
    print(f"Response: {response}")
    
    # 方案 2: 使用 LoRA 權重（用於進一步微調）
    print("\n" + "=" * 60)
    print("Option 2: Using LoRA weights with base model")
    print("=" * 60)
    
    inference2 = InferenceEngine(
        model_path="unsloth/llama-3.1-8b-bnb-4bit",
        lora_path="./lora_weights",
        use_quantized=True,
    )
    inference2.load_model()
    
    # 對話推論
    messages = [
        {"role": "user", "content": "我是台球初學者，應該如何練習基本技巧？"}
    ]
    response = inference2.chat(messages, max_length=256)
    print(f"\nUser: {messages[0]['content']}")
    print(f"Assistant: {response}")


if __name__ == "__main__":
    main()
