"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  Landmark,
  Loader2,
  MessageSquare,
  Upload,
  Wallet,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { ExpenseChat, DATASET_STORAGE_KEY } from "@/components/expense-chat";
import { SpendCharts } from "@/components/spend-charts";
import {
  filterRows,
  toCategoryPie,
  toDailyTrend,
  toFrequentMerchant,
  toHighestMerchant,
  toKpis,
  toMerchantBars,
  uniqueCategories,
} from "@/lib/aggregate";
import { apiError, inr } from "@/lib/format";
import type { AnalyzeResponse, DatasetResponse, WorkbookInspect } from "@/lib/types";
import { cn } from "@/lib/utils";

const TX_INITIAL = 10;
const TX_STEP = 10;

export function AnalyzerDashboard() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [period, setPeriod] = useState("all");
  const [category, setCategory] = useState("all");
  const [wide, setWide] = useState<boolean | null>(null);
  const [savedDatasetId, setSavedDatasetId] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(false);
  const [txLimit, setTxLimit] = useState(TX_INITIAL);
  const [sheets, setSheets] = useState<string[]>([]);
  const [sheet, setSheet] = useState("");
  const [workbookFormat, setWorkbookFormat] = useState<string | null>(null);
  const [inspecting, setInspecting] = useState(false);

  useEffect(() => {
    const id = window.localStorage.getItem(DATASET_STORAGE_KEY);
    if (id) setSavedDatasetId(id);
  }, []);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1280px)");
    const sync = () => setWide(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    setTxLimit(TX_INITIAL);
  }, [period, category, data?.dataset_id]);

  function rememberDataset(id: string | null | undefined) {
    if (!id) return;
    window.localStorage.setItem(DATASET_STORAGE_KEY, id);
    setSavedDatasetId(id);
  }

  async function loadDataset(id: string) {
    setError("");
    setRestoring(true);
    try {
      const res = await fetch(`/api/backend/datasets/${id}`);
      const payload = await res.json();
      if (!res.ok) {
        throw new Error(apiError(payload, "Could not load saved statement"));
      }
      const dataset = payload as DatasetResponse;
      rememberDataset(dataset.dataset_id);
      setData(dataset);
      setPeriod("all");
      setCategory("all");
    } catch (err) {
      window.localStorage.removeItem(DATASET_STORAGE_KEY);
      setSavedDatasetId(null);
      setError(err instanceof Error ? err.message : "Could not load saved statement");
    } finally {
      setRestoring(false);
    }
  }

  async function onFileChosen(picked: File | null) {
    setFile(picked);
    setSheets([]);
    setSheet("");
    setWorkbookFormat(null);
    if (!picked) return;
    if (!picked.name.toLowerCase().endsWith(".xlsx")) {
      setWorkbookFormat("csv");
      return;
    }
    setInspecting(true);
    setError("");
    try {
      const body = new FormData();
      body.append("file", picked);
      const res = await fetch("/api/backend/inspect-workbook", {
        method: "POST",
        body,
      });
      const payload = await res.json();
      if (!res.ok) {
        throw new Error(apiError(payload, "Could not read workbook sheets"));
      }
      const inspected = payload as WorkbookInspect;
      setSheets(inspected.sheets);
      setWorkbookFormat(inspected.format);
      setSheet(inspected.suggested_sheet ?? inspected.sheets[0] ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read workbook sheets");
    } finally {
      setInspecting(false);
    }
  }

  async function onAnalyze(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setData(null);
    setPeriod("all");
    setCategory("all");
    if (!file) {
      setError("Choose a CSV or Excel (.xlsx) file first.");
      return;
    }
    const body = new FormData();
    body.append("file", file);
    if (sheet) body.append("sheet", sheet);
    setLoading(true);
    try {
      const res = await fetch("/api/backend/analyze", { method: "POST", body });
      const payload = await res.json();
      if (!res.ok) {
        throw new Error(apiError(payload, "Analyze failed"));
      }
      const analyzed = payload as AnalyzeResponse;
      setData(analyzed);
      rememberDataset(analyzed.dataset_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not analyze file");
    } finally {
      setLoading(false);
    }
  }

  const categories = useMemo(
    () => (data?.rows ? uniqueCategories(data.rows) : []),
    [data],
  );
  const filtered = useMemo(
    () => (data?.rows ? filterRows(data.rows, { period, category }) : []),
    [data, period, category],
  );
  const kpis = useMemo(() => toKpis(filtered), [filtered]);
  const pie = useMemo(() => toCategoryPie(filtered), [filtered]);
  const bars = useMemo(() => toMerchantBars(filtered), [filtered]);
  const trend = useMemo(() => toDailyTrend(filtered), [filtered]);
  const highest = useMemo(() => toHighestMerchant(filtered), [filtered]);
  const frequent = useMemo(() => toFrequentMerchant(filtered), [filtered]);
  const transactionsSorted = useMemo(
    () => [...filtered].sort((a, b) => b.date.localeCompare(a.date)),
    [filtered],
  );
  const visibleTransactions = transactionsSorted.slice(0, txLimit);
  const remainingTx = transactionsSorted.length - visibleTransactions.length;

  const chat = (
    <ExpenseChat
      datasetId={data?.dataset_id}
      insights={data?.insights}
      insightsSource={data?.insights_source}
    />
  );

  return (
    <div className="flex min-h-0 flex-1">
      <div className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl space-y-5 px-4 py-6 lg:px-6">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col gap-1">
              <h1 className="text-2xl font-semibold tracking-tight">Analyzer</h1>
              <p className="text-sm text-muted-foreground">
                Review spend on the left. Ask the statement on the right.
              </p>
            </div>
            {wide === false ? (
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline" size="sm">
                  <MessageSquare className="h-4 w-4" />
                  Chat
                </Button>
              </SheetTrigger>
              <SheetContent
                side="right"
                className="w-full gap-0 p-0 sm:max-w-md"
                showCloseButton
              >
                <SheetTitle className="sr-only">Ask the statement</SheetTitle>
                {chat}
              </SheetContent>
            </Sheet>
            ) : null}
          </div>

          <Card>
            <CardContent className="pt-6">
              <form
                className="flex flex-col gap-3 sm:flex-row sm:items-end"
                onSubmit={onAnalyze}
              >
                <div className="grid min-w-0 flex-1 gap-2">
                  <Label htmlFor="statement">Statement file</Label>
                  <input
                    ref={inputRef}
                    id="statement"
                    type="file"
                    accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    className="hidden"
                    onChange={(e) => onFileChosen(e.target.files?.[0] ?? null)}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    className="justify-start font-normal"
                    onClick={() => inputRef.current?.click()}
                  >
                    <Upload className="h-4 w-4" />
                    <span className="truncate">
                      {file ? file.name : "Choose file…"}
                    </span>
                  </Button>
                </div>
                {sheets.length > 0 ? (
                  <div className="grid min-w-0 sm:w-56 gap-2">
                    <Label htmlFor="sheet">Worksheet</Label>
                    <Select value={sheet} onValueChange={setSheet}>
                      <SelectTrigger id="sheet" className="w-full">
                        <SelectValue placeholder="Choose sheet" />
                      </SelectTrigger>
                      <SelectContent>
                        {sheets.map((name) => (
                          <SelectItem key={name} value={name}>
                            {name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ) : null}
                <Button
                  type="submit"
                  disabled={loading || inspecting}
                  className="sm:w-32"
                >
                  {loading || inspecting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      {inspecting ? "Reading" : "Analyzing"}
                    </>
                  ) : (
                    "Analyze"
                  )}
                </Button>
              </form>
              <p className="mt-2 text-xs text-muted-foreground">
                {workbookFormat === "paytm"
                  ? "Paytm workbook detected. Pick Passbook Payment History, not Summary."
                  : "CSV or Excel (.xlsx). Generic sheets need date, merchant, amount, type (Credit / Debit). For Paytm, pick Passbook Payment History, not Summary."}
              </p>
              {error ? (
                <Alert variant="destructive" className="mt-4">
                  <AlertTitle>Could not analyze</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              ) : null}
            </CardContent>
          </Card>

          {!data ? (
            <Card className="border-dashed">
              <CardContent className="flex flex-col items-center gap-2 py-16 text-center">
                <Wallet className="h-8 w-8 text-muted-foreground" />
                <p className="text-sm font-medium">No statement loaded</p>
                <p className="max-w-sm text-sm text-muted-foreground">
                  Upload{" "}
                  <span className="font-mono text-xs">
                    sample_data/transactions.csv
                  </span>{" "}
                  or{" "}
                  <span className="font-mono text-xs">
                    sample_data/paytm_passbook_sample.xlsx
                  </span>{" "}
                  (choose Passbook Payment History) to populate the dashboard and unlock
                  chat.
                </p>
                {savedDatasetId ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="mt-2"
                    disabled={restoring}
                    onClick={() => loadDataset(savedDatasetId)}
                  >
                    {restoring ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Loading last upload
                      </>
                    ) : (
                      "Continue with last upload"
                    )}
                  </Button>
                ) : null}
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Period
                  </p>
                  <ToggleGroup
                    type="single"
                    value={period}
                    onValueChange={(value) => {
                      if (value) setPeriod(value);
                    }}
                    variant="outline"
                    size="sm"
                  >
                    <ToggleGroupItem value="all">All</ToggleGroupItem>
                    <ToggleGroupItem value="7d">Last 7 days</ToggleGroupItem>
                    <ToggleGroupItem value="month">Last month</ToggleGroupItem>
                  </ToggleGroup>
                </div>
                <div className="grid w-full gap-2 sm:max-w-xs">
                  <Label>By category</Label>
                  <Select value={category} onValueChange={setCategory}>
                    <SelectTrigger>
                      <SelectValue placeholder="All categories" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All categories</SelectItem>
                      {categories.map((name) => (
                        <SelectItem key={name} value={name}>
                          {name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <KpiCard
                  label="Income"
                  value={inr(kpis.income)}
                  icon={ArrowUpRight}
                  tone="positive"
                />
                <KpiCard
                  label="Expense"
                  value={inr(kpis.expense)}
                  icon={ArrowDownRight}
                  tone="negative"
                />
                <KpiCard
                  label="Savings"
                  value={inr(kpis.savings)}
                  icon={Landmark}
                  tone={kpis.savings >= 0 ? "positive" : "negative"}
                />
                <KpiCard
                  label="Transactions"
                  value={String(kpis.transaction_count)}
                  icon={Wallet}
                />
              </div>

              {filtered.length === 0 ? (
                <Alert>
                  <AlertTitle>No matching transactions</AlertTitle>
                  <AlertDescription>
                    Try a wider period or clear the category filter.
                  </AlertDescription>
                </Alert>
              ) : (
                <SpendCharts pie={pie} bars={bars} trend={trend} />
              )}

              <div className="grid gap-4 lg:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Merchants</CardTitle>
                    <CardDescription>
                      Highest spend and visit frequency
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {highest ? (
                      <p className="text-sm">
                        Highest spend{" "}
                        <span className="font-medium">{highest.name}</span>{" "}
                        <span className="font-mono text-muted-foreground">
                          {inr(highest.amount)}
                        </span>
                      </p>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No debit spend in this filter.
                      </p>
                    )}
                    {frequent ? (
                      <p className="text-sm">
                        Most frequent{" "}
                        <span className="font-medium">{frequent.name}</span>{" "}
                        <span className="text-muted-foreground">
                          {frequent.count} times
                        </span>
                      </p>
                    ) : null}
                    <Separator />
                    <ul className="space-y-2 text-sm">
                      {bars.map((m) => (
                        <li
                          key={m.name}
                          className="flex items-center justify-between gap-3"
                        >
                          <span>{m.name}</span>
                          <span className="font-mono text-muted-foreground">
                            {inr(m.amount)} · {m.count}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Categories</CardTitle>
                    <CardDescription>Share of filtered expenses</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {pie.length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        No expense categories in this filter.
                      </p>
                    ) : (
                      pie.map((c) => (
                        <div key={c.name} className="space-y-1.5">
                          <div className="flex items-center justify-between text-sm">
                            <span>{c.name}</span>
                            <span className="font-mono text-muted-foreground">
                              {inr(c.amount)} · {c.pct_of_expense}%
                            </span>
                          </div>
                          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                            <div
                              className="h-full rounded-full bg-foreground/80"
                              style={{
                                width: `${Math.min(c.pct_of_expense, 100)}%`,
                              }}
                            />
                          </div>
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Transactions</CardTitle>
                  <CardDescription>
                    {transactionsSorted.length === 0
                      ? "No rows in this filter"
                      : `Showing ${visibleTransactions.length} of ${transactionsSorted.length} · newest first`}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Date</TableHead>
                          <TableHead>Merchant</TableHead>
                          <TableHead>Amount</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Category</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {visibleTransactions.map((row, i) => (
                          <TableRow key={`${row.date}-${row.merchant}-${i}`}>
                            <TableCell className="font-mono text-xs">
                              {row.date}
                            </TableCell>
                            <TableCell>{row.merchant}</TableCell>
                            <TableCell className="font-mono">
                              {inr(row.amount)}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={
                                  row.type === "Credit" ? "secondary" : "outline"
                                }
                              >
                                {row.type}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-muted-foreground">
                              {row.category}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                  {remainingTx > 0 ? (
                    <div className="flex justify-center border-t border-border pt-4">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setTxLimit((n) =>
                            Math.min(n + TX_STEP, transactionsSorted.length),
                          )
                        }
                      >
                        Load more ({remainingTx} remaining)
                      </Button>
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>

      {wide ? (
        <aside className="flex h-full w-[24rem] shrink-0 flex-col border-l border-border">
          {chat}
        </aside>
      ) : null}
    </div>
  );
}

function KpiCard({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  tone?: "positive" | "negative";
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardDescription>{label}</CardDescription>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <p
          className={cn(
            "font-mono text-2xl font-semibold tracking-tight",
            tone === "positive" && "text-emerald-400",
            tone === "negative" && "text-rose-400",
          )}
        >
          {value}
        </p>
      </CardContent>
    </Card>
  );
}
