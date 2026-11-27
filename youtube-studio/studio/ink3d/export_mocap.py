"""Export CMU mocap clips (studio.whatif.mocap) as JSON joint tracks for the Blender scenes.

    python -m studio.ink3d.export_mocap 143_17 111_06 ...   -> projects/ink_proto3d/mocap/<id>.json
"""

import json
import sys
from pathlib import Path

from studio.whatif import mocap

OUT = Path(__file__).resolve().parents[2] / "projects" / "ink_proto3d" / "mocap"


def main(ids: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for cid in ids:
        fr = mocap.load_cmu(cid, 30)
        data = [{j: [round(v, 4) for v in p] for j, p in f.items()} for f in fr]
        (OUT / f"{cid}.json").write_text(json.dumps(data), encoding="utf-8")
        print(cid, len(fr), "frames")


if __name__ == "__main__":
    main(sys.argv[1:])
