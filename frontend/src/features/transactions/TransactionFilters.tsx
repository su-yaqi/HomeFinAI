import { SlidersHorizontal } from "lucide-react"
import { useState } from "react"

import type { CategoryPublic, HandlerUserOption } from "@/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { TransactionFiltersState } from "@/features/transactions/model"
import { cn } from "@/lib/utils"

type Props = {
  filters: TransactionFiltersState
  categories: CategoryPublic[]
  handlerUsers: HandlerUserOption[]
  onUpdate: (key: keyof TransactionFiltersState, value: string) => void
  onClear: () => void
}

export function TransactionFilters({
  filters,
  categories,
  handlerUsers,
  onUpdate,
  onClear,
}: Props) {
  const [open, setOpen] = useState(false)
  const activeCount = Object.entries(filters).filter(([key, value]) => {
    if (key === "start_date" || key === "end_date") return Boolean(value)
    return value !== "all"
  }).length

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle>Filters</CardTitle>
        <Button
          variant="outline"
          className="min-h-11 md:hidden"
          onClick={() => setOpen((current) => !current)}
          aria-expanded={open}
        >
          <SlidersHorizontal className="h-4 w-4" />
          {open ? "Hide" : "Show"}
          {activeCount > 0 ? ` (${activeCount})` : ""}
        </Button>
      </CardHeader>
      <CardContent
        className={cn("gap-4 lg:grid-cols-6", open ? "grid" : "hidden md:grid")}
      >
        <Select
          value={filters.category_id}
          onValueChange={(value) => onUpdate("category_id", value)}
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
          onValueChange={(value) => onUpdate("transaction_type", value)}
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
          onValueChange={(value) => onUpdate("entry_status", value)}
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
          onValueChange={(value) => onUpdate("handler_user_id", value)}
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
          onChange={(event) => onUpdate("start_date", event.target.value)}
        />
        <Input
          type="date"
          aria-label="Filter end date"
          value={filters.end_date}
          onChange={(event) => onUpdate("end_date", event.target.value)}
        />
        <Button
          variant="outline"
          onClick={onClear}
          className="min-h-11 lg:col-span-6 lg:min-h-9 lg:justify-self-start"
        >
          Clear Filters
        </Button>
      </CardContent>
    </Card>
  )
}
