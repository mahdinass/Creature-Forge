"""Native pilot supervisor: fixed worklist, fail fast, no selective resume."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--stop-pilot',action='store_true')
    p.add_argument('--prior',default='artifacts/di1_pilot_v1');a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    common=[sys.executable,'-B','scripts/di1_study.py','run','--config',
            'experiments/causal_engineer/dev/di1/pilot_config.json','--stop-model',
            'experiments/causal_engineer/dev/di1/stopmap_dev_v1.json','--out',str(out)]
    if a.stop_pilot:
        common=[sys.executable,'-B','scripts/di1_stop_pilot.py','--prior',a.prior,'--out',str(out)]
    running=[]
    def launch(i):
        f=open(out/f'base{i}.log','xb')
        proc=subprocess.Popen([*common,'--index',str(i)],stdout=f,stderr=subprocess.STDOUT)
        running.append((i,proc,f))
    try:
        # First full equivalence before broad parallel execution.
        launch(0)
        if running[0][1].wait()!=0:raise RuntimeError('first base failed; no broad execution')
        running[0][2].close();running.clear()
        for i in range(1,8):launch(i)
        while running:
            for i,proc,f in list(running):
                rc=proc.poll()
                if rc is None:continue
                f.close();running.remove((i,proc,f))
                if rc:raise RuntimeError(f'base{i} engineering error exit{rc}; preserve all outputs')
            if running:time.sleep(1)
    finally:
        for _,proc,_ in running:proc.terminate()
        for _,proc,f in running:proc.wait();f.close()
    (out/'PILOT_COMPLETE').write_text('all eight fixed attempts completed\n')


if __name__=='__main__':main()
