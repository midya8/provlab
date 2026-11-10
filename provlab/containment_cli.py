"""Installed comparison/replay entrypoint, sharing only strict JSON and atomic IO conventions."""

import argparse, json, os, sys, tempfile
from pathlib import Path
from .input import load


def main():
    ap = argparse.ArgumentParser(
        description="Bounded set-CQ containment, frozen counterexamples and exact atom-subset minima"
    )
    ap.add_argument("input", help="JSON path or -")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--output")
    args = ap.parse_args()
    try:
        cap = 16 * 1024 * 1024 if args.verify else 65536
        if args.input == "-":
            raw = sys.stdin.buffer.read(cap + 1)
        else:
            with Path(args.input).open("rb") as f:
                raw = f.read(cap + 1)
        if len(raw) > cap:
            raise ValueError("input exceeds byte limit")
        data = load(raw.decode("utf-8"))
        if args.verify:
            from .containment_verify import verify

            verify(data)
            out = {"valid": True, "schema": "provlab-containment-v1"}
        else:
            from .containment import analyze

            out = analyze(data)
        text = json.dumps(out, indent=2, allow_nan=False) + "\n"
        if len(text.encode()) > 16 * 1024 * 1024:
            raise ValueError("report exceeds byte limit")
        if args.output:
            p = Path(args.output)
            tmp = None
            try:
                with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", dir=p.parent, delete=False
                ) as f:
                    tmp = f.name
                    f.write(text)
                os.replace(tmp, p)
            finally:
                if tmp and os.path.exists(tmp):
                    os.unlink(tmp)
        else:
            sys.stdout.write(text)
        return 0
    except (ValueError, TypeError, OSError, RecursionError) as e:
        print("provlab-containment: " + str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
