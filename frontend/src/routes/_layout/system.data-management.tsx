import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Download, FileSpreadsheet, RefreshCcw, Upload } from "lucide-react"
import { useState } from "react"

import { type DataJobPublic, DataJobsService, UsersService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
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
    queryFn: () => DataJobsService.readDataJobs({ page, pageSize }),
    refetchInterval: (query) => {
      const jobs = query.state.data?.data ?? []
      return jobs.some(
        (job) => job.status === "PENDING" || job.status === "PROCESSING",
      )
        ? 2000
        : false
    },
  })

  const exportMutation = useMutation({
    mutationFn: () => DataJobsService.createExportJob(),
    onSuccess: () => {
      showSuccessToast("Export job started")
      queryClient.invalidateQueries({ queryKey: ["data-jobs"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const importMutation = useMutation({
    mutationFn: () => {
      if (!selectedFile) {
        throw new Error("Please choose an Excel file to import")
      }
      return DataJobsService.createImportJob({
        formData: { file: selectedFile },
      })
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
    loader: () => PromiseLike<Blob>,
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
      showErrorToast(error instanceof Error ? error.message : "Download failed")
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Data Management"
        description="Export categories, budgets, and transactions to a multi-sheet Excel workbook, or import them back with the standard template."
        actions={
          <Button
            variant="outline"
            onClick={() => jobsQuery.refetch()}
            disabled={jobsQuery.isFetching}
          >
            <RefreshCcw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        }
      />

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
              className="min-h-11 w-full sm:min-h-9 sm:w-auto"
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
                className="min-h-11 w-full sm:min-h-9 sm:w-auto"
                onClick={() =>
                  handleBlobDownload(
                    DataJobsService.downloadTemplate,
                    "homefin-import-template.xlsx",
                  )
                }
              >
                <Download className="mr-2 h-4 w-4" />
                Download Template
              </Button>
              <Input
                className="min-w-0"
                type="file"
                accept=".xlsx"
                onChange={(event) =>
                  setSelectedFile(event.target.files?.[0] ?? null)
                }
              />
            </div>
            <Button
              className="min-h-11 w-full sm:min-h-9 sm:w-auto"
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
        <CardContent className="px-4 sm:px-6">
          <div className="space-y-4">
            <div className="mobile-record-list">
              {jobs.map((job) => (
                <Card key={job.id} className="gap-4 py-4 shadow-none">
                  <CardContent className="space-y-4 px-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold">{job.job_type}</p>
                        <p className="text-xs text-muted-foreground">
                          {job.created_at
                            ? new Date(job.created_at).toLocaleString()
                            : "-"}
                        </p>
                      </div>
                      <Badge variant={badgeVariant(job.status)}>
                        {job.status}
                      </Badge>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>Progress</span>
                        <span>{job.progress_percent}%</span>
                      </div>
                      <div className="h-2 rounded-full bg-muted">
                        <div
                          className="h-2 rounded-full bg-primary transition-all"
                          style={{ width: `${job.progress_percent}%` }}
                        />
                      </div>
                    </div>
                    <dl className="grid grid-cols-3 gap-2 text-center text-sm">
                      <div className="rounded-md bg-muted/50 p-2">
                        <dt className="text-xs text-muted-foreground">Total</dt>
                        <dd className="font-medium">{job.total_rows}</dd>
                      </div>
                      <div className="rounded-md bg-muted/50 p-2">
                        <dt className="text-xs text-muted-foreground">OK</dt>
                        <dd className="font-medium">{job.success_rows}</dd>
                      </div>
                      <div className="rounded-md bg-muted/50 p-2">
                        <dt className="text-xs text-muted-foreground">
                          Failed
                        </dt>
                        <dd className="font-medium">{job.failed_rows}</dd>
                      </div>
                    </dl>
                    {(job.has_result_file || job.has_error_file) && (
                      <div className="grid grid-cols-2 gap-2">
                        {job.has_result_file && (
                          <Button
                            variant="outline"
                            className="min-h-11"
                            onClick={() =>
                              handleBlobDownload(
                                () =>
                                  DataJobsService.downloadResultFile({
                                    jobId: job.id,
                                  }),
                                `data-job-${job.id}-result.xlsx`,
                              )
                            }
                          >
                            <Download className="h-4 w-4" />
                            Result
                          </Button>
                        )}
                        {job.has_error_file && (
                          <Button
                            variant="outline"
                            className="min-h-11"
                            onClick={() =>
                              handleBlobDownload(
                                () =>
                                  DataJobsService.downloadErrorFile({
                                    jobId: job.id,
                                  }),
                                `data-job-${job.id}-errors.xlsx`,
                              )
                            }
                          >
                            <Download className="h-4 w-4" />
                            Errors
                          </Button>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
              {!jobsQuery.isLoading && jobs.length === 0 && (
                <div className="rounded-lg border px-4 py-10 text-center text-sm text-muted-foreground">
                  No data jobs yet.
                </div>
              )}
            </div>
            <div className="desktop-table-only">
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
                      <TableCell className="font-medium">
                        {job.job_type}
                      </TableCell>
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
                                () =>
                                  DataJobsService.downloadResultFile({
                                    jobId: job.id,
                                  }),
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
                                () =>
                                  DataJobsService.downloadErrorFile({
                                    jobId: job.id,
                                  }),
                                `data-job-${job.id}-errors.xlsx`,
                              )
                            }
                          >
                            Errors
                          </Button>
                        )}
                        {!job.has_result_file && !job.has_error_file && (
                          <span className="text-sm text-muted-foreground">
                            -
                          </span>
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

function badgeVariant(status: DataJobPublic["status"]) {
  if (status === "SUCCEEDED") {
    return "default" as const
  }
  if (status === "FAILED" || status === "CANCELLED") {
    return "destructive" as const
  }
  return "secondary" as const
}
