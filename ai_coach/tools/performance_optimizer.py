"""
Qwen 模型推論性能優化工具

優化策略：
1. 知識蒸餾 (Knowledge Distillation) - 用小模型逼近大模型
2. 權重剪枝 (Pruning) - 移除冗餘參數
3. 量化優化 (Quantization) - 4-bit vs 8-bit vs FP16 對比
4. 批批處理 (Batch Processing) - 提升吞吐量
5. KV-Cache 優化 - 減少推論延遲
"""

import torch
import torch.nn as nn
import torch.nn.utils.prune as prune
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset
from pathlib import Path
from typing import Any, Tuple, Optional, Dict, List
from dataclasses import dataclass
import time
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """推論性能指標。"""
    
    inference_time_ms: float  # 平均推論延遲（毫秒）
    throughput_samples_per_sec: float  # 吞吐量
    memory_usage_mb: float  # 峰值內存使用
    latency_p95_ms: float  # P95 延遲
    latency_p99_ms: float  # P99 延遲
    
    def __str__(self):
        return f"""
Performance Metrics:
  - Avg Latency: {self.inference_time_ms:.2f}ms
  - Throughput: {self.throughput_samples_per_sec:.2f} samples/sec
  - Peak Memory: {self.memory_usage_mb:.2f}MB
  - P95 Latency: {self.latency_p95_ms:.2f}ms
  - P99 Latency: {self.latency_p99_ms:.2f}ms
        """


class KnowledgeDistiller:
    """知識蒸餾 - 用小模型逼近大模型。"""
    
    def __init__(
        self,
        teacher_model_name: str = "unsloth/Qwen2.5-7B-bnb-4bit",
        student_model_name: str = "unsloth/Qwen2.5-3B-bnb-4bit",
        temperature: float = 4.0,
        alpha: float = 0.7,  # 蒸餾損失權重 (0.7 * distill + 0.3 * task_loss)
    ):
        """初始化蒸餾器。
        
        Args:
            teacher_model_name: 教師模型（大模型）
            student_model_name: 學生模型（小模型）
            temperature: 蒸餾溫度（越高越軟化輸出分佈）
            alpha: 蒸餾損失權重
        """
        self.teacher_model_name = teacher_model_name
        self.student_model_name = student_model_name
        self.temperature = temperature
        self.alpha = alpha
        
        self.teacher_model: Any = None
        self.student_model: Any = None
        self.tokenizer: Any = None
    
    def load_models(self):
        """加載教師和學生模型。"""
        
        logger.info(f"Loading teacher model: {self.teacher_model_name}")
        self.teacher_model = AutoModelForCausalLM.from_pretrained(
            self.teacher_model_name,
            load_in_4bit=True,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        self.teacher_model.eval()
        
        logger.info(f"Loading student model: {self.student_model_name}")
        self.student_model = AutoModelForCausalLM.from_pretrained(
            self.student_model_name,
            load_in_4bit=True,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        
        self.tokenizer = AutoTokenizer.from_pretrained(self.student_model_name)
        
        return self.teacher_model, self.student_model, self.tokenizer
    
    def distillation_loss(
        self,
        student_logits: torch.Tensor,
        teacher_logits: torch.Tensor,
        target_ids: torch.Tensor,
    ) -> torch.Tensor:
        """計算蒸餾損失。
        
        組合：
            - KL 散度（軟化教師-學生匹配）
            - 交叉熵（任務損失）
        """
        
        # 軟損失（KL 散度）- 讓學生模型學習教師的輸出分佈
        student_probs = torch.nn.functional.log_softmax(
            student_logits / self.temperature, dim=-1
        )
        teacher_probs = torch.nn.functional.softmax(
            teacher_logits / self.temperature, dim=-1
        )
        soft_loss = torch.nn.functional.kl_div(student_probs, teacher_probs, reduction="batchmean")
        
        # 硬損失（交叉熵）- 任務特定損失
        hard_loss = torch.nn.functional.cross_entropy(student_logits, target_ids)
        
        # 加權組合
        total_loss = self.alpha * soft_loss + (1 - self.alpha) * hard_loss
        
        return total_loss, soft_loss, hard_loss
    
    def train_distilled_model(
        self,
        train_dataset: Dataset,
        output_dir: str = "./distilled_model",
        num_epochs: int = 3,
        batch_size: int = 4,
        learning_rate: float = 5e-5,
    ):
        """訓練蒸餾模型。
        
        Args:
            train_dataset: 訓練數據集
            output_dir: 輸出目錄
            num_epochs: 訓練輪數
            batch_size: 批大小
            learning_rate: 學習率
        """
        
        self.load_models()
        teacher_model = self.teacher_model
        student_model = self.student_model
        tokenizer = self.tokenizer
        if teacher_model is None or student_model is None or tokenizer is None:
            raise RuntimeError("Models and tokenizer must be loaded before distillation")
        
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True
        )
        
        # 優化器
        optimizer = AdamW(
            student_model.parameters(),
            lr=learning_rate
        )
        
        # 學習率調度
        total_steps = len(train_loader) * num_epochs
        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=0,
            num_training_steps=total_steps
        )
        
        student_model.train()
        teacher_model.eval()
        
        logger.info(f"Starting distillation training for {num_epochs} epochs")
        
        for epoch in range(num_epochs):
            total_loss = 0
            
            for batch_idx, batch in enumerate(train_loader):
                
                # 前向傳遞
                with torch.no_grad():
                    teacher_outputs = teacher_model(**batch)
                    teacher_logits = teacher_outputs.logits
                
                student_outputs = student_model(**batch)
                student_logits = student_outputs.logits
                
                # 計算蒸餾損失
                loss, soft_loss, hard_loss = self.distillation_loss(
                    student_logits,
                    teacher_logits,
                    batch["labels"]
                )
                
                # 後向傳遞
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                scheduler.step()
                
                total_loss += loss.item()
                
                if (batch_idx + 1) % 10 == 0:
                    logger.info(
                        f"Epoch {epoch+1}/{num_epochs}, Batch {batch_idx+1}, "
                        f"Loss: {loss.item():.4f}, "
                        f"Soft: {soft_loss.item():.4f}, "
                        f"Hard: {hard_loss.item():.4f}"
                    )
            
            avg_loss = total_loss / len(train_loader)
            logger.info(f"Epoch {epoch+1} completed. Average loss: {avg_loss:.4f}")
        
        # 保存蒸餾模型
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        student_model.save_pretrained(output_path / "student_model")
        tokenizer.save_pretrained(output_path / "student_model")
        
        logger.info(f"Distilled model saved to {output_path}")


