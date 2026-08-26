"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { inr } from "@/lib/format";

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

type PieRow = { name: string; amount: number; pct_of_expense: number };
type BarRow = { name: string; amount: number; count: number };
type TrendRow = { date: string; expense: number; income: number };

const merchantConfig = {
  amount: { label: "Spend", color: "var(--chart-1)" },
} satisfies ChartConfig;

const trendConfig = {
  expense: { label: "Expense", color: "var(--chart-4)" },
  income: { label: "Income", color: "var(--chart-2)" },
} satisfies ChartConfig;

function Empty({ message }: { message: string }) {
  return (
    <p className="py-10 text-center text-sm text-muted-foreground">{message}</p>
  );
}

export function SpendCharts({
  pie,
  bars,
  trend,
}: {
  pie: PieRow[];
  bars: BarRow[];
  trend: TrendRow[];
}) {
  const pieConfig = Object.fromEntries(
    pie.map((row, i) => [
      row.name,
      { label: row.name, color: CHART_COLORS[i % CHART_COLORS.length] },
    ]),
  ) satisfies ChartConfig;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Spend by category</CardTitle>
          <CardDescription>Debit share of filtered expenses</CardDescription>
        </CardHeader>
        <CardContent>
          {pie.length === 0 ? (
            <Empty message="No expense data for this filter." />
          ) : (
            <ChartContainer config={pieConfig} className="aspect-auto h-[280px]">
              <PieChart>
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      formatter={(value) => inr(Number(value))}
                    />
                  }
                />
                <Pie
                  data={pie.map((row, i) => ({
                    ...row,
                    fill: CHART_COLORS[i % CHART_COLORS.length],
                  }))}
                  dataKey="amount"
                  nameKey="name"
                  innerRadius={58}
                  outerRadius={92}
                  strokeWidth={2}
                >
                  {pie.map((entry, i) => (
                    <Cell
                      key={entry.name}
                      fill={CHART_COLORS[i % CHART_COLORS.length]}
                    />
                  ))}
                </Pie>
                <ChartLegend content={<ChartLegendContent nameKey="name" />} />
              </PieChart>
            </ChartContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Top merchants</CardTitle>
          <CardDescription>Highest debit totals in view</CardDescription>
        </CardHeader>
        <CardContent>
          {bars.length === 0 ? (
            <Empty message="No merchant spend for this filter." />
          ) : (
            <ChartContainer
              config={merchantConfig}
              className="aspect-auto h-[280px]"
            >
              <BarChart data={bars} margin={{ left: 8, right: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="name" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} width={48} />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      formatter={(value) => inr(Number(value))}
                    />
                  }
                />
                <Bar
                  dataKey="amount"
                  fill="var(--color-amount)"
                  radius={[6, 6, 0, 0]}
                />
              </BarChart>
            </ChartContainer>
          )}
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Daily trend</CardTitle>
          <CardDescription>Income and expense by transaction date</CardDescription>
        </CardHeader>
        <CardContent>
          {trend.length === 0 ? (
            <Empty message="No transactions for this filter." />
          ) : (
            <ChartContainer
              config={trendConfig}
              className="aspect-auto h-[280px]"
            >
              <LineChart data={trend} margin={{ left: 8, right: 8 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="date" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} width={48} />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      formatter={(value) => inr(Number(value))}
                    />
                  }
                />
                <ChartLegend content={<ChartLegendContent />} />
                <Line
                  type="monotone"
                  dataKey="expense"
                  stroke="var(--color-expense)"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="income"
                  stroke="var(--color-income)"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ChartContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
