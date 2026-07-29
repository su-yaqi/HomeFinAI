import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Pencil, Plus, Trash2 } from "lucide-react"
import { useState } from "react"

import { PageHeader } from "@/components/Common/PageHeader"
import { TablePagination } from "@/components/Common/TablePagination"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  type Budget,
  type BudgetPeriod,
  homefinApi,
} from "@/features/homefin/api"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const periodLabel: Record<BudgetPeriod, string> = {
  1: "Monthly",
  2: "Quarterly",
  3: "Yearly",
}

const EMPTY_FORM = {
  name: "",
  year: String(new Date().getFullYear()),
  period: "1",
  amount: "",
}

export const Route = createFileRoute("/_layout/budgets")({
  component: BudgetsPage,
  head: () => ({
    meta: [{ title: "Budgets - HomeFin" }],
  }),
})

function BudgetsPage() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const { data, isLoading } = useQuery({
    queryKey: ["budgets", page, pageSize],
    queryFn: () => homefinApi.readBudgets({ page, page_size: pageSize }),
  })

  const budgets = data?.data ?? []
  const totalCount = data?.count ?? 0
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Budget | null>(null)
  const [form, setForm] = useState(EMPTY_FORM)

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        name: form.name,
        year: Number(form.year),
        period: Number(form.period) as BudgetPeriod,
        amount: Number(form.amount),
      }
      return editing
        ? homefinApi.updateBudget(editing.id, payload)
        : homefinApi.createBudget(payload)
    },
    onSuccess: () => {
      showSuccessToast(editing ? "Budget updated" : "Budget created")
      setOpen(false)
      setEditing(null)
      setForm(EMPTY_FORM)
      queryClient.invalidateQueries({ queryKey: ["budgets"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
    onError: handleError.bind(showErrorToast) as never,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => homefinApi.deleteBudget(id),
    onSuccess: () => {
      showSuccessToast("Budget deleted")
      queryClient.invalidateQueries({ queryKey: ["budgets"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
    onError: handleError.bind(showErrorToast) as never,
  })

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setOpen(true)
  }

  const openEdit = (budget: Budget) => {
    setEditing(budget)
    setForm({
      name: budget.name,
      year: String(budget.year),
      period: String(budget.period),
      amount: String(budget.amount),
    })
    setOpen(true)
  }

  const formatCurrency = (value: number) =>
    new Intl.NumberFormat("zh-CN", {
      style: "currency",
      currency: "CNY",
    }).format(value)

  return (
    <div className="flex flex-col gap-6">
      <Dialog open={open} onOpenChange={setOpen}>
        <PageHeader
          title="Budgets"
          description="Set annual, quarterly, or monthly spending targets."
          actions={
            <DialogTrigger asChild>
              <Button onClick={openCreate}>
                <Plus className="mr-2 h-4 w-4" />
                New Budget
              </Button>
            </DialogTrigger>
          }
        />
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit budget" : "Create budget"}
            </DialogTitle>
            <DialogDescription>
              Budget amounts are entered in yuan and tracked against expense
              transactions.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <label className="text-sm font-medium" htmlFor="budget-name">
                Name
              </label>
              <Input
                id="budget-name"
                placeholder="Budget name"
                value={form.name}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    name: event.target.value,
                  }))
                }
              />
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="grid gap-2">
                <label className="text-sm font-medium" htmlFor="budget-year">
                  Year
                </label>
                <Input
                  id="budget-year"
                  placeholder="Year"
                  type="number"
                  value={form.year}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      year: event.target.value,
                    }))
                  }
                />
              </div>
              <div className="grid gap-2">
                <span className="text-sm font-medium">Period</span>
                <Select
                  value={form.period}
                  onValueChange={(value) =>
                    setForm((current) => ({ ...current, period: value }))
                  }
                >
                  <SelectTrigger className="w-full" aria-label="Period">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">Monthly</SelectItem>
                    <SelectItem value="2">Quarterly</SelectItem>
                    <SelectItem value="3">Yearly</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <label className="text-sm font-medium" htmlFor="budget-amount">
                  Amount
                </label>
                <Input
                  id="budget-amount"
                  placeholder="Amount"
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="0.01"
                  value={form.amount}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      amount: event.target.value,
                    }))
                  }
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => saveMutation.mutate()}
              disabled={
                saveMutation.isPending ||
                !form.name.trim() ||
                !form.year ||
                !form.amount
              }
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Card>
        <CardHeader>
          <CardTitle>Budget List</CardTitle>
        </CardHeader>
        <CardContent className="px-4 sm:px-6">
          <div className="space-y-4">
            <div className="mobile-record-list">
              {budgets.map((budget) => (
                <Card key={budget.id} className="gap-4 py-4 shadow-none">
                  <CardContent className="space-y-4 px-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="break-words font-semibold">
                          {budget.name}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {budget.year} · {periodLabel[budget.period]}
                        </p>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="font-semibold">
                          {formatCurrency(budget.amount)}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Used {formatCurrency(budget.used_amount)}
                        </p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <Button
                        variant="outline"
                        className="min-h-11"
                        onClick={() => openEdit(budget)}
                      >
                        <Pencil className="h-4 w-4" />
                        Edit
                      </Button>
                      <Button
                        variant="outline"
                        className="min-h-11"
                        onClick={() => deleteMutation.mutate(budget.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {!isLoading && budgets.length === 0 && (
                <div className="rounded-lg border px-4 py-10 text-center text-sm text-muted-foreground">
                  No budgets yet.
                </div>
              )}
            </div>
            <div className="desktop-table-only">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Year</TableHead>
                    <TableHead>Period</TableHead>
                    <TableHead>Budget</TableHead>
                    <TableHead>Used</TableHead>
                    <TableHead className="w-[140px] text-right">
                      Actions
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {budgets.map((budget) => (
                    <TableRow key={budget.id}>
                      <TableCell className="font-medium">
                        {budget.name}
                      </TableCell>
                      <TableCell>{budget.year}</TableCell>
                      <TableCell>{periodLabel[budget.period]}</TableCell>
                      <TableCell>{formatCurrency(budget.amount)}</TableCell>
                      <TableCell>
                        {formatCurrency(budget.used_amount)}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            aria-label={`Edit ${budget.name}`}
                            onClick={() => openEdit(budget)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            aria-label={`Delete ${budget.name}`}
                            onClick={() => deleteMutation.mutate(budget.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!isLoading && budgets.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        No budgets yet.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
            <TablePagination
              page={page}
              pageSize={pageSize}
              totalCount={totalCount}
              onPageChange={setPage}
              onPageSizeChange={(nextPageSize) => {
                setPage(1)
                setPageSize(nextPageSize)
              }}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
