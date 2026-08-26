import { describe, expect, it } from "vitest";

import {
  filterRows,
  maxDateFromRows,
  toCategoryPie,
  toDailyTrend,
  toFrequentMerchant,
  toHighestMerchant,
  toKpis,
  toMerchantBars,
  uniqueCategories,
} from "@/lib/aggregate";
import type { TransactionRow } from "@/lib/types";

const rows: TransactionRow[] = [
  { date: "2025-01-01", merchant: "Swiggy", amount: 450, type: "Debit", category: "Food" },
  { date: "2025-01-02", merchant: "Uber", amount: 280, type: "Debit", category: "Travel" },
  { date: "2025-01-04", merchant: "Salary", amount: 50000, type: "Credit", category: "Income" },
  { date: "2025-01-06", merchant: "Swiggy", amount: 320, type: "Debit", category: "Food" },
  { date: "2025-01-12", merchant: "Amazon", amount: 1500, type: "Debit", category: "Shopping" },
];

describe("maxDateFromRows", () => {
  it("returns the latest date", () => {
    const max = maxDateFromRows(rows);
    expect(max).not.toBeNull();
    expect(max!.toISOString().slice(0, 10)).toBe("2025-01-12");
  });

  it("returns null for empty input", () => {
    expect(maxDateFromRows([])).toBeNull();
  });
});

describe("uniqueCategories", () => {
  it("returns sorted unique categories", () => {
    expect(uniqueCategories(rows)).toEqual([
      "Food",
      "Income",
      "Shopping",
      "Travel",
    ]);
  });
});

describe("filterRows", () => {
  it("returns all rows when period is all", () => {
    expect(filterRows(rows, { period: "all", category: "all" })).toHaveLength(5);
  });

  it("filters by category", () => {
    const out = filterRows(rows, { period: "all", category: "Food" });
    expect(out).toHaveLength(2);
    expect(out.every((r) => r.category === "Food")).toBe(true);
  });

  it("filters last 7 days relative to max date", () => {
    const out = filterRows(rows, { period: "7d", category: "all" });
    // max date 2025-01-12; 7-day window starts 2025-01-06
    expect(out).toHaveLength(2);
    expect(out.map((r) => r.date).sort()).toEqual(["2025-01-06", "2025-01-12"]);
  });

  it("filters current month relative to max date", () => {
    const out = filterRows(rows, { period: "month", category: "all" });
    expect(out).toHaveLength(5); // all in January 2025
  });

  it("returns empty for empty input", () => {
    expect(filterRows([], { period: "all", category: "all" })).toEqual([]);
  });
});

describe("toKpis", () => {
  it("sums income and expense and computes savings", () => {
    const kpis = toKpis(rows);
    expect(kpis.income).toBe(50000);
    expect(kpis.expense).toBe(450 + 280 + 320 + 1500);
    expect(kpis.savings).toBe(50000 - (450 + 280 + 320 + 1500));
    expect(kpis.transaction_count).toBe(5);
  });

  it("handles empty input", () => {
    const kpis = toKpis([]);
    expect(kpis).toEqual({ income: 0, expense: 0, savings: 0, transaction_count: 0 });
  });
});

describe("toCategoryPie", () => {
  it("groups debits by category and computes pct of expense", () => {
    const pie = toCategoryPie(rows);
    const food = pie.find((c) => c.name === "Food")!;
    expect(food.amount).toBe(450 + 320);
    const expense = 450 + 280 + 320 + 1500;
    expect(food.pct_of_expense).toBe(Math.round(((450 + 320) / expense) * 1000) / 10);
    // Income credits are excluded
    expect(pie.find((c) => c.name === "Income")).toBeUndefined();
  });

  it("returns empty for no debits", () => {
    expect(toCategoryPie([])).toEqual([]);
  });
});

describe("toMerchantBars / toHighestMerchant / toFrequentMerchant", () => {
  it("groups debit totals and counts per merchant", () => {
    const bars = toMerchantBars(rows);
    const swiggy = bars.find((m) => m.name === "Swiggy")!;
    expect(swiggy.amount).toBe(450 + 320);
    expect(swiggy.count).toBe(2);
  });

  it("limits to top N by amount", () => {
    expect(toMerchantBars(rows, 2)).toHaveLength(2);
  });

  it("picks highest spend merchant by amount", () => {
    expect(toHighestMerchant(rows)?.name).toBe("Amazon");
  });

  it("picks most frequent merchant by count", () => {
    expect(toFrequentMerchant(rows)?.name).toBe("Swiggy");
  });

  it("returns null when no debits", () => {
    expect(toHighestMerchant([])).toBeNull();
    expect(toFrequentMerchant([])).toBeNull();
  });
});

describe("toDailyTrend", () => {
  it("aggregates income/expense per date and sorts ascending", () => {
    const trend = toDailyTrend(rows);
    expect(trend).toHaveLength(5);
    expect(trend[0].date).toBe("2025-01-01");
    expect(trend[2]).toEqual({ date: "2025-01-04", expense: 0, income: 50000 });
    expect(trend.map((t) => t.date)).toEqual([...trend.map((t) => t.date)].sort());
  });

  it("returns empty for no rows", () => {
    expect(toDailyTrend([])).toEqual([]);
  });
});
