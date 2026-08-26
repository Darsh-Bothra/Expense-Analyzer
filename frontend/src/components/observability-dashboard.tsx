"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { Activity, AlertCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiError, fmtCost, fmtMs, fmtTokens, fmtTime } from "@/lib/format";
import { ANALYZE_STEPS, type ObservabilitySnapshot } from "@/lib/types";

const POLL_MS = 2000;
const STEP_ORDER = [...ANALYZE_STEPS];

const latencyConfig = {
  avg_ms: { label: "Average", color: "var(--chart-1)" },
} satisfies ChartConfig;

export function ObservabilityDashboard() {
  const [data, setData] = useState<ObservabilitySnapshot | null>(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch("/api/backend/observability");
        const payload = await res.json();
        if (!res.ok) {
          throw new Error(apiError(payload, "Could not load observability"));
        }
        if (!cancelled) {
          setData(payload as ObservabilitySnapshot);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not reach GET /observability",
          );
        }
      } finally {
        if (!cancelled) setReady(true);
      }
    }

    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const chartRows = useMemo(() => {
    if (!data?.avg_ms) return [];
    return STEP_ORDER.filter((step) => data.avg_ms[step] != null).map((step) => ({
      step,
      avg_ms: data.avg_ms[step],
    }));
  }, [data]);

  const empty = !data || data.request_count === 0;

  return (
    <div className="h-full overflow-y-auto">
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-8 sm:px-6">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">Observability</h1>
          <Badge variant="outline" className="font-mono text-[11px]">
            poll 2s
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          Per-step latency and LLM token/cost for recent{" "}
          <span className="font-mono text-xs">POST /analyze</span> and{" "}
          <span className="font-mono text-xs">POST /chat</span> calls. Timings are
          persisted in SQLite and survive restarts. Upload a CSV on the{" "}
          <Link href="/" className="underline underline-offset-4">
            Analyzer
          </Link>{" "}
          to record timings.
        </p>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Backend unreachable</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {!ready ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
      ) : null}

      {ready && empty && !error ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center gap-2 py-16 text-center">
            <Activity className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm font-medium">No analyze runs yet</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              Timings are persisted in SQLite on the API and survive uvicorn
              restarts.
            </p>
          </CardContent>
        </Card>
      ) : null}

      {ready && !empty && data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Requests</CardDescription>
                <CardTitle className="font-mono text-2xl">
                  {data.request_count}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Bottleneck</CardDescription>
                <CardTitle className="font-mono text-2xl">
                  {data.bottleneck?.step ?? "—"}
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  avg {fmtMs(data.bottleneck?.avg_ms)} · max{" "}
                  {fmtMs(data.bottleneck?.max_ms)}
                </p>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Avg total</CardDescription>
                <CardTitle className="font-mono text-2xl">
                  {fmtMs(data.avg_ms?.total)}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Tokens (in / out)</CardDescription>
                <CardTitle className="font-mono text-2xl">
                  {fmtTokens(data.tokens_in)} / {fmtTokens(data.tokens_out)}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Est. cost</CardDescription>
                <CardTitle className="font-mono text-2xl">
                  {fmtCost(data.cost_usd)}
                </CardTitle>
              </CardHeader>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Average latency by step</CardTitle>
              <CardDescription>
                Mean milliseconds across recorded analyze calls
              </CardDescription>
            </CardHeader>
            <CardContent>
              {chartRows.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No step averages yet.
                </p>
              ) : (
                <ChartContainer
                  config={latencyConfig}
                  className="aspect-auto h-[280px]"
                >
                  <BarChart data={chartRows} margin={{ left: 8, right: 8 }}>
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="step" tickLine={false} axisLine={false} />
                    <YAxis
                      tickLine={false}
                      axisLine={false}
                      width={48}
                      unit="ms"
                    />
                    <ChartTooltip
                      content={
                        <ChartTooltipContent
                          formatter={(value) => fmtMs(Number(value))}
                        />
                      }
                    />
                    <Bar
                      dataKey="avg_ms"
                      fill="var(--color-avg_ms)"
                      radius={[6, 6, 0, 0]}
                    />
                  </BarChart>
                </ChartContainer>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent runs</CardTitle>
              <CardDescription>Last 50 analyze and chat requests</CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Endpoint</TableHead>
                    <TableHead>File</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>OK</TableHead>
                    <TableHead>Slowest</TableHead>
                    <TableHead>Total</TableHead>
                    <TableHead>Tokens</TableHead>
                    <TableHead>Cost</TableHead>
                    {STEP_ORDER.filter((s) => s !== "total").map((step) => (
                      <TableHead key={step} className="font-mono text-xs">
                        {step}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(data.recent ?? []).map((run, i) => (
                    <TableRow key={`${run.at}-${i}`}>
                      <TableCell className="whitespace-nowrap font-mono text-xs">
                        {fmtTime(run.at)}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="font-mono text-[11px]">
                          {run.endpoint ?? "—"}
                        </Badge>
                      </TableCell>
                      <TableCell>{run.filename ?? "—"}</TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="font-mono text-[11px]">
                          {run.insights_source ?? "—"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={run.ok ? "secondary" : "destructive"}>
                          {run.ok ? "ok" : "fail"}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {run.slowest_step ?? "—"}
                      </TableCell>
                      <TableCell className="font-mono">{fmtMs(run.total_ms)}</TableCell>
                      <TableCell className="font-mono text-xs">
                        {run.tokens_in || run.tokens_out
                          ? `${fmtTokens(run.tokens_in)}/${fmtTokens(run.tokens_out)}`
                          : "—"}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {fmtCost(run.cost_usd)}
                      </TableCell>
                      {STEP_ORDER.filter((s) => s !== "total").map((step) => (
                        <TableCell key={step} className="font-mono text-xs">
                          {fmtMs(run.steps_ms?.[step])}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
    </div>
  );
}
