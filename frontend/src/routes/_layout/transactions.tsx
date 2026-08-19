import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Pencil, Plus, Save, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"

import {
  BudgetsService,
  CategoriesService,
  type EntryStatus,
  type TransactionPublic as Transaction,
  TransactionsService,
  type TransactionType,
  UsersService,
} from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { TablePagination } from "@/components/Common/TablePagination"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogTrigger } from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  buildTransactionDetail,
  createDetailItemForm,
  EMPTY_FILTERS,
  EMPTY_FORM,
  entryStatusClassName,
  entryStatusLabel,
  formatDetailItem,
  summarizeDetail,
  transactionTypeClassName,
  transactionTypeLabel,
} from "@/features/transactions/model"
import { TransactionFilters } from "@/features/transactions/TransactionFilters"
import { TransactionFormDialog } from "@/features/transactions/TransactionFormDialog"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

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

  const categoriesQuery = useQuery({
    queryKey: ["category-options"],
    queryFn: () => CategoriesService.readCategories({ page: 1, pageSize: 200 }),
  })
  const budgetsQuery = useQuery({
    queryKey: ["budget-options"],
    queryFn: () => BudgetsService.readBudgets({ page: 1, pageSize: 200 }),
  })
  const handlerUsersQuery = useQuery({
    queryKey: ["handler-users"],
    queryFn: () => UsersService.readHandlerOptions({ page: 1, pageSize: 200 }),
  })
  const transactionsQuery = useQuery({
    queryKey: ["transactions", filters, page, pageSize],
    queryFn: () =>
      TransactionsService.readTransactions({
        page,
        pageSize,
        categoryId:
          filters.category_id === "all" ? undefined : filters.category_id,
        transactionType:
          filters.transaction_type === "all"
            ? undefined
            : (Number(filters.transaction_type) as TransactionType),
        entryStatus:
          filters.entry_status === "all"
            ? undefined
            : (Number(filters.entry_status) as EntryStatus),
        handlerUserId:
          filters.handler_user_id === "all"
            ? undefined
            : filters.handler_user_id,
        startDate: filters.start_date || undefined,
        endDate: filters.end_date || undefined,
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
        ? TransactionsService.updateTransaction({
            transactionId: editing.id,
            requestBody: payload,
          })
        : TransactionsService.createTransaction({ requestBody: payload })
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
    onError: handleError.bind(showErrorToast),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      TransactionsService.deleteTransaction({ transactionId: id }),
    onSuccess: () => {
      showSuccessToast("Transaction deleted")
      setSelectedIds([])
      queryClient.invalidateQueries({ queryKey: ["transactions"] })
      queryClient.invalidateQueries({ queryKey: ["budget-options"] })
      queryClient.invalidateQueries({ queryKey: ["budgets"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const batchEnterMutation = useMutation({
    mutationFn: () =>
      TransactionsService.batchEnterTransactions({
        requestBody: { ids: selectedIds },
      }),
    onSuccess: () => {
      showSuccessToast("Selected transactions marked as entered")
      setSelectedIds([])
      queryClient.invalidateQueries({ queryKey: ["transactions"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
    },
    onError: handleError.bind(showErrorToast),
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
        <TransactionFormDialog
          isEditing={editing !== null}
          form={form}
          setForm={setForm}
          categories={categories}
          budgets={budgets}
          handlerUsers={handlerUsers}
          isSaving={saveMutation.isPending}
          onClose={() => setOpen(false)}
          onSave={() => saveMutation.mutate()}
        />
      </Dialog>

      <TransactionFilters
        filters={filters}
        categories={categories}
        handlerUsers={handlerUsers}
        onUpdate={updateFilter}
        onClear={clearFilters}
      />

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
