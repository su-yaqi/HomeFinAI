import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import {
  Download,
  FileSpreadsheet,
  RefreshCcw,
  Upload,
} from "lucide-react"
import { useState } from "react"

import { UsersService } from "@/client"
import { TablePagination } from "@/components/Common/TablePagination"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { type DataJobRecord, homefinApi } from "@/features/homefin/api"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/system/data-management")({
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({ to: "/" })
    }
  },
  component: DataManagementPage,
  head: () => ({
    meta: [{ title: "Data Management - HomeFin" }],
  }),
})

function DataManagementPage() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const jobsQuery = useQuery({
    queryKey: ["data-jobs", page, pageSize],
    queryFn: () => homefinApi.readDataJobs({ page, page_size: pageSize }),
    refetchInterval: (query) => {
      const jobs = (query.state.data?.data ?? []) as DataJobRecord[]
      return jobs.some(
        (job) => job.status === "PENDING" || job.status === "PROCESSING",
      )
        ? 2000
        : false
    },
  })

  const exportMutation = useMutation({
    mutationFn: () => homefinApi.createExportJob(),
    onSuccess: () => {
      showSuccessToast("Export job started")
      queryClient.invalidateQueries({ queryKey: ["data-jobs"] })
    },
    onError: handleError.bind(showErrorToast) as never,
  })

  const importMutation = useMutation({
    mutationFn: () => {
      if (!selectedFile) {
        throw new Error("Please choose an Excel file to import")
      }
      return homefinApi.createImportJob(selectedFile)
    },
    onSuccess: () => {
      showSuccessToast("Import job started")
      setSelectedFile(null)
      queryClient.invalidateQueries({ queryKey: ["data-jobs"] })
    },
    onError: (error) => {
      const message =
        error instanceof Error ? error.message : "Something went wrong."
      showErrorToast(message)
    },
  })

  const jobs = jobsQuery.data?.data ?? []
  const totalCount = jobsQuery.data?.count ?? 0
  const activeJobs = jobs.filter(
    (job) => job.status === "PENDING" || job.status === "PROCESSING",
  )

  const handleBlobDownload = async (
    loader: () => Promise<Blob>,
    filename: string,
  ) => {
    try {
      const blob = await loader()
      const url = window.URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = filename
      anchor.click()
      window.URL.revokeObjectURL(url)
    } catch (error) {
      showErrorToast(
        error instanceof Error ? error.message : "Download failed",
      )
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Data Management</h1>
          <p className="text-muted-foreground">
            Export categories, budgets, and transactions to a multi-sheet Excel
            workbook, or import them back with the standard template.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => jobsQuery.refetch()}
          disabled={jobsQuery.isFetching}
        >
          <RefreshCcw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {activeJobs.length > 0 && (
        <Alert>
          <FileSpreadsheet className="h-4 w-4" />
          <AlertTitle>Jobs are running</AlertTitle>
          <AlertDescription>
            {activeJobs.length} data job(s) are still processing. This page
            refreshes automatically while work is in progress.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Backup Export</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Generate a workbook with `README`, `Categories`, `Budgets`, and
              `Transactions` sheets for all system users.
            </p>
            <Button
              onClick={() => exportMutation.mutate()}
              disabled={exportMutation.isPending}
            >
              <Download className="mr-2 h-4 w-4" />
              Start Export
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Import</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Download the template first, then upload a filled `.xlsx` file to
              create a background import job.
            </p>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button
                variant="outline"
                onClick={() =>
                  handleBlobDownload(
                    homefinApi.downloadDataJobTemplate,
                    "homefin-import-template.xlsx",
                  )
                }
              >
                <Download className="mr-2 h-4 w-4" />
                Download Template
              </Button>
              <Input
                type="file"
                accept=".xlsx"
                onChange={(event) =>
                  setSelectedFile(event.target.files?.[0] ?? null)
                }
              />
            </div>
            <Button
              onClick={() => importMutation.mutate()}
              disabled={importMutation.isPending || !selectedFile}
            >
              <Upload className="mr-2 h-4 w-4" />
              Upload and Import
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Progress</TableHead>
                  <TableHead>Rows</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-[280px] text-right">
                    Files
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="font-medium">{job.job_type}</TableCell>
                    <TableCell>
                      <Badge variant={badgeVariant(job.status)}>
                        {job.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex min-w-[160px] items-center gap-3">
                        <div className="h-2 flex-1 rounded-full bg-muted">
                          <div
                            className="h-2 rounded-full bg-primary transition-all"
                            style={{ width: `${job.progress_percent}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {job.progress_percent}%
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      <div>Total {job.total_rows}</div>
                      <div>OK {job.success_rows}</div>
                      <div>Fail {job.failed_rows}</div>
                    </TableCell>
                    <TableCell>
                      {job.created_at
                        ? new Date(job.created_at).toLocaleString()
                        : "-"}
                    </TableCell>
                    <TableCell className="space-x-2 text-right">
                      {job.has_result_file && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            handleBlobDownload(
                              () => homefinApi.downloadDataJobResult(job.id),
                              `data-job-${job.id}-result.xlsx`,
                            )
                          }
                        >
                          Result
                        </Button>
                      )}
                      {job.has_error_file && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            handleBlobDownload(
                              () => homefinApi.downloadDataJobErrors(job.id),
                              `data-job-${job.id}-errors.xlsx`,
                            )
                          }
                        >
                          Errors
                        </Button>
                      )}
                      {!job.has_result_file && !job.has_error_file && (
                        <span className="text-sm text-muted-foreground">-</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
                {!jobsQuery.isLoading && jobs.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="h-24 text-center">
                      No data jobs yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>

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

function badgeVariant(status: DataJobRecord["status"]) {
  if (status === "SUCCEEDED") {
    return "default" as const
  }
  if (status === "FAILED" || status === "CANCELLED") {
    return "destructive" as const
  }
  return "secondary" as const
}
