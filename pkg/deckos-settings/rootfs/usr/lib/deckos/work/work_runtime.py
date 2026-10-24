"""Optional local artifact runtime, isolated from DeckOS's system Python."""
import argparse
import json
import os
import subprocess
from pathlib import Path

DATA = Path(os.environ.get('DECKOS_WORK_HOME') or Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'deckos/work')
RUNTIME = Path(os.environ.get('DECKOS_WORK_RUNTIME') or DATA/'runtime')
PYTHON = RUNTIME/'venv/bin/python'
CACHE = RUNTIME/'models'
DOCUMENT_PACKAGES = ['python-docx>=1.2,<2', 'python-pptx>=1,<2', 'openpyxl>=3.1,<4',
                     'reportlab>=4,<5', 'pypdf>=6,<7', 'Pillow>=11,<13']
IMAGE_PACKAGES = ['diffusers>=0.35,<0.39', 'transformers>=4.51,<5', 'accelerate>=1,<2',
                  'safetensors>=0.6,<1', 'sentencepiece>=0.2,<1']


def environment():
    return dict(os.environ, UV_CACHE_DIR=str(RUNTIME/'cache'), UV_PYTHON_INSTALL_DIR=str(RUNTIME/'python'),
                HF_HOME=str(CACHE), HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1')


def setup(images=False, device='rocm'):
    import shutil
    if not shutil.which('uv'):
        raise RuntimeError('Install uv first: sudo pacman -S uv')
    RUNTIME.mkdir(parents=True, exist_ok=True)
    env = environment()
    def call(args):
        print(' '.join(args), flush=True)
        subprocess.run(args, check=True, env=env)
    if not PYTHON.exists():
        call(['uv', 'venv', '--python', '3.12', str(RUNTIME/'venv')])
    call(['uv', 'pip', 'install', '--python', str(PYTHON), *DOCUMENT_PACKAGES])
    if images:
        index = {'rocm': 'https://download.pytorch.org/whl/rocm7.1',
                 'cuda': 'https://download.pytorch.org/whl/cu128',
                 'cpu': 'https://download.pytorch.org/whl/cpu'}[device]
        call(['uv', 'pip', 'install', '--python', str(PYTHON), 'torch==2.10.0', '--index-url', index])
        call(['uv', 'pip', 'install', '--python', str(PYTHON), *IMAGE_PACKAGES])
    print('Local runtime installed. Image weights download on first generation.', flush=True)


def status():
    if not PYTHON.exists():
        return {'documents': False, 'images': False, 'gpu': False, 'runtime': str(RUNTIME)}
    code = '''import importlib.util,json
modules=['docx','pptx','openpyxl','reportlab','pypdf','diffusers','torch']
s={k:bool(importlib.util.find_spec(k)) for k in modules}
s['gpu']=False
if s['torch']:
 import torch
 s['gpu']=torch.cuda.is_available()
 s['device']=torch.cuda.get_device_name(0) if s['gpu'] else 'CPU'
print(json.dumps(s))'''
    result = subprocess.run([str(PYTHON), '-c', code], capture_output=True, text=True, timeout=45, env=environment())
    if result.returncode:
        return {'documents': False, 'images': False, 'gpu': False, 'error': result.stderr[-1000:]}
    info = json.loads(result.stdout)
    return dict(documents=all(info.get(k) for k in ('docx','pptx','openpyxl','reportlab','pypdf')),
                images=all(info.get(k) for k in ('diffusers','torch')), gpu=info.get('gpu'),
                device=info.get('device','CPU'), runtime=str(RUNTIME))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup','status'])
    parser.add_argument('--images', action='store_true')
    parser.add_argument('--device', choices=['rocm','cuda','cpu'], default='rocm')
    args = parser.parse_args()
    if args.command == 'setup':
        setup(args.images, args.device)
    else:
        print(json.dumps(status()))
