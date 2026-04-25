# YOLO 使用 GPU / CUDA 排查指南

## 問題現象

- 開啟 YOLO 後 CPU 使用率接近 100%。
- NVIDIA GPU 幾乎沒有 Compute 使用率。
- 後端啟動日誌顯示 `cuda_available=False` 或 `YOLO inference device: cpu`。

## 判斷重點

專案程式會在 PyTorch 能看到 CUDA 時自動使用 GPU。若仍跑 CPU，通常不是 YOLO 程式邏輯問題，而是 Python 虛擬環境中的 PyTorch 不是 CUDA 版，或 `.venv` 指向的基底 Python 已不存在。

## 快速檢查

在專案根目錄執行：

```bat
.\.venv\Scripts\python.exe backend\test-program\utils\check_yolo_gpu.py
```

正常輸出應包含：

```text
cuda_available: True
cuda_device_name: NVIDIA GeForce RTX 2070 SUPER
```

若看到 `cuda_available: False`，YOLO 會跑 CPU。

## 修復流程

1. 先確認 NVIDIA 驅動存在：

```bat
nvidia-smi
```

2. 若 `.venv` 壞掉或 Python 無法啟動，刪除 `.venv` 後重新安裝：

```bat
rmdir /s /q .venv
install.bat
```

3. `install.bat` 會在偵測到 `nvidia-smi` 時優先安裝 CUDA 版 PyTorch：

```bat
python -m pip install --upgrade --force-reinstall -r requirements-cuda.txt
```

`requirements-cuda.txt` 只放 PyTorch CUDA wheel 來源與 `torch` / `torchvision`，主 `requirements.txt` 維持一般套件清單，避免所有套件都改從 PyTorch index 查找。

4. 啟動後端時確認日誌：

```text
YOLO inference device: cuda:0
cuda_available=True
```

## 環境變數

可在 `backend\.env` 指定 YOLO device：

```env
YOLO_DEVICE=auto
YOLO_HALF=auto
```

可用值：

```text
YOLO_DEVICE=auto | cpu | cuda | cuda:0 | 0
YOLO_HALF=auto | true | false
```

## 輸出格式

GPU 檢查腳本輸出格式：

```text
python: C:\...\billiards-analytics-v1.5\.venv\Scripts\python.exe
torch: 2.x.x+cu128
torch_cuda: 12.8
cuda_available: True
cuda_device_count: 1
cuda_device_name: NVIDIA GeForce RTX 2070 SUPER
```

## 更新紀錄

- 04/25: '新增 YOLO GPU/CUDA 啟動檢查與 CUDA 版 PyTorch 安裝流程'
  - 範例：啟動後端時應顯示 `YOLO inference device: cuda:0`。
  - 規範用法：先用 `check_yolo_gpu.py` 確認 PyTorch 可見 CUDA，再啟動 YOLO 辨識。
  - 輸出格式：如上方 GPU 檢查腳本輸出格式。
- 04/25: '新增 requirements-cuda.txt 管理 CUDA 版 PyTorch'
  - 範例：`install.bat` 偵測 NVIDIA GPU 後執行 `python -m pip install --upgrade --force-reinstall -r requirements-cuda.txt`。
  - 規範用法：主 `requirements.txt` 放一般依賴，`requirements-cuda.txt` 只放 CUDA 版 PyTorch 來源與套件。
  - 輸出格式：安裝後 `torch_cuda` 應顯示 CUDA 版本，`cuda_available` 應為 `True`。
