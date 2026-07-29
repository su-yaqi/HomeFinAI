import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Pencil, Plus, Save, SlidersHorizontal, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"

import { PageHeader } from "@/components/Common/PageHeader"
import { TablePagination } from "@/components/Common/TablePagination"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
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
  type EntryStatus,
  homefinApi,
  type Transaction,
  type TransactionDetail,
  type TransactionDetailItem,
  type TransactionType,
} from "@/features/homefin/api"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

const EMPTY_FILTERS = {
  category_id: "all",
  transaction_type: "all",
  entry_status: "all",
  handler_user_id: "all",
  start_date: "",
  end_date: "",
}

const EMPTY_FORM = {
  category_id: "",
  transaction_type: "2",
  budget_id: "none",
  summary: "",
  detail_note: "",
  detail_items: [] as TransactionDetailItemForm[],
  entry_status: "1",
  handler_user_id: "",
  transaction_date: new Date().toISOString().slice(0, 10),
  amount: "",
}

type TransactionDetailItemForm = {
  id: string
  name: string
  remark: string
}

const createDetailItemForm = (
  item?: TransactionDetailItem,
): TransactionDetailItemForm => ({
  id:
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2)}`,
  name: item?.name ?? "",
  remark: typeof item?.remark === "string" ? item.remark : "",
})

const getDetailItems = (detail: TransactionDetail | null | undefined) =>
  Array.isArray(detail?.items) ? detail.items : []

const buildTransactionDetail = (
  form: typeof EMPTY_FORM,
): TransactionDetail | null => {
  const note = form.detail_note.trim()
  const items = form.detail_items
    .map((item) => ({
      name: item.name.trim(),
      remark: item.remark.trim(),
    }))
    .filter((item) => item.name)
    .map((item) => (item.remark ? item : { name: item.name }))

  if (!note && items.length === 0) {
    return null
  }

  return {
    ...(note ? { note } : {}),
    ...(items.length > 0 ? { items } : {}),
  }
}

const formatDetailItem = (item: TransactionDetailItem) =>
  item.remark ? `${item.name} - ${item.remark}` : item.name

const summarizeDetail = (detail: TransactionDetail | null | undefined) => {
  if (!detail) {
    return null
  }
  const note = typeof detail.note === "string" ? detail.note : ""
  const items = getDetailItems(detail)
  if (!note && items.length === 0) {
    return null
  }
  return {
    note,
    items,
  }
}

const transactionTypeLabel: Record<TransactionType, string> = {
  1: "Income",
  2: "Expense",
}

const transactionTypeClassName: Record<TransactionType, string> = {
  1: "border-emerald-200 bg-emerald-50 text-emerald-700",
  2: "border-rose-200 bg-rose-50 text-rose-700",
}

const entryStatusLabel: Record<EntryStatus, string> = {
  1: "Pending",
  2: "Skipped",
  3: "Entered",
}

const entryStatusClassName: Record<EntryStatus, string> = {
  1: "border-amber-200 bg-amber-50 text-amber-700",
  2: "border-slate-200 bg-slate-100 text-slate-700",
  3: "border-sky-200 bg-sky-50 text-sky-700",
}

export const Route = createFileRoute("/_layout/transactions")({
  component: TransactionsPage,
  head: () => ({
    meta: [{ title: "Transactions - HomeFin" }],
  }),
})

function TransactionsPage() {
  const queryClient = useQueryClient()
  const { user: currentUser } = useAuth()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Transaction | null>(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [filtersOpen, setFiltersOpen] = useState(false)

  const categoriesQuery = useQuery({
    queryKey: ["category-options"],
    queryFn: () => homefinApi.readCategories({ page: 1, page_size: 200 }),
  })
  const budgetsQuery = useQuery({
    queryKey: ["budget-options"],
    queryFn: () => homefinApi.readBudgets({ page: 1, page_size: 200 }),
  })
  const handlerUsersQuery = useQuery({
    queryKey: ["handler-users"],
    queryFn: () => homefinApi.readHandlerUsers({ page: 1, page_size: 200 }),
  })
  const transactionsQuery = useQuery({
    queryKey: ["transactions", filters, page, pageSize],
    queryFn: () =>
      homefinApi.readTransactions({
        page,
        page_size: pageSize,
        category_id:
          filters.category_id === "all" ? undefined : filters.category_id,
        transaction_type:
          filters.transaction_type === "all"
            ? undefined
            : (Number(filters.transaction_type) as TransactionType),
        entry_status:
          filters.entry_status === "all"
            ? undefined
            : (Number(filters.entry_status) as EntryStatus),
        handler_user_id:
          filters.handler_user_id === "all"
            ? undefined
            : filters.handler_user_id,
        start_date: filters.start_date || undefined,
        end_date: filters.end_date || undefined,
      }),
  })

  const categories = categoriesQuery.data?.data ?? []
  const budgets = budgetsQuery.data?.data ?? []
  const handlerUsers = handlerUsersQuery.data?.data ?? []
  const transactions = transactionsQuery.data?.data ?? []
  const totalCount = transactionsQuery.data?.count ?? 0

  const categoryMap = useMemo(
    () => new Map(categories.map((category) => [category.id, category.name])),
    [categories],
  )
  const budgetMap = useMemo(
    () => new Map(budgets.map((budget) => [budget.id, budget.name])),
    [budgets],
  )

  const allCurrentPageSelected =
    transactions.length > 0 &&
    transactions.every((transaction) => selectedIds.includes(transaction.id))

  const activeFilterCount = Object.entries(filters).filter(([key, value]) => {
    if (key === "start_date" || key === "end_date") return Boolean(value)
    return value !== "all"
  }).length

  const updateFilter = (key: keyof typeof EMPTY_FILTERS, value: string) => {
    setPage(1)
    setSelectedIds([])
    setFilters((current) => ({ ...current, [key]: value }))
  }

  const clearFilters = () => {
    setPage(1)
    setSelectedIds([])
    setFilters(EMPTY_FILTERS)
  }

  const changePage = (nextPage: number) => {
    setSelectedIds([])
    setPage(nextPage)
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        category_id: form.category_id,
        transaction_type: Number(form.transaction_type) as TransactionType,
        budget_id: form.budget_id === "none" ? null : form.budget_id,
        summary: form.summary.trim() || null,
        detail: buildTransactionDetail(form),
        entry_status: Number(form.entry_status) as EntryStatus,
        handler_user_id: form.handler_user_id || currentUser?.id || null,
        transaction_date: form.transaction_date,
        amount: Number(form.amount),
      }
      return editing
        ? homefinApi.updateTransaction(editing.id, payload)
        : homefinApi.createTransaction(payload)
    },
    onSuccess: () => {
      showSuccessToast(editing ? "Transaction updated" : "Transaction created")
      setOpen(false)
      setEditing(null)
      setForm(EMPTY_FORM)
      setSelectedIds([])
      queryClient.invalidateQueries({ queryKey: ["transactions"] })
      queryClient.invalidateQueries({ queryKey: ["budget-options"] })
      queryClient.invalidateQueries({ queryKey: ["budgets"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
    onError: handleError.bind(showErrorToast) as never,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => homefinApi.deleteTransaction(id),
    onSuccess: () => {
      showSuccessToast("Transaction deleted")
      setSelectedIds([])
      queryClient.invalidateQueries({ queryKey: ["transactions"] })
      queryClient.invalidateQueries({ queryKey: ["budget-options"] })
      queryClient.invalidateQueries({ queryKey: ["budgets"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
    onError: handleError.bind(showErrorToast) as never,
  })

  const batchEnterMutation = useMutation({
    mutationFn: () => homefinApi.batchEnterTransactions(selectedIds),
    onSuccess: () => {
      showSuccessToast("Selected transactions marked as entered")
      setSelectedIds([])
      queryClient.invalidateQueries({ queryKey: ["transactions"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
    onError: handleError.bind(showErrorToast) as never,
  })

  const openCreate = () => {
    setEditing(null)
    setForm({
      ...EMPTY_FORM,
      category_id: categories[0]?.id ?? "",
      handler_user_id: currentUser?.id ?? handlerUsers[0]?.id ?? "",
    })
    setOpen(true)
  }

  const openEdit = (transaction: Transaction) => {
    const detail = summarizeDetail(transaction.detail)
    setEditing(transaction)
    setForm({
      category_id: transaction.category_id,
      transaction_type: String(transaction.transaction_type),
      budget_id: transaction.budget_id ?? "none",
      summary: transaction.summary ?? transaction.description ?? "",
      detail_note: detail?.note ?? "",
      detail_items:
        detail?.items.map((item) => createDetailItemForm(item)) ?? [],
      entry_status: String(transaction.entry_status),
      handler_user_id: transaction.handler_user_id ?? currentUser?.id ?? "",
      transaction_date: transaction.transaction_date,
      amount: String(transaction.amount),
    })
    setOpen(true)
  }

  const toggleSelection = (id: string, checked: boolean) => {
    setSelectedIds((current) =>
      checked ? [...current, id] : current.filter((item) => item !== id),
    )
  }

  const toggleCurrentPageSelection = (checked: boolean) => {
    if (checked) {
      setSelectedIds(transactions.map((transaction) => transaction.id))
      return
    }
    setSelectedIds([])
  }

  const formatCurrency = (value: number) =>
    new Intl.NumberFormat("zh-CN", {
      style: "currency",
      currency: "CNY",
    }).format(value)

  const updateDetailItem = (
    id: string,
    field: keyof Omit<TransactionDetailItemForm, "id">,
    value: string,
  ) => {
    setForm((current) => ({
      ...current,
      detail_items: current.detail_items.map((item) =>
        item.id === id ? { ...item, [field]: value } : item,
      ),
    }))
  }

  const addDetailItem = () => {
    setForm((current) => ({
      ...current,
      detail_items: [...current.detail_items, createDetailItemForm()],
    }))
  }

  const removeDetailItem = (id: string) => {
    setForm((current) => ({
      ...current,
      detail_items: current.detail_items.filter((item) => item.id !== id),
    }))
  }

  return (
    <div className="flex flex-col gap-6">
      <Dialog open={open} onOpenChange={setOpen}>
        <PageHeader
          title="Transactions"
          description="Record income and expense flows with budget and category links."
          actions={
            <>
              <Button
                className="hidden sm:inline-flex"
                variant="outline"
                onClick={() => batchEnterMutation.mutate()}
                disabled={
                  selectedIds.length === 0 || batchEnterMutation.isPending
                }
              >
                <Save className="mr-2 h-4 w-4" />
                Mark Entered
              </Button>
              <DialogTrigger asChild>
                <Button onClick={openCreate}>
                  <Plus className="mr-2 h-4 w-4" />
                  New Transaction
                </Button>
              </DialogTrigger>
            </>
          }
        />
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit transaction" : "Create transaction"}
            </DialogTitle>
            <DialogDescription>
              Amounts are entered in yuan and stored with finance-specific
              metadata.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-4 md:grid-cols-2">
              <Select
                value={form.category_id}
                onValueChange={(value) =>
                  setForm((current) => ({ ...current, category_id: value }))
                }
              >
                <SelectTrigger className="w-full" aria-label="Category">
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  {categories.map((category) => (
                    <SelectItem key={category.id} value={category.id}>
                      {category.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={form.transaction_type}
                onValueChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    transaction_type: value,
                  }))
                }
              >
                <SelectTrigger className="w-full" aria-label="Transaction type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">Income</SelectItem>
                  <SelectItem value="2">Expense</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <Select
                value={form.budget_id}
                onValueChange={(value) =>
                  setForm((current) => ({ ...current, budget_id: value }))
                }
              >
                <SelectTrigger className="w-full" aria-label="Budget">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No budget</SelectItem>
                  {budgets.map((budget) => (
                    <SelectItem key={budget.id} value={budget.id}>
                      {budget.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={form.entry_status}
                onValueChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    entry_status: value,
                  }))
                }
              >
                <SelectTrigger className="w-full" aria-label="Entry status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">Pending</SelectItem>
                  <SelectItem value="2">Skipped</SelectItem>
                  <SelectItem value="3">Entered</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <Input
                type="number"
                inputMode="decimal"
                aria-label="Amount"
                min="0"
                step="0.01"
                placeholder="Amount"
                value={form.amount}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    amount: event.target.value,
                  }))
                }
              />
              <Input
                type="date"
                aria-label="Transaction date"
                value={form.transaction_date}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    transaction_date: event.target.value,
                  }))
                }
              />
              <Select
                value={form.handler_user_id}
                onValueChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    handler_user_id: value,
                  }))
                }
              >
                <SelectTrigger className="w-full" aria-label="Handler">
                  <SelectValue placeholder="Handler" />
                </SelectTrigger>
                <SelectContent>
                  {handlerUsers.map((user) => (
                    <SelectItem key={user.id} value={user.id}>
                      {user.display_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-3">
              <Input
                aria-label="Summary"
                placeholder="Summary (e.g. 打车 / 房租 / 麦当劳)"
                value={form.summary}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    summary: event.target.value,
                  }))
                }
              />
              <textarea
                aria-label="Detail note"
                className="min-h-[100px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
                placeholder="Detail note (optional)"
                value={form.detail_note}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    detail_note: event.target.value,
                  }))
                }
              />
              <div className="rounded-lg border border-dashed border-border/70 p-3">
                <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-medium">Detail Items</p>
                    <p className="text-xs text-muted-foreground">
                      Add readable line items instead of raw JSON.
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    className="min-h-11 w-full sm:min-h-8 sm:w-auto"
                    size="sm"
                    onClick={addDetailItem}
                  >
                    Add Item
                  </Button>
                </div>
                <div className="space-y-3">
                  {form.detail_items.length === 0 ? (
                    <div className="rounded-md bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
                      No detail items yet.
                    </div>
                  ) : (
                    form.detail_items.map((item) => (
                      <div
                        key={item.id}
                        className="grid gap-2 rounded-md border border-border/70 p-3 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_auto]"
                      >
                        <Input
                          aria-label="Detail item name"
                          placeholder="Item name"
                          value={item.name}
                          onChange={(event) =>
                            updateDetailItem(
                              item.id,
                              "name",
                              event.target.value,
                            )
                          }
                        />
                        <Input
                          aria-label="Detail item remark"
                          placeholder="Remark (optional)"
                          value={item.remark}
                          onChange={(event) =>
                            updateDetailItem(
                              item.id,
                              "remark",
                              event.target.value,
                            )
                          }
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          className="min-h-11 md:min-h-8"
                          size="sm"
                          onClick={() => removeDetailItem(item.id)}
                        >
                          Remove
                        </Button>
                      </div>
                    ))
                  )}
                </div>
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
                !form.category_id ||
                !form.summary.trim() ||
                !form.amount ||
                !form.handler_user_id
              }
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle>Filters</CardTitle>
          <Button
            variant="outline"
            className="min-h-11 md:hidden"
            onClick={() => setFiltersOpen((current) => !current)}
            aria-expanded={filtersOpen}
          >
            <SlidersHorizontal className="h-4 w-4" />
            {filtersOpen ? "Hide" : "Show"}
            {activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
          </Button>
        </CardHeader>
        <CardContent
          className={cn(
            "gap-4 lg:grid-cols-6",
            filtersOpen ? "grid" : "hidden md:grid",
          )}
        >
          <Select
            value={filters.category_id}
            onValueChange={(value) => updateFilter("category_id", value)}
          >
            <SelectTrigger
              className="min-h-11 w-full lg:min-h-9"
              aria-label="Filter by category"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {categories.map((category) => (
                <SelectItem key={category.id} value={category.id}>
                  {category.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={filters.transaction_type}
            onValueChange={(value) => updateFilter("transaction_type", value)}
          >
            <SelectTrigger
              className="min-h-11 w-full lg:min-h-9"
              aria-label="Filter by transaction type"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All types</SelectItem>
              <SelectItem value="1">Income</SelectItem>
              <SelectItem value="2">Expense</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={filters.entry_status}
            onValueChange={(value) => updateFilter("entry_status", value)}
          >
            <SelectTrigger
              className="min-h-11 w-full lg:min-h-9"
              aria-label="Filter by entry status"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="1">Pending</SelectItem>
              <SelectItem value="2">Skipped</SelectItem>
              <SelectItem value="3">Entered</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={filters.handler_user_id}
            onValueChange={(value) => updateFilter("handler_user_id", value)}
          >
            <SelectTrigger
              className="min-h-11 w-full lg:min-h-9"
              aria-label="Filter by handler"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All handlers</SelectItem>
              {handlerUsers.map((user) => (
                <SelectItem key={user.id} value={user.id}>
                  {user.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            type="date"
            aria-label="Filter start date"
            value={filters.start_date}
            onChange={(event) => updateFilter("start_date", event.target.value)}
          />
          <Input
            type="date"
            aria-label="Filter end date"
            value={filters.end_date}
            onChange={(event) => updateFilter("end_date", event.target.value)}
          />
          <Button
            variant="outline"
            onClick={clearFilters}
            className="min-h-11 lg:col-span-6 lg:min-h-9 lg:justify-self-start"
          >
            Clear Filters
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Transaction List</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 px-4 sm:px-6">
          <div className="mobile-record-list">
            {transactions.length > 0 ? (
              <label
                htmlFor="select-current-transaction-page"
                className="flex min-h-11 items-center gap-3 rounded-lg border px-4 py-2 text-sm font-medium"
              >
                <Checkbox
                  id="select-current-transaction-page"
                  className="size-5"
                  checked={allCurrentPageSelected}
                  onCheckedChange={(checked) =>
                    toggleCurrentPageSelection(checked === true)
                  }
                />
                Select all on this page
              </label>
            ) : null}
            {transactions.map((transaction) => {
              const detail = summarizeDetail(transaction.detail)
              const summary =
                transaction.summary ?? transaction.description ?? "-"
              return (
                <Card key={transaction.id} className="gap-4 py-4 shadow-none">
                  <CardContent className="space-y-4 px-4">
                    <div className="flex items-start gap-3">
                      <Checkbox
                        className="mt-1 size-5"
                        aria-label={`Select ${summary}`}
                        checked={selectedIds.includes(transaction.id)}
                        onCheckedChange={(checked) =>
                          toggleSelection(transaction.id, checked === true)
                        }
                      />
                      <div className="min-w-0 flex-1">
                        <p className="break-words font-semibold">{summary}</p>
                        <p className="text-sm text-muted-foreground">
                          {transaction.transaction_date} ·{" "}
                          {categoryMap.get(transaction.category_id) ?? "-"}
                        </p>
                      </div>
                      <p className="shrink-0 font-semibold">
                        {formatCurrency(transaction.amount)}
                      </p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <Badge
                        variant="outline"
                        className={
                          transactionTypeClassName[transaction.transaction_type]
                        }
                      >
                        {transactionTypeLabel[transaction.transaction_type]}
                      </Badge>
                      <Badge
                        variant="outline"
                        className={
                          entryStatusClassName[transaction.entry_status]
                        }
                      >
                        {entryStatusLabel[transaction.entry_status]}
                      </Badge>
                    </div>

                    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                      <div className="min-w-0">
                        <dt className="text-xs text-muted-foreground">
                          Handler
                        </dt>
                        <dd className="break-words">
                          {transaction.handler_display_name ?? "-"}
                        </dd>
                      </div>
                      <div className="min-w-0">
                        <dt className="text-xs text-muted-foreground">
                          Budget
                        </dt>
                        <dd className="break-words">
                          {transaction.budget_id
                            ? (budgetMap.get(transaction.budget_id) ?? "-")
                            : "None"}
                        </dd>
                      </div>
                    </dl>

                    {detail?.note || detail?.items.length ? (
                      <div className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
                        {detail.note ? (
                          <p className="line-clamp-2 break-words">
                            {detail.note}
                          </p>
                        ) : null}
                        {detail.items.length > 0 ? (
                          <p className="mt-1 line-clamp-2 break-words">
                            {detail.items
                              .slice(0, 2)
                              .map((item) => formatDetailItem(item))
                              .join(" / ")}
                            {detail.items.length > 2
                              ? ` +${detail.items.length - 2}`
                              : ""}
                          </p>
                        ) : null}
                      </div>
                    ) : null}

                    <div className="grid grid-cols-2 gap-2">
                      <Button
                        variant="outline"
                        className="min-h-11"
                        onClick={() => openEdit(transaction)}
                      >
                        <Pencil className="h-4 w-4" />
                        Edit
                      </Button>
                      <Button
                        variant="outline"
                        className="min-h-11"
                        onClick={() => deleteMutation.mutate(transaction.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
            {!transactionsQuery.isLoading && transactions.length === 0 && (
              <div className="rounded-lg border px-4 py-10 text-center text-sm text-muted-foreground">
                No transactions found.
              </div>
            )}
          </div>

          {selectedIds.length > 0 ? (
            <div className="sticky bottom-3 z-10 flex items-center justify-between gap-3 rounded-xl border bg-background/95 p-3 shadow-lg backdrop-blur md:hidden">
              <span className="text-sm font-medium">
                {selectedIds.length} selected
              </span>
              <Button
                className="min-h-11"
                onClick={() => batchEnterMutation.mutate()}
                disabled={batchEnterMutation.isPending}
              >
                <Save className="h-4 w-4" />
                Mark Entered
              </Button>
            </div>
          ) : null}

          <div className="desktop-table-only">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <Checkbox
                      checked={allCurrentPageSelected}
                      onCheckedChange={(checked) =>
                        toggleCurrentPageSelection(checked === true)
                      }
                      disabled={transactions.length === 0}
                    />
                  </TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Summary</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Budget</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Handler</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead className="w-[140px] text-right">
                    Actions
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transactions.map((transaction) => (
                  <TableRow key={transaction.id}>
                    <TableCell>
                      <Checkbox
                        checked={selectedIds.includes(transaction.id)}
                        onCheckedChange={(checked) =>
                          toggleSelection(transaction.id, checked === true)
                        }
                      />
                    </TableCell>
                    <TableCell>{transaction.transaction_date}</TableCell>
                    <TableCell>
                      {categoryMap.get(transaction.category_id) ?? "-"}
                    </TableCell>
                    <TableCell>
                      {(() => {
                        const detail = summarizeDetail(transaction.detail)
                        return (
                          <div className="max-w-[260px] space-y-1">
                            <span
                              className="block truncate font-medium text-foreground"
                              title={
                                transaction.summary ??
                                transaction.description ??
                                "-"
                              }
                            >
                              {transaction.summary ??
                                transaction.description ??
                                "-"}
                            </span>
                            {detail?.note ? (
                              <p
                                className="line-clamp-2 text-xs text-muted-foreground"
                                title={detail.note}
                              >
                                {detail.note}
                              </p>
                            ) : null}
                            {detail && detail.items.length > 0 ? (
                              <p
                                className="line-clamp-2 text-xs text-muted-foreground"
                                title={detail.items
                                  .map((item) => formatDetailItem(item))
                                  .join("\n")}
                              >
                                {detail.items
                                  .slice(0, 2)
                                  .map((item) => formatDetailItem(item))
                                  .join(" / ")}
                                {detail.items.length > 2
                                  ? ` +${detail.items.length - 2}`
                                  : ""}
                              </p>
                            ) : null}
                          </div>
                        )
                      })()}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={
                          transactionTypeClassName[transaction.transaction_type]
                        }
                      >
                        {transactionTypeLabel[transaction.transaction_type]}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {transaction.budget_id
                        ? (budgetMap.get(transaction.budget_id) ?? "-")
                        : "-"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={
                          entryStatusClassName[transaction.entry_status]
                        }
                      >
                        {entryStatusLabel[transaction.entry_status]}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {transaction.handler_display_name ?? "-"}
                    </TableCell>
                    <TableCell>{formatCurrency(transaction.amount)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          aria-label={`Edit ${transaction.summary ?? transaction.description ?? "transaction"}`}
                          onClick={() => openEdit(transaction)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          aria-label={`Delete ${transaction.summary ?? transaction.description ?? "transaction"}`}
                          onClick={() => deleteMutation.mutate(transaction.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {!transactionsQuery.isLoading && transactions.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={10} className="h-24 text-center">
                      No transactions found.
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
            onPageChange={changePage}
            onPageSizeChange={(nextPageSize) => {
              setPage(1)
              setSelectedIds([])
              setPageSize(nextPageSize)
            }}
          />
        </CardContent>
      </Card>
    </div>
  )
}
