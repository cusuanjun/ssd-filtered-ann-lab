#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

// Bounded metadata-only policy. No workload name or ground truth is inspected.
inline uint64_t budget_from_selectivity(uint64_t base, double fraction) {
  const double factor = std::sqrt(0.10 / std::max(fraction, 1.0 / 1024.0));
  const uint64_t cap = std::max<uint64_t>(base, 4096);
  const double proposed = std::max<double>(base, base * factor);
  return std::min(cap, static_cast<uint64_t>(std::ceil(proposed / 32.0)) * 32);
}

template <class Store>
uint64_t adaptive_budget(const Store &store, const void *labels, uint64_t base) {
  const uint64_t n = store.size();
  if (!n) return base;
  const uint64_t count = std::min<uint64_t>(1024, n);
  uint64_t matches = 0;
  // Fixed evenly spaced sample, reproducible and independent of query order.
  for (uint64_t j = 0; j < count; ++j)
    matches += store.passes(static_cast<uint32_t>((j * n + n / 2) / count), labels);
  return budget_from_selectivity(base, static_cast<double>(matches) / count);
}
