#include "adaptive_budget.h"
#include <cassert>
#include <iostream>
struct Store {
  uint64_t n;
  uint64_t size() const { return n; }
  bool passes(uint32_t id, const void *p) const {
    assert(id < n);
    return p == nullptr || id % 100 == 0;
  }
};
int main() {
  assert(budget_from_selectivity(320, 1.0) == 320);
  assert(budget_from_selectivity(320, 0.1) == 320);
  assert(budget_from_selectivity(320, 0.0) <= 4096);
  assert(budget_from_selectivity(5000, 0.0) == 5000);
  uint64_t previous = 4096;
  for (int i = 0; i <= 1024; ++i) {
    auto b = budget_from_selectivity(320, i / 1024.0);
    assert(b >= 320 && b <= 4096 && b % 32 == 0);
    assert(b <= previous);
    previous = b;
  }
  int predicate = 1;
  for (uint64_t n : {0, 1, 2, 1023, 1024, 1000000}) {
    Store s{n};
    assert(adaptive_budget(s, nullptr, 320) == 320);
    assert(adaptive_budget(s, &predicate, 320) == adaptive_budget(s, &predicate, 320));
  }
  std::cout << "PASS: bounds, monotonicity, rounding, null filter, empty store, sample IDs, determinism\n";
}
