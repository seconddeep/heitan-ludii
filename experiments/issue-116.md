# Issue 116: larger-board UCT execution benchmark

This report measures execution capability only. It does not inspect or summarize game outcomes.

## Feasibility map

| Board | 1k | 3k | 10k | 30k |
|---|---|---|---|---|
| 6x6 | feasible (3/3; median 4.1 min; max RSS 1.60 GiB) | feasible (3/3; median 11.6 min; max RSS 2.63 GiB) | feasible (3/3; median 38.8 min; max RSS 5.57 GiB) | borderline (3/3; median 122.1 min; max RSS 6.38 GiB) |
| 7x7 | feasible (3/3; median 5.4 min; max RSS 2.08 GiB) | feasible (3/3; median 15.6 min; max RSS 2.94 GiB) | feasible (3/3; median 49.5 min; max RSS 6.40 GiB) | borderline (3/3; median 153.1 min; max RSS 7.08 GiB) |
| 8x8 | feasible (3/3; median 9.8 min; max RSS 2.20 GiB) | feasible (3/3; median 28.4 min; max RSS 3.04 GiB) | feasible (3/3; median 90.9 min; max RSS 5.02 GiB) | borderline (3/3; median 279.9 min; max RSS 6.66 GiB) |

## Recommended production ceilings

| Board | Technically completable | Repeated-production recommendation |
|---|---:|---:|
| 6x6 | 30000 | 10000 |
| 7x7 | 30000 | 10000 |
| 8x8 | 30000 | 10000 |

Peak RSS relative to physical RAM supplies the machine-memory gate. JVM `-Xmx` and GC evidence are reported separately and are not treated as the same ratio.
