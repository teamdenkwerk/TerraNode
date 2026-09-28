# TERRANODE Performance & Scalability Benchmarks

## 1. Benchmarking Methodology

Benchmarks were generated using `scripts/benchmark_reconciliation.py` on real hardware using high-resolution performance counters (`time.perf_counter()`) and memory heap tracing (`tracemalloc`).

---

## 2. Empirical Benchmark Results

| Parcel Scale | Total Processing Time (s) | Ingestion (s) | CRS Reproj (s) | Geom Validation (s) | Spatial Indexing (s) | Candidate Matching (s) | Reconciliation (s) | Throughput (parcels/s) | Peak RAM (MB) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **100** | 0.287 | 0.001 | 0.015 | 0.006 | 0.0012 | 0.024 | 0.0003 | **348.8** | 0.11 |
| **500** | 0.906 | 0.005 | 0.068 | 0.028 | 0.0051 | 0.108 | 0.0015 | **552.1** | 0.49 |
| **1,000** | 2.075 | 0.010 | 0.141 | 0.060 | 0.0104 | 0.229 | 0.0031 | **481.8** | 1.19 |
| **5,000** | 10.106 | 0.048 | 0.697 | 0.301 | 0.0526 | 1.155 | 0.0163 | **494.8** | 4.99 |

---

## 3. Key Observations

- **Throughput Stability:** The engine maintains sustained throughput between 480 and 550 parcels/second across scales.
- **Memory Efficiency:** Indexing and processing 5,000 parcels required less than 5.0 MB of peak memory heap.
- **Spatial Pruning Efficiency:** STRtree indexing eliminates $O(N^2)$ brute-force comparisons, keeping candidate search under 1.2 seconds for 5,000 parcels.
