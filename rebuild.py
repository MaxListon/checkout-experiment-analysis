"""One-command reproducible portfolio build, tests, checks and ZIP packaging."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import zipfile
from run_analysis import run, save_json
from build_readout import build as build_readout
from build_notebook import build as build_notebook
from verify_project import verify

ROOT=Path(__file__).resolve().parents[1]


def package(root=ROOT):
    destination=root.parent/'checkout-experiment-portfolio.zip'
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(root.rglob('*')):
            if not path.is_file() or any(part in {'.venv','__pycache__','.git','.ipynb_checkpoints'} for part in path.parts) or path.name=='.DS_Store':continue
            z.write(path,path.relative_to(root))
    return destination


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--regenerate',action='store_true',help='Regenerate source simulation before analysis')
    args=parser.parse_args()
    run(regenerate=args.regenerate)
    build_readout();build_notebook()
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v'],capture_output=True,text=True)
    save_json(ROOT/'results/test_results.json',{'status':'PASS' if result.returncode==0 else 'FAIL',
        'command':'python -m unittest discover -s tests -v','output':result.stdout+result.stderr})
    if result.returncode:
        print(result.stdout+result.stderr);raise SystemExit(result.returncode)
    print('Behavioral regression tests PASS.')
    verify()
    print('Packaged:',package())


if __name__=='__main__':main()
