import type { Dispatch, SetStateAction } from "react"

import type { BudgetPublic, CategoryPublic, HandlerUserOption } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
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
  createDetailItemForm,
  type EMPTY_FORM,
  type TransactionDetailItemForm,
} from "@/features/transactions/model"

type TransactionForm = typeof EMPTY_FORM

type TransactionFormDialogProps = {
  isEditing: boolean
  form: TransactionForm
  setForm: Dispatch<SetStateAction<TransactionForm>>
  categories: CategoryPublic[]
  budgets: BudgetPublic[]
  handlerUsers: HandlerUserOption[]
  isSaving: boolean
  onClose: () => void
  onSave: () => void
}

export function TransactionFormDialog({
  isEditing,
  form,
  setForm,
  categories,
  budgets,
  handlerUsers,
  isSaving,
  onClose,
  onSave,
}: TransactionFormDialogProps) {
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
    <DialogContent className="max-w-2xl">
      <DialogHeader>
        <DialogTitle>
          {isEditing ? "Edit transaction" : "Create transaction"}
        </DialogTitle>
        <DialogDescription>
          Amounts are entered in yuan and stored with finance-specific metadata.
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
              setForm((current) => ({ ...current, entry_status: value }))
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
                        updateDetailItem(item.id, "name", event.target.value)
                      }
                    />
                    <Input
                      aria-label="Detail item remark"
                      placeholder="Remark (optional)"
                      value={item.remark}
                      onChange={(event) =>
                        updateDetailItem(item.id, "remark", event.target.value)
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
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button
          onClick={onSave}
          disabled={
            isSaving ||
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
  )
}
