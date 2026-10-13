# Results Log

Every measured number this project produces, with the method that produced it.

**Rules (master spec section 13.1):**
1. Every number has a method: what was measured, where the clock started and
   stopped, how many trials, on which build, on which device.
2. Latency is median and 95th percentile. Never a mean alone, never a best case.
3. A single stage is never reported as the total.
4. Accuracy carries its denominator.
5. Rates near zero carry a confidence interval.
6. **This file is the only source for slides.** A figure not here does not go
   on a slide or into a viva answer.

Rows are written ONLY by `harness/analysis/results_writer.py`.

| Metric | Value | Method | Trials | Build | Date |
|---|---|---|---|---|---|
| memory recall hit@1 | 19/24 = 79.2% | scripted day, 24 events, 24 questions, hybrid filter-then-rank (harness/bench/memory_recall_bench.py) | 24 | — | 2026-10-12 |
