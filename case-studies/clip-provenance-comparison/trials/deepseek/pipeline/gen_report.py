"""Generate the results tables (subsection of report.md)."""
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
r = json.load(open(os.path.join(ROOT, "results.json")))

conf = [x for x in r if x["classification"] == "confident"]
likely = [x for x in r if x["classification"] == "likely"]
unc = [x for x in r if x["classification"] == "uncertain"]
none = [x for x in r if x["classification"] == "not-identified"]


def rowfmt(x):
    src = f"master_{x['source_master']:02d}"
    corr = ("%.2f" % x["audio_corr"]) if x["audio_corr"] is not None else "—"
    begin = "%.1fs" % x["begin_time_s"] if x["classification"] != "not-identified" else "—"
    ratio = "%.2f" % x["ratio"]
    return (f"| {x['clip']} | {src} | {begin} | {ratio} | "
            f"{x['uniqueness']:.3f} | {x['score']:.3f} | {corr} |")


HEAD = ("| clip | source | begin | speed | uniqueness | score | audio-corr |\n"
        "|------|--------|-------|-------|-----------|-------|-----------|")

L = []
L.append("### 3.1 Confident (%d)\n" % len(conf))
L.append("_begin = start time in the master; speed = playback ratio (1.0 = unaltered); uniqueness/score = video match quality (lower = better); audio-corr = spectral cross-correlation (higher = better, '—' = no audio)._")
L.append("")
L.append(HEAD)
for x in conf:
    L.append(rowfmt(x))

L.append("")
L.append("### 3.2 Likely (%d)\n" % len(likely))
L.append(HEAD)
for x in likely:
    L.append(rowfmt(x))

L.append("")
L.append("### 3.3 Uncertain (%d)\n" % len(unc))
L.append(HEAD)
for x in unc:
    L.append(rowfmt(x))

L.append("")
L.append("### 3.4 Not identified (likely external) (%d)\n" % len(none))
L.append(HEAD)
for x in none:
    L.append(rowfmt(x))

open(os.path.join(ROOT, "results_tables.md"), "w").write("\n".join(L))
print("wrote results_tables.md;", Counter(x['classification'] for x in r))