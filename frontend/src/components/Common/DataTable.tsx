import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
} from "@tanstack/react-table"
import type { ReactNode } from "react"

import { TablePagination } from "@/components/Common/TablePagination"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  totalCount?: number
  page?: number
  pageSize?: number
  onPageChange?: (page: number) => void
  onPageSizeChange?: (pageSize: number) => void
  renderMobileCard?: (row: TData) => ReactNode
  mobileEmptyMessage?: string
}

export function DataTable<TData, TValue>({
  columns,
  data,
  totalCount,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  renderMobileCard,
  mobileEmptyMessage = "No results found.",
}: DataTableProps<TData, TValue>) {
  const manualPagination =
    totalCount !== undefined &&
    page !== undefined &&
    pageSize !== undefined &&
    onPageChange !== undefined &&
    onPageSizeChange !== undefined

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    ...(manualPagination
      ? {}
      : { getPaginationRowModel: getPaginationRowModel() }),
  })

  return (
    <div className="flex flex-col gap-4">
      {renderMobileCard ? (
        <div className="mobile-record-list">
          {data.length > 0 ? (
            data.map((row, index) => (
              <div key={String((row as { id?: unknown }).id ?? index)}>
                {renderMobileCard(row)}
              </div>
            ))
          ) : (
            <div className="rounded-lg border px-4 py-10 text-center text-sm text-muted-foreground">
              {mobileEmptyMessage}
            </div>
          )}
        </div>
      ) : null}
      <div className={renderMobileCard ? "desktop-table-only" : undefined}>
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="hover:bg-transparent">
                {headerGroup.headers.map((header) => {
                  return (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext(),
                          )}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow className="hover:bg-transparent">
                <TableCell
                  colSpan={columns.length}
                  className="h-32 text-center text-muted-foreground"
                >
                  No results found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {manualPagination ? (
        <TablePagination
          page={page}
          pageSize={pageSize}
          totalCount={totalCount}
          onPageChange={onPageChange}
          onPageSizeChange={onPageSizeChange}
        />
      ) : table.getPageCount() > 1 ? (
        <TablePagination
          page={table.getState().pagination.pageIndex + 1}
          pageSize={table.getState().pagination.pageSize}
          totalCount={data.length}
          onPageChange={(nextPage) => table.setPageIndex(nextPage - 1)}
          onPageSizeChange={(nextPageSize) => table.setPageSize(nextPageSize)}
        />
      ) : null}
    </div>
  )
}