class PruningOptimizer:
    """權重剪枝 - 移除冗餘參數。"""
    
    @staticmethod
    def structured_pruning(
        model: nn.Module,
        pruning_ratio: float = 0.3,  # 移除 30% 參數
    ) -> nn.Module:
        """結構化剪枝（按層剪枝）。
        
        Args:
            model: 要剪枝的模型
            pruning_ratio: 剪枝比例 (0-1)
            
        Returns:
            剪枝後的模型
        """
        
        logger.info(f"Applying structured pruning (ratio: {pruning_ratio})")
        
        parameters_to_prune = [
            (module, "weight")
            for name, module in model.named_modules()
            if isinstance(module, nn.Linear)
        ]
        
        if not parameters_to_prune:
            logger.warning("No Linear layers found for pruning")
            return model
        
        # 應用全局非結構化剪枝
        prune.global_unstructured(
            parameters_to_prune,
            pruning_method=prune.L1Unstructured,
            amount=pruning_ratio,
        )
        
        # 移除剪枝蒙版，永久化權重
        for module, _ in parameters_to_prune:
            prune.remove(module, "weight")
        
        logger.info(f"Pruning completed. Model parameters reduced by ~{pruning_ratio*100:.1f}%")
        
        return model
    
    @staticmethod
    def calculate_sparsity(model: nn.Module) -> float:
        """計算模型稀疏度（零參數比例）。
        
        Returns:
            稀疏度百分比（0-100）
        """
        
        total = 0
        zeros = 0
        
        for param in model.parameters():
            total += param.data.numel()
            zeros += (param.data == 0).sum().item()
        
        if total == 0:
            return 0.0
        
        sparsity = (zeros / total) * 100
        return sparsity


