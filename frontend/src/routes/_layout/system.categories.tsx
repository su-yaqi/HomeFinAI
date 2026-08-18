import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Pencil, Plus, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"
import { CategoriesService, type CategoryPublic as Category } from "@/client"
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
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const EMPTY_FORM = {
  name: "",
  color: "#3b82f6",
  parent_id: "",
}

export const Route = createFileRoute("/_layout/system/categories")({
  component: CategoriesPage,
  head: () => ({
    meta: [{ title: "Categories - HomeFin" }],
  }),
})

function CategoriesPage() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const { data, isLoading } = useQuery({
    queryKey: ["categories", page, pageSize],
    queryFn: () => CategoriesService.readCategories({ page, pageSize }),
  })
  const categoriesOptionsQuery = useQuery({
    queryKey: ["category-options"],
    queryFn: () => CategoriesService.readCategories({ page: 1, pageSize: 200 }),
  })

  const categories = data?.data ?? []
  const totalCount = data?.count ?? 0
  const categoryOptions = categoriesOptionsQuery.data?.data ?? []
  const categoryMap = useMemo(
    () => new Map(categoryOptions.map((category) => [category.id, category])),
    [categoryOptions],
  )

  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Category | null>(null)
  const [form, setForm] = useState(EMPTY_FORM)

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        name: form.name,
        color: form.color,
        parent_id: form.parent_id || null,
      }
      return editing
        ? CategoriesService.updateCategory({
            categoryId: editing.id,
            requestBody: payload,
          })
        : CategoriesService.createCategory({ requestBody: payload })
    },
    onSuccess: () => {
      showSuccessToast(editing ? "Category updated" : "Category created")
      setOpen(false)
      setEditing(null)
      setForm(EMPTY_FORM)
      queryClient.invalidateQueries({ queryKey: ["categories"] })
      queryClient.invalidateQueries({ queryKey: ["category-options"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      CategoriesService.deleteCategory({ categoryId: id }),
    onSuccess: () => {
      showSuccessToast("Category deleted")
      queryClient.invalidateQueries({ queryKey: ["categories"] })
      queryClient.invalidateQueries({ queryKey: ["category-options"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setOpen(true)
  }

  const openEdit = (category: Category) => {
    setEditing(category)
    setForm({
      name: category.name,
      color: category.color,
      parent_id: category.parent_id ?? "",
    })
    setOpen(true)
  }

  return (
    <div className="flex flex-col gap-6">
      <Dialog open={open} onOpenChange={setOpen}>
        <PageHeader
          title="Categories"
          description="Organize transactions with reusable category definitions."
          actions={
            <DialogTrigger asChild>
              <Button onClick={openCreate}>
                <Plus className="mr-2 h-4 w-4" />
                New Category
              </Button>
            </DialogTrigger>
          }
        />
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit category" : "Create category"}
            </DialogTitle>
            <DialogDescription>
              Categories are used by transactions and dashboard summaries.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <label className="text-sm font-medium" htmlFor="category-name">
                Name
              </label>
              <Input
                id="category-name"
                value={form.name}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    name: event.target.value,
                  }))
                }
              />
            </div>
            <div className="grid gap-2">
              <label className="text-sm font-medium" htmlFor="category-color">
                Color
              </label>
              <div className="grid grid-cols-[4rem_minmax(0,1fr)_2rem] items-center gap-3">
                <Input
                  id="category-color-picker"
                  type="color"
                  value={form.color}
                  className="h-11 w-16 cursor-pointer p-1"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      color: event.target.value,
                    }))
                  }
                />
                <Input
                  id="category-color"
                  value={form.color}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      color: event.target.value,
                    }))
                  }
                />
                <span
                  className="h-8 w-8 rounded-full border"
                  style={{ backgroundColor: form.color }}
                />
              </div>
            </div>
            <div className="grid gap-2">
              <div className="text-sm font-medium">Parent Category</div>
              <Select
                value={form.parent_id || "none"}
                onValueChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    parent_id: value === "none" ? "" : value,
                  }))
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="No parent" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">No parent</SelectItem>
                  {categoryOptions
                    .filter((category) => category.id !== editing?.id)
                    .map((category) => (
                      <SelectItem key={category.id} value={category.id}>
                        {category.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending || !form.name.trim()}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Card>
        <CardHeader>
          <CardTitle>Category List</CardTitle>
        </CardHeader>
        <CardContent className="px-4 sm:px-6">
          <div className="space-y-4">
            <div className="mobile-record-list">
              {categories.map((category) => (
                <Card key={category.id} className="gap-4 py-4 shadow-none">
                  <CardContent className="space-y-4 px-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="break-words font-semibold">
                          {category.name}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          Parent:{" "}
                          {category.parent_id
                            ? (categoryMap.get(category.parent_id)?.name ?? "-")
                            : "None"}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2 rounded-full border px-2 py-1 text-xs">
                        <span
                          className="h-3 w-3 rounded-full border"
                          style={{ backgroundColor: category.color }}
                        />
                        {category.color}
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Created{" "}
                      {category.created_at
                        ? new Date(category.created_at).toLocaleDateString()
                        : "-"}
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <Button
                        variant="outline"
                        className="min-h-11"
                        onClick={() => openEdit(category)}
                      >
                        <Pencil className="h-4 w-4" />
                        Edit
                      </Button>
                      <Button
                        variant="outline"
                        className="min-h-11"
                        onClick={() => deleteMutation.mutate(category.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {!isLoading && categories.length === 0 && (
                <div className="rounded-lg border px-4 py-10 text-center text-sm text-muted-foreground">
                  No categories yet.
                </div>
              )}
            </div>
            <div className="desktop-table-only">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Parent</TableHead>
                    <TableHead>Color</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="w-[140px] text-right">
                      Actions
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {categories.map((category) => (
                    <TableRow key={category.id}>
                      <TableCell className="font-medium">
                        {category.name}
                      </TableCell>
                      <TableCell>
                        {category.parent_id
                          ? (categoryMap.get(category.parent_id)?.name ?? "-")
                          : "-"}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span
                            className="h-3 w-3 rounded-full border"
                            style={{ backgroundColor: category.color }}
                          />
                          {category.color}
                        </div>
                      </TableCell>
                      <TableCell>
                        {category.created_at
                          ? new Date(category.created_at).toLocaleDateString()
                          : "-"}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            aria-label={`Edit ${category.name}`}
                            onClick={() => openEdit(category)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            aria-label={`Delete ${category.name}`}
                            onClick={() => deleteMutation.mutate(category.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!isLoading && categories.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} className="h-24 text-center">
                        No categories yet.
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
