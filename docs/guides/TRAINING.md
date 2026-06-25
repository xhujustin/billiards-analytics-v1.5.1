# Unsloth LLM 微調訓練指南

## 06/21: '移除練習設定與統計畫面的玩家資訊'

### 範例

練習流程不再要求使用者於訓練頁選擇或輸入玩家：

```text
訓練中心 -> 選擇練習類型 -> 設定訓練題目 -> 開始練習
```

### 規範用法

- 練習設定頁不顯示「玩家資訊」、玩家名稱輸入框、既有玩家選擇或提示文字。
- 練習設定頁段落標題不顯示 `1`、`2` 編號，直接顯示題目或類型標題。
- 練習中 header 與統計面板不顯示「玩家」或「匿名玩家」資訊。
- 若目前有登入帳號，前端仍以 `signedInPlayerName` 傳送 `player_name` 與錄影 `players`，用於後端紀錄與統計歸屬；訪客或無帳號名稱時送空值。
- 此調整不新增後端 API，也不改變練習題目、投影或錄影啟停流程。

### 輸出格式

```json
{
  "mode": "accuracy",
  "player_name": "登入帳號名稱",
  "pattern_layout": {}
}
```

## 06/18: '準度訓練投影改用一般練習座標轉換'

### 範例

準度訓練或球型練習啟動後，前端仍傳送相對座標：

```json
{
  "pattern_layout": {
    "coordinate_space": "relative",
    "balls": [{ "x": 0.28, "y": 0.5, "r": 24, "type": "cue" }],
    "route_segments": [{ "type": "cue_to_contact", "points": [[0.28, 0.5], [0.52, 0.5]] }],
    "cue_landing_point": [0.62, 0.5]
  }
}
```

後端會把相對座標先換成相機 `table_roi` 上的實際點，再直接走 homography，與一般練習 planner 路線的投影方式一致。

### 規範用法

- 此規則只影響 `coordinate_space: "relative"` 的準度訓練與球型練習靜態投影。
- 投影層不再對袋口做特殊吸附，不再額外放大，也不再套球位內縮。
- 即時 YOLO 規劃路線與校正矩陣不受此設定影響。
- 若投影仍整體偏小或偏移，應優先修正 table ROI / projector homography，而不是在練習投影層補償。

### 輸出格式

```text
投影輸出：setup_balls、route_segments、ghost_balls、cue_landing_point
座標流程：relative 0~1 -> table_roi camera point -> homography -> projector pixel
```

## 05/14: '新增訓練首頁分頁與推薦卡片'

> 此段為舊版首頁規格；目前已由 `06/05: '移除訓練首頁未接入 mock 內容'` 取代。

### 範例

訓練頁預設進入 `訓練推薦` 分頁，畫面包含四張推薦卡片與本週訓練總覽。

```text
訓練頁 -> 訓練推薦
訓練頁 -> 我的計畫 -> 內容建置中
訓練頁 -> 分析報告 -> 內容建置中
訓練頁 -> 歷史紀錄 -> 內容建置中
```

### 規範用法

- `準度訓練`、`走位訓練`、`一般練習` 暫時共用既有一般練習流程。
- `球型練習` 使用既有球型練習流程。
- 本週訓練總覽第一版使用固定示範資料，不新增後端 API。

### 輸出格式

首頁呈現：

```text
訓練推薦卡片：標題、簡述、標籤、主要按鈕
本週訓練總覽：訓練時間、完成局數、平均入袋率、最佳連續成功、AI 綜合評分
```

## 06/05: '移除訓練首頁未接入 mock 內容'

### 範例

訓練首頁只保留已接入正式流程的訓練入口：

```text
訓練中心 -> 準度訓練
訓練中心 -> 球型練習
訓練中心 -> 一般練習
```

### 規範用法

- 首頁不顯示 `訓練推薦`、`我的計畫`、`分析報告`、`歷史紀錄` 等尚未接資料的分頁。
- 首頁不顯示固定示範資料的本週訓練總覽。
- 首頁不顯示 `返回即時影像` 按鈕；頁面切換統一使用頂部導覽。
- `走位訓練` 不再作為獨立入口顯示；若未來要恢復，需先接入專屬流程、資料來源與紀錄輸出。
- 可保留原卡片視覺風格，但卡片只能指向已可執行的練習流程。

### 輸出格式

```text
訓練模式卡片：標題、簡述、標籤、主要按鈕
```

## 06/05: '統一練習設定頁與好友對戰建立頁風格'

### 範例

從訓練首頁進入任一練習流程後，設定頁沿用遊戲頁 `建立好友對戰` 的版型：

```text
練習模式 - 準度訓練
準度訓練題目
開始練習
```

### 規範用法

- 設定頁外層使用 `friend-match-page`、`friend-match-panel` 與 `friend-setup-section` 的視覺語言。
- 返回按鈕、段落標題、分段按鈕與狀態資訊需與 `遊戲 > 建立好友對戰` 保持一致。
- 練習頁可保留專屬內容，例如準度題目資訊與球型練習球檯編輯器，但外框與操作節奏需一致。
- 設定頁底部只保留 `開始練習` 主要按鈕，不提供匿名跳過入口。

### 輸出格式

```tsx
<div className="practice-page practice-setup-page friend-match-page">
  <div className="friend-match-panel practice-setup-panel">
    <section className="friend-setup-section">...</section>
  </div>
</div>
```

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
