"""Download public safetensors weights once; never upload user photos."""
import json
from pathlib import Path

MODEL_ID = 'depth-anything/Depth-Anything-V2-Small-hf'
MODEL_REVISION = '5426e4f0f36572d16453bbda7a8389317b1bef99'
MODEL_DIR = Path(__file__).resolve().parent / 'models' / 'depth-anything-v2-small'


def download():
    from huggingface_hub import snapshot_download
    revision = MODEL_REVISION
    snapshot_download(MODEL_ID, revision=revision, local_dir=MODEL_DIR, token=False,
                      allow_patterns=['config.json', 'preprocessor_config.json', 'model.safetensors', 'README.md'])
    (MODEL_DIR/'provenance.json').write_text(json.dumps({'model_id':MODEL_ID,'revision':revision},indent=2))
    print(f'Model ready: {MODEL_DIR}', flush=True)


if __name__ == '__main__':
    download()
