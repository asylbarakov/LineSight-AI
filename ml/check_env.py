"""Read-only CPU-friendly environment diagnostics; no installation or downloads."""
import argparse
import importlib.metadata
import json
import platform
import shutil
import sys


def check_environment():
    report = {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "packages": {},
        "ffmpeg": shutil.which("ffmpeg"),
        "cuda_available": False,
        "gpus": [],
    }
    for name in ("torch", "Pillow", "pytest", "huggingface_hub", "ultralytics", "opencv-python", "opencv-python-headless"):
        try:
            report["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            report["packages"][name] = None
    if report["packages"]["torch"]:
        try:
            import torch
            report["torch_cuda_build"] = torch.version.cuda
            report["cuda_available"] = torch.cuda.is_available()
            if report["cuda_available"]:
                for index in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(index)
                    report["gpus"].append({"index": index, "name": props.name, "vram_bytes": props.total_memory})
        except Exception as exc:
            report["torch_error"] = f"{type(exc).__name__}: {exc}"
    return report


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(check_environment(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
