import type { TransactionRow } from "@/lib/types";

function parseDate(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function maxDateFromRows(rows: TransactionRow[]) {
  let max: Date | null = null;
  for (const row of rows) {
    const d = parseDate(row.date);
    if (!max || d > max) max = d;
  }
  return max;
}

export function uniqueCategories(rows: TransactionRow[]) {
  return [...new Set(rows.map((r) => r.category))].sort();
}

export function filterRows(
  rows: TransactionRow[],
  { period = "all", category = "all" }: { period?: string; category?: string } = {},
) {
  const maxDate = maxDateFromRows(rows);
  if (!maxDate) return [];

  let start: Date | null = null;
  const end = maxDate;

  if (period === "7d") {
    start = new Date(maxDate);
    start.setDate(start.getDate() - 6);
  } else if (period === "month") {
    start = new Date(maxDate.getFullYear(), maxDate.getMonth(), 1);
  }

  return rows.filter((row) => {
    const d = parseDate(row.date);
    if (start && d < start) return false;
    if (d > end) return false;
    if (category !== "all" && row.category !== category) return false;
    return true;
  });
}

export function toKpis(rows: TransactionRow[]) {
  let income = 0;
  let expense = 0;
  for (const row of rows) {
    if (row.type === "Credit") income += row.amount;
    else if (row.type === "Debit") expense += row.amount;
  }
  return {
    income,
    expense,
    savings: income - expense,
    transaction_count: rows.length,
  };
}

export function toCategoryPie(rows: TransactionRow[]) {
  const totals = new Map<string, number>();
  let expense = 0;
  for (const row of rows) {
    if (row.type !== "Debit") continue;
    expense += row.amount;
    totals.set(row.category, (totals.get(row.category) || 0) + row.amount);
  }
  return [...totals.entries()]
    .map(([name, amount]) => ({
      name,
      amount,
      pct_of_expense: expense ? Math.round((amount / expense) * 1000) / 10 : 0,
    }))
    .sort((a, b) => b.amount - a.amount);
}

function merchantTotals(rows: TransactionRow[]) {
  const totals = new Map<string, { amount: number; count: number }>();
  for (const row of rows) {
    if (row.type !== "Debit") continue;
    const prev = totals.get(row.merchant) || { amount: 0, count: 0 };
    prev.amount += row.amount;
    prev.count += 1;
    totals.set(row.merchant, prev);
  }
  return [...totals.entries()].map(([name, stats]) => ({ name, ...stats }));
}

export function toMerchantBars(rows: TransactionRow[], limit = 5) {
  return merchantTotals(rows)
    .sort((a, b) => b.amount - a.amount || a.name.localeCompare(b.name))
    .slice(0, limit);
}

export function toHighestMerchant(rows: TransactionRow[]) {
  const list = merchantTotals(rows).sort(
    (a, b) => b.amount - a.amount || a.name.localeCompare(b.name),
  );
  return list[0] ?? null;
}

export function toFrequentMerchant(rows: TransactionRow[]) {
  const list = merchantTotals(rows).sort(
    (a, b) =>
      b.count - a.count || b.amount - a.amount || a.name.localeCompare(b.name),
  );
  return list[0] ?? null;
}

export function toDailyTrend(rows: TransactionRow[]) {
  const byDate = new Map<
    string,
    { date: string; expense: number; income: number }
  >();
  for (const row of rows) {
    const prev = byDate.get(row.date) || {
      date: row.date,
      expense: 0,
      income: 0,
    };
    if (row.type === "Debit") prev.expense += row.amount;
    else if (row.type === "Credit") prev.income += row.amount;
    byDate.set(row.date, prev);
  }
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
}