class QuantizationAnalyzer:
    """量化分析 - 對比不同量化策略。"""
    
    @staticmethod
    def benchmark_quantization_schemes(
        model_name: str = "unsloth/Qwen2.5-7B-bnb-4bit",
        input_ids: torch.Tensor = None,
        num_runs: int = 10,
    ) -> Dict[str, PerformanceMetrics]:
        """對比不同的量化方案。
        
        方案：
            1. 原生 FP16
            2. 8-bit 量化
            3. 4-bit 量化
            
        Returns:
            各方案的性能指標
        """
        
        results = {}
        
        # 方案 1: FP16 (原生)
        logger.info("Testing FP16 (Native)")
        model_fp16 = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            device_map="auto",
        )
        model_fp16.eval()
        
        metrics_fp16 = QuantizationAnalyzer._benchmark_model(
            model_fp16,
            input_ids,
            num_runs=num_runs,
            scheme_name="FP16"
        )
        results["fp16"] = metrics_fp16
        
        del model_fp16
        torch.cuda.empty_cache()
        
        # 方案 2: 8-bit 量化
        logger.info("Testing 8-bit Quantization")
        model_8bit = AutoModelForCausalLM.from_pretrained(
            model_name,
            load_in_8bit=True,
            device_map="auto",
        )
        model_8bit.eval()
        
        metrics_8bit = QuantizationAnalyzer._benchmark_model(
            model_8bit,
            input_ids,
            num_runs=num_runs,
            scheme_name="8-bit"
        )
        results["8bit"] = metrics_8bit
        
        del model_8bit
        torch.cuda.empty_cache()
        
        # 方案 3: 4-bit 量化
        logger.info("Testing 4-bit Quantization")
        model_4bit = AutoModelForCausalLM.from_pretrained(
            model_name,
            load_in_4bit=True,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        model_4bit.eval()
        
        metrics_4bit = QuantizationAnalyzer._benchmark_model(
            model_4bit,
            input_ids,
            num_runs=num_runs,
            scheme_name="4-bit"
        )
        results["4bit"] = metrics_4bit
        
        del model_4bit
        torch.cuda.empty_cache()
        
        return results
    
    @staticmethod
    def _benchmark_model(
        model: nn.Module,
        input_ids: torch.Tensor,
        num_runs: int = 10,
        scheme_name: str = "unknown",
    ) -> PerformanceMetrics:
        """對單個模型進行基準測試。"""
        
        times = []
        
        # 預熱
        with torch.no_grad():
            for _ in range(3):
                _ = model(input_ids)
        
        # 測試
        torch.cuda.synchronize()
        for _ in range(num_runs):
            start = time.perf_counter()
            
            with torch.no_grad():
                _ = model(input_ids)
            
            torch.cuda.synchronize()
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)
        
        times = sorted(times)
        avg_time = sum(times) / len(times)
        throughput = 1000 / avg_time  # samples/sec
        
        # 內存使用
        memory_mb = torch.cuda.max_memory_allocated() / 1024 / 1024
        
        metrics = PerformanceMetrics(
            inference_time_ms=avg_time,
            throughput_samples_per_sec=throughput,
            memory_usage_mb=memory_mb,
            latency_p95_ms=times[int(len(times) * 0.95)],
            latency_p99_ms=times[int(len(times) * 0.99)],
        )
        
        logger.info(f"{scheme_name} - {metrics}")
        
        return metrics


class BatchInferenceOptimizer:
    """批推論優化 - 提升吞吐量。"""
    
    def __init__(self, model_name: str, max_batch_size: int = 32):
        """初始化批推論優化器。
        
        Args:
            model_name: 模型名稱
            max_batch_size: 最大批大小
        """
        self.model_name = model_name
        self.max_batch_size = max_batch_size
        self.model: Any = None
        self.tokenizer: Any = None
    
    def load_model(self):
        """加載模型。"""
        
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            load_in_4bit=True,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model.eval()
    
    def batch_generate(
        self,
        prompts: List[str],
        max_length: int = 256,
        batch_size: Optional[int] = None,
    ) -> List[str]:
        """批量生成。
        
        Args:
            prompts: 提示語列表
            max_length: 最大生成長度
            batch_size: 批大小（None 則用 max_batch_size）
            
        Returns:
            生成的文本列表
        """
        
        if self.model is None:
            self.load_model()
        model = self.model
        tokenizer = self.tokenizer
        if model is None or tokenizer is None:
            raise RuntimeError("Model and tokenizer must be loaded before batch generation")
        
        if batch_size is None:
            batch_size = self.max_batch_size
        
        results = []
        
        # 分批處理
        for i in range(0, len(prompts), batch_size):
            batch_prompts = prompts[i:i+batch_size]
            
            # 編碼
            inputs = tokenizer(
                batch_prompts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            ).to(model.device)
            
            # 生成
            with torch.no_grad():
                output_ids = model.generate(
                    **inputs,
                    max_length=max_length,
                    do_sample=True,
                    top_p=0.95,
                    temperature=0.7,
                    pad_token_id=tokenizer.eos_token_id,
                )
            
            # 解碼
            batch_results = tokenizer.batch_decode(
                output_ids,
                skip_special_tokens=True,
            )
            
            results.extend(batch_results)
        
        return results


