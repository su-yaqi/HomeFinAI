import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ArrowDownRight, ArrowUpRight, PiggyBank, Wallet } from "lucide-react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { homefinApi } from "@/features/homefin/api"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "Dashboard - HomeFin",
      },
    ],
  }),
})

function Dashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: homefinApi.readDashboard,
  })

  const summaryCards = [
    {
      title: "Income",
      value: data?.summary.income ?? 0,
      icon: ArrowUpRight,
    },
    {
      title: "Expense",
      value: data?.summary.expense ?? 0,
      icon: ArrowDownRight,
    },
    {
      title: "Balance",
      value: data?.summary.balance ?? 0,
      icon: Wallet,
    },
    {
      title: "Budgets",
      value: data?.budget_usage.length ?? 0,
      icon: PiggyBank,
      raw: true,
    },
  ]

  const formatCurrency = (value: number) =>
    new Intl.NumberFormat("zh-CN", {
      style: "currency",
      currency: "CNY",
    }).format(value)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Financial Dashboard
        </h1>
        <p className="text-muted-foreground">
          Track this month&apos;s cash flow, category mix, and budget usage.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {summaryCards.map((card) => (
          <Card key={card.title}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {card.title}
              </CardTitle>
              <card.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold">
                {isLoading
                  ? "..."
                  : card.raw
                    ? card.value
                    : formatCurrency(card.value)}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Six-Month Trend</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(data?.trends ?? []).map((point) => (
              <div
                key={point.month}
                className="flex items-center justify-between rounded-lg border p-3"
              >
                <div className="font-medium">{point.month}</div>
                <div className="text-sm text-muted-foreground">
                  Income {formatCurrency(point.income)}
                </div>
                <div className="text-sm text-muted-foreground">
                  Expense {formatCurrency(point.expense)}
                </div>
              </div>
            ))}
            {!isLoading && (data?.trends.length ?? 0) === 0 && (
              <div className="text-sm text-muted-foreground">
                No trend data yet.
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Category Spend Share</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(data?.category_shares ?? []).map((item) => (
              <div
                key={item.category_id}
                className="flex items-center justify-between rounded-lg border p-3"
              >
                <div className="font-medium">{item.category_name}</div>
                <div className="text-sm text-muted-foreground">
                  {formatCurrency(item.amount)}
                </div>
              </div>
            ))}
            {!isLoading && (data?.category_shares.length ?? 0) === 0 && (
              <div className="text-sm text-muted-foreground">
                No expense categories this month.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Budget Usage</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {(data?.budget_usage ?? []).map((item) => {
            const ratio =
              item.amount > 0
                ? Math.min(
                    100,
                    Math.round((item.used_amount / item.amount) * 100),
                  )
                : 0
            return (
              <div
                key={item.budget_id}
                className="space-y-2 rounded-lg border p-3"
              >
                <div className="flex items-center justify-between">
                  <div className="font-medium">{item.budget_name}</div>
                  <div className="text-sm text-muted-foreground">
                    {formatCurrency(item.used_amount)} /{" "}
                    {formatCurrency(item.amount)}
                  </div>
                </div>
                <div className="h-2 rounded-full bg-muted">
                  <div
                    className="h-2 rounded-full bg-primary"
                    style={{ width: `${ratio}%` }}
                  />
                </div>
              </div>
            )
          })}
          {!isLoading && (data?.budget_usage.length ?? 0) === 0 && (
            <div className="text-sm text-muted-foreground">
              No budgets configured for this year.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
