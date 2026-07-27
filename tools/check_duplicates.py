"""Flag near-duplicate logs within each class.

Duplicates inflate the dataset count without adding coverage and distort
evaluation scores. Run before adding new examples.

    python tools/check_duplicates.py [threshold]
"""
import collections
import difflib
import glob
import os
import sys

THRESHOLD = float(sys.argv[1]) if len(sys.argv) > 1 else 0.90
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dataset")

by_class = collections.defaultdict(list)
for path in sorted(glob.glob(os.path.join(ROOT, "*", "*.log"))):
    by_class[os.path.basename(os.path.dirname(path))].append(path)

found = 0
for cls, files in sorted(by_class.items()):
    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            a = open(files[i]).read()
            b = open(files[j]).read()
            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            if ratio >= THRESHOLD:
                found += 1
                print(f"{ratio:.3f}  {cls}/{os.path.basename(files[i])}"
                      f"  ~=  {cls}/{os.path.basename(files[j])}")

print(f"\n{found} pair(s) at or above {THRESHOLD:.2f} similarity."
      if found else f"\nNo pairs at or above {THRESHOLD:.2f} similarity.")
sys.exit(1 if found else 0)