class KVCacheOptimizer:
    """KV-Cache 優化 - 減少推論延遲。
    
    原理：在生成過程中快取已計算的 Key 和 Value，避免重複計算。
    """
    
    @staticmethod
    def enable_kv_cache(model: nn.Module) -> nn.Module:
        """啟用 KV-Cache。"""
        
        # Transformers 庫在 generate() 時默認啟用
        logger.info("KV-Cache enabled (via use_cache=True in generate())")
        return model
    
    @staticmethod
    def benchmark_with_kv_cache(
        model_name: str,
        input_ids: torch.Tensor,
        num_runs: int = 10,
    ) -> Tuple[PerformanceMetrics, PerformanceMetrics]:
        """對比有/無 KV-Cache 的性能。
        
        Returns:
            (metrics_with_cache, metrics_without_cache)
        """
        
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            load_in_4bit=True,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        model.eval()
        
        # 有 KV-Cache
        times_with = []
        for _ in range(num_runs):
            start = time.perf_counter()
            with torch.no_grad():
                _ = model.generate(
                    input_ids,
                    max_length=256,
                    use_cache=True,  # 啟用 KV-Cache
                )
            torch.cuda.synchronize()
            times_with.append((time.perf_counter() - start) * 1000)
        
        # 無 KV-Cache
        times_without = []
        for _ in range(num_runs):
            start = time.perf_counter()
            with torch.no_grad():
                _ = model.generate(
                    input_ids,
                    max_length=256,
                    use_cache=False,  # 禁用 KV-Cache
                )
            torch.cuda.synchronize()
            times_without.append((time.perf_counter() - start) * 1000)
        
        metrics_with = PerformanceMetrics(
            inference_time_ms=sum(times_with) / len(times_with),
            throughput_samples_per_sec=1000 / (sum(times_with) / len(times_with)),
            memory_usage_mb=torch.cuda.max_memory_allocated() / 1024 / 1024,
            latency_p95_ms=sorted(times_with)[int(len(times_with) * 0.95)],
            latency_p99_ms=sorted(times_with)[int(len(times_with) * 0.99)],
        )
        
        metrics_without = PerformanceMetrics(
            inference_time_ms=sum(times_without) / len(times_without),
            throughput_samples_per_sec=1000 / (sum(times_without) / len(times_without)),
            memory_usage_mb=torch.cuda.max_memory_allocated() / 1024 / 1024,
            latency_p95_ms=sorted(times_without)[int(len(times_without) * 0.95)],
            latency_p99_ms=sorted(times_without)[int(len(times_without) * 0.99)],
        )
        
        return metrics_with, metrics_without


def main():
    """性能優化演示。"""
    
    logger.info("="*60)
    logger.info("Qwen Model Inference Optimization")
    logger.info("="*60)
    
    # 假設我們有測試數據
    test_prompts = [
        "白球在左上角，標靶球在底袋位。建議動作：",
        "遊戲局勢：領先 2 分，剩餘 2 局。建議策略：",
    ]
    
    tokenizer = AutoTokenizer.from_pretrained("unsloth/Qwen2.5-7B-bnb-4bit")
    input_ids = tokenizer(test_prompts, return_tensors="pt")["input_ids"]
    
    # 01. 量化對比
    logger.info("\n[01] Quantization Comparison")
    logger.info("-" * 40)
    results = QuantizationAnalyzer.benchmark_quantization_schemes(
        num_runs=5
    )
    
    for scheme, metrics in results.items():
        logger.info(f"\n{scheme.upper()}: {metrics}")
    
    # 02. 批推論優化
    logger.info("\n[02] Batch Inference Optimization")
    logger.info("-" * 40)
    batch_optimizer = BatchInferenceOptimizer(
        "unsloth/Qwen2.5-7B-bnb-4bit",
        max_batch_size=8
    )
    batch_results = batch_optimizer.batch_generate(
        test_prompts * 4,  # 8 個提示語
        batch_size=4
    )
    logger.info(f"Batch generated {len(batch_results)} samples")
    
    logger.info("\n✅ Optimization benchmarks completed!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    main()
