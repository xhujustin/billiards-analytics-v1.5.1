# Unsloth LLM 微調訓練指南

## 快速開始

### 1. 環境配置

```bash
# 安裝 unsloth 和依賴
pip install -r ai_coach/requirements_train.txt

# 或手動安裝
pip install unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git
```

### 2. 準備訓練數據

創建 `dataset.jsonl` 檔案，支持以下格式：

#### 格式 A：指令-輸入-輸出 (Instruction-Input-Output)
```json
{"instruction": "分析台球局面", "input": "白球在中線", "output": "建議走位方向..."}
```

#### 格式 B：純文本 (Plain Text)
```json
{"text": "台球比賽規則是..."}
```

#### 格式 C：對話格式 (Chat Messages)
```json
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

示例數據在 `ai_coach/dataset.example.jsonl`

### 3. 運行訓練

#### 基本訓練（推薦用 Llama-3.1-8B）
```bash
cd ai_coach
python train.py \
    --model unsloth/llama-3.1-8b-bnb-4bit \
    --dataset dataset.jsonl \
    --output ./lora_weights \
    --epochs 3
```

#### 或使用 Qwen-2.5-7B
```bash
python train.py \
    --model unsloth/Qwen2.5-7B-bnb-4bit \
    --dataset dataset.jsonl \
    --output ./lora_weights \
    --epochs 3
```

**訓練參數詳解：**
- `--model`: 基礎模型名稱
- `--dataset`: 訓練數據路徑 (JSONL 格式)
- `--output`: LoRA 權重輸出目錄
- `--epochs`: 訓練輪次 (默認 3)

### 4. 訓練配置

編輯 `train.py` 中的 `TrainingConfig` 類別來自定義：

```python
config = TrainingConfig(
    # LoRA 配置 (已優化)
    lora_rank=16,           # LoRA rank
    lora_alpha=32,          # LoRA alpha (2x rank)
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    
    # 訓練參數
    learning_rate=2e-4,     # 學習率
    num_train_epochs=3,     # 訓練輪次
    per_device_train_batch_size=4,
    per_device_eval_batch_size=4,
    gradient_accumulation_steps=2,
    
    # A100 優化
    bf16=True,              # 使用 BF16 混合精度
    tf32=False,
)
```

## 訓練流程

### 步驟 1：加載模型與 LoRA 設置
- 使用 unsloth 快速加載 4-bit 量化模型
- 配置 LoRA rank=16, alpha=32 (推薦值)
- 目標模組：q_proj, v_proj, k_proj, o_proj

### 步驟 2：數據預處理
- 加載 JSONL 數據集
- 自動格式化為訓練文本
- 支持多種輸入格式

### 步驟 3：訓練
- 使用 SFTTrainer (監督微調訓練器)
- BF16 混合精度 (A100 優化)
- 每 10 steps 記錄損失
- 每 100 steps 保存檢查點

### 步驟 4：保存 LoRA 權重
訓練完成後，LoRA 權重保存在指定目錄

## 模型合併與量化

### 自動合併（訓練腳本已包含）
訓練完成後腳本會自動執行：

1. **合併 LoRA 裡進基礎模型**
   ```python
   # 生成 FP16 合併模型
   merger.export_merged()  # 輸出到 ./merged_model
   ```

2. **導出 4-bit 量化版本**
   ```python
   # 為推論準備 4-bit 量化模型
   merger.export_quantized_4bit()
   ```

### 手動合併（如果需要）
```python
from train import ModelMerger, TrainingConfig

config = TrainingConfig()
merger = ModelMerger(config)

# 合併
model, tokenizer = merger.export_merged()

# 4-bit 量化導出
model, tokenizer = merger.export_quantized_4bit()
```

## 推論 (Inference)

### 使用合併的量化模型
```bash
python ai_coach/inference.py
```

### Python 代碼推論
```python
from ai_coach.inference import InferenceEngine

# 初始化引擎
engine = InferenceEngine(
    model_path="./merged_model",
    use_quantized=True,  # 4-bit 量化
)
engine.load_model()

# 生成文本
response = engine.generate(
    prompt="台球比賽的關鍵技巧是什麼？",
    max_length=256,
    temperature=0.7
)
print(response)
```

### 對話模式
```python
messages = [
    {"role": "user", "content": "我是初學者，如何練習?"}
]
response = engine.chat(messages)
```

## 性能優化

### A100 GPU 優化
- **BF16 混合精度**：啟用 `bf16=True` (約 50% 內存節省)
- **梯度積累**：`gradient_accumulation_steps=2` (有效批次大小翻倍)
- **Unsloth 加速**：比標準 PyTorch 快 2-3 倍
- **內存使用**：~20GB for Llama-8B (vs 40GB 不優化)

### 訓練時長估計
- **Llama-3.1-8B**
  - 1 epoch (1000 樣本): ~5 分鐘
  - 3 epochs: ~15 分鐘
- **Qwen-2.5-7B**
  - 1 epoch: ~4 分鐘
  - 3 epochs: ~12 分鐘

（在 A100 GPU 上）

## 問題排除

### CUDA 內存不足 (OOM)
```python
# 減小批次大小
per_device_train_batch_size=2
gradient_accumulation_steps=4  # 維持有效批次大小
```

### 模型加載失敗
```bash
# 清除 HF cache
rm -rf ~/.cache/huggingface/

# 重新下載
python train.py --model unsloth/llama-3.1-8b-bnb-4bit ...
```

### 訓練速度慢
- 確認 GPU 使用：`nvidia-smi`
- 啟用 BF16：`bf16=True`
- 減小 `max_seq_length` (目前設為 2048)

### 生成品質差
- 增加訓練數據量
- 增加訓練輪次：`num_train_epochs=5`
- 調整學習率：嘗試 1e-4 到 5e-4

## 文件結構

```
ai_coach/
├── train.py                 # 訓練主腳本
├── inference.py             # 推論腳本
├── requirements_train.txt   # 依賴包
├── dataset.example.jsonl    # 示例數據
├── lora_weights/            # LoRA 權重 (訓練後)
├── merged_model/            # 合併模型 (訓練後)
└── quantized_model/         # 量化模型 (訓練後)
```

## 進階用法

### 多 GPU 訓練
```bash
export CUDA_VISIBLE_DEVICES=0,1,2,3
python -m torch.distributed.launch --nproc_per_node=4 train.py
```

### 繼續訓練 (Continue Training)
```python
# 從保存的檢查點繼續
config.output_dir = "lora_weights"  # 包含檢查點
trainer = ModelTrainer(config)
trainer.load_model()
trainer.setup_lora()
# trainer 會自動檢測檢查點並繼續
trainer.train(dataset)
```

### 自定義數據格式
編輯 `DatasetLoader.prepare_text_data()` 方法以支持額外的格式。

## 參考文獻

- **Unsloth**: https://github.com/unslothai/unsloth
- **LoRA**: https://arxiv.org/abs/2106.09685
- **BF16**: https://en.wikipedia.org/wiki/Bfloat16_floating-point_format
- **4-bit Quantization**: https://arxiv.org/abs/2305.14314

## 許可證

該代碼遵循項目主許可證。
