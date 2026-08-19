import type {
  EntryStatus,
  TransactionCreate,
  TransactionPublic,
  TransactionType,
} from "@/client"

export const EMPTY_FILTERS = {
  category_id: "all",
  transaction_type: "all",
  entry_status: "all",
  handler_user_id: "all",
  start_date: "",
  end_date: "",
}

export type TransactionFiltersState = typeof EMPTY_FILTERS

export type TransactionDetailItemForm = {
  id: string
  name: string
  remark: string
}

type TransactionDetailItem = {
  name: string
  remark?: string
  [key: string]: unknown
}

export const EMPTY_FORM = {
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

export const createDetailItemForm = (
  item?: TransactionDetailItem,
): TransactionDetailItemForm => ({
  id:
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2)}`,
  name: item?.name ?? "",
  remark: typeof item?.remark === "string" ? item.remark : "",
})

const getDetailItems = (
  detail: TransactionPublic["detail"],
): TransactionDetailItem[] => {
  if (!detail || !Array.isArray(detail.items)) return []
  return detail.items.filter(
    (item): item is TransactionDetailItem =>
      typeof item === "object" &&
      item !== null &&
      typeof (item as { name?: unknown }).name === "string",
  )
}

export const buildTransactionDetail = (
  form: typeof EMPTY_FORM,
): TransactionCreate["detail"] => {
  const note = form.detail_note.trim()
  const items = form.detail_items
    .map((item) => ({
      name: item.name.trim(),
      remark: item.remark.trim(),
    }))
    .filter((item) => item.name)
    .map((item) => (item.remark ? item : { name: item.name }))

  if (!note && items.length === 0) return null
  return {
    ...(note ? { note } : {}),
    ...(items.length > 0 ? { items } : {}),
  }
}

export const formatDetailItem = (item: TransactionDetailItem) =>
  item.remark ? `${item.name} - ${item.remark}` : item.name

export const summarizeDetail = (detail: TransactionPublic["detail"]) => {
  if (!detail) return null
  const note = typeof detail.note === "string" ? detail.note : ""
  const items = getDetailItems(detail)
  if (!note && items.length === 0) return null
  return { note, items }
}

export const transactionTypeLabel: Record<TransactionType, string> = {
  1: "Income",
  2: "Expense",
}

export const transactionTypeClassName: Record<TransactionType, string> = {
  1: "border-emerald-200 bg-emerald-50 text-emerald-700",
  2: "border-rose-200 bg-rose-50 text-rose-700",
}

export const entryStatusLabel: Record<EntryStatus, string> = {
  1: "Pending",
  2: "Skipped",
  3: "Entered",
}

export const entryStatusClassName: Record<EntryStatus, string> = {
  1: "border-amber-200 bg-amber-50 text-amber-700",
  2: "border-slate-200 bg-slate-100 text-slate-700",
  3: "border-sky-200 bg-sky-50 text-sky-700",
}
