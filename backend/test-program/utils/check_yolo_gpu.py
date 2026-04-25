import sys


def main() -> int:
    try:
        import torch
    except Exception as exc:
        print(f"ERROR torch import failed: {exc}")
        return 1

    print(f"python: {sys.executable}")
    print(f"torch: {torch.__version__}")
    print(f"torch_cuda: {torch.version.cuda}")
    print(f"cuda_available: {torch.cuda.is_available()}")
    print(f"cuda_device_count: {torch.cuda.device_count()}")
    if torch.cuda.is_available():
        print(f"cuda_device_name: {torch.cuda.get_device_name(0)}")
        return 0

    print("WARNING CUDA is not visible to PyTorch. YOLO will run on CPU.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
