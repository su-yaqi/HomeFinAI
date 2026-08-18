import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Ban, Copy, KeyRound, Plus, Trash2 } from "lucide-react"
import { useState } from "react"

import {
  type ApiTokenSecretPublic,
  ApiTokensService,
  UsersService,
} from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { TablePagination } from "@/components/Common/TablePagination"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/system/api-tokens")({
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({ to: "/" })
    }
  },
  component: ApiTokensPage,
  head: () => ({
    meta: [{ title: "API Tokens - HomeFin" }],
  }),
})

function ApiTokensPage() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [, copyToClipboard] = useCopyToClipboard()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [expiresAt, setExpiresAt] = useState("")
  const [generateSecret, setGenerateSecret] = useState(false)
  const [latestSecret, setLatestSecret] = useState<ApiTokenSecretPublic | null>(
    null,
  )

  const tokensQuery = useQuery({
    queryKey: ["api-tokens", page, pageSize],
    queryFn: () => ApiTokensService.readApiTokens({ page, pageSize }),
  })

  const createMutation = useMutation({
    mutationFn: () =>
      ApiTokensService.createApiToken({
        requestBody: {
          name,
          expires_at: expiresAt ? `${expiresAt}T00:00:00Z` : null,
          generate_secret: generateSecret,
        },
      }),
    onSuccess: (secret) => {
      showSuccessToast("API token created")
      setLatestSecret(secret)
      setOpen(false)
      setName("")
      setExpiresAt("")
      setGenerateSecret(false)
      queryClient.invalidateQueries({ queryKey: ["api-tokens"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const disableMutation = useMutation({
    mutationFn: (id: string) =>
      ApiTokensService.disableApiToken({ tokenId: id }),
    onSuccess: () => {
      showSuccessToast("API token disabled")
      queryClient.invalidateQueries({ queryKey: ["api-tokens"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      ApiTokensService.deleteApiToken({ tokenId: id }),
    onSuccess: () => {
      showSuccessToast("API token deleted")
      queryClient.invalidateQueries({ queryKey: ["api-tokens"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const tokens = tokensQuery.data?.data ?? []
  const totalCount = tokensQuery.data?.count ?? 0

  const copyValue = async (label: string, value: string) => {
    const copied = await copyToClipboard(value)
    if (copied) {
      showSuccessToast(`${label} copied`)
      return
    }
    showErrorToast(`Could not copy ${label.toLowerCase()}`)
  }

  return (
    <div className="flex flex-col gap-6">
      <Dialog open={open} onOpenChange={setOpen}>
        <PageHeader
          title="API Tokens"
          description="Issue and disable agent tokens for external transaction ingestion."
          actions={
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                New Token
              </Button>
            </DialogTrigger>
          }
        />
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create API token</DialogTitle>
            <DialogDescription>
              The plain token is shown only once. Copy it after creation.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <Input
              placeholder="Token name"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <Input
              type="date"
              value={expiresAt}
              onChange={(event) => setExpiresAt(event.target.value)}
            />
            <div className="flex items-center gap-3 text-sm">
              <Checkbox
                checked={generateSecret}
                onCheckedChange={(checked) =>
                  setGenerateSecret(checked === true)
                }
              />
              <span>Generate HMAC secret</span>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending || !name.trim()}
            >
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Alert>
        <KeyRound className="h-4 w-4" />
        <AlertTitle>Use these tokens only with agent endpoints</AlertTitle>
        <AlertDescription>
          <p>
            API tokens authenticate external callers against
            <code className="mx-1 break-all rounded bg-muted px-1 py-0.5 text-xs">
              /api/v1/agent/*
            </code>
            routes.
          </p>
          <p className="mt-2">
            Requests to standard user endpoints such as
            <code className="mx-1 break-all rounded bg-muted px-1 py-0.5 text-xs">
              /api/v1/categories
            </code>
            ,
            <code className="mx-1 break-all rounded bg-muted px-1 py-0.5 text-xs">
              /api/v1/budgets
            </code>
            , and
            <code className="mx-1 break-all rounded bg-muted px-1 py-0.5 text-xs">
              /api/v1/transactions
            </code>
            still require a user JWT and will return 401 with an API token.
          </p>
        </AlertDescription>
      </Alert>

      {latestSecret && (
        <Alert>
          <KeyRound className="h-4 w-4" />
          <AlertTitle>Copy this token now</AlertTitle>
          <AlertDescription className="min-w-0 space-y-3">
            <div className="grid gap-2">
              <span className="font-medium text-foreground">Token</span>
              <code className="break-all rounded bg-muted px-2 py-2 text-xs">
                {latestSecret.token}
              </code>
              <Button
                variant="outline"
                className="min-h-11 w-full sm:min-h-9 sm:w-fit"
                onClick={() => copyValue("Token", latestSecret.token)}
              >
                <Copy className="h-4 w-4" />
                Copy Token
              </Button>
            </div>
            {latestSecret.secret && (
              <div className="grid gap-2">
                <span className="font-medium text-foreground">Secret</span>
                <code className="break-all rounded bg-muted px-2 py-2 text-xs">
                  {latestSecret.secret}
                </code>
                <Button
                  variant="outline"
                  className="min-h-11 w-full sm:min-h-9 sm:w-fit"
                  onClick={() => copyValue("Secret", latestSecret.secret ?? "")}
                >
                  <Copy className="h-4 w-4" />
                  Copy Secret
                </Button>
              </div>
            )}
            <p>Prefix: {latestSecret.token_prefix}</p>
            <p className="mt-2">
              Example:
              <code className="ml-1 break-all rounded bg-muted px-1 py-0.5 text-xs">
                Authorization: Bearer {latestSecret.token}
              </code>
            </p>
            <p className="mt-2">
              New tokens use letters and numbers only, so they are easier to
              paste into scripts, headers, and agent configs without escaping.
            </p>
            <p className="mt-2">
              Try it with
              <code className="mx-1 rounded bg-muted px-1 py-0.5 text-xs">
                GET /api/v1/agent/categories/
              </code>
              or another
              <code className="mx-1 rounded bg-muted px-1 py-0.5 text-xs">
                /api/v1/agent/*
              </code>
              endpoint.
            </p>
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Issued Tokens</CardTitle>
        </CardHeader>
        <CardContent className="px-4 sm:px-6">
          <div className="space-y-4">
            <div className="mobile-record-list">
              {tokens.map((token) => (
                <Card key={token.id} className="gap-4 py-4 shadow-none">
                  <CardContent className="space-y-4 px-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="break-words font-semibold">
                          {token.name}
                        </p>
                        <p className="break-all text-sm text-muted-foreground">
                          Prefix: {token.token_prefix}
                        </p>
                      </div>
                      <Badge
                        variant={token.is_active ? "default" : "secondary"}
                      >
                        {token.is_active ? "Active" : "Disabled"}
                      </Badge>
                    </div>
                    <dl className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <dt className="text-xs text-muted-foreground">
                          Expires
                        </dt>
                        <dd>
                          {token.expires_at
                            ? new Date(token.expires_at).toLocaleDateString()
                            : "Never"}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted-foreground">
                          Last used
                        </dt>
                        <dd className="break-words">
                          {token.last_used_at
                            ? new Date(token.last_used_at).toLocaleString()
                            : "Never"}
                        </dd>
                      </div>
                    </dl>
                    <div className="grid grid-cols-2 gap-2">
                      <Button
                        variant="outline"
                        className="min-h-11"
                        disabled={!token.is_active}
                        onClick={() => disableMutation.mutate(token.id)}
                      >
                        <Ban className="h-4 w-4" />
                        Disable
                      </Button>
                      <Button
                        variant="outline"
                        className="min-h-11"
                        disabled={deleteMutation.isPending}
                        onClick={() => {
                          if (
                            window.confirm(
                              `Delete API token "${token.name}" permanently?`,
                            )
                          ) {
                            deleteMutation.mutate(token.id)
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {!tokensQuery.isLoading && tokens.length === 0 && (
                <div className="rounded-lg border px-4 py-10 text-center text-sm text-muted-foreground">
                  No API tokens yet.
                </div>
              )}
            </div>
            <div className="desktop-table-only">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Prefix</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Expires</TableHead>
                    <TableHead>Last Used</TableHead>
                    <TableHead className="w-[220px] text-right">
                      Actions
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tokens.map((token) => (
                    <TableRow key={token.id}>
                      <TableCell className="font-medium">
                        {token.name}
                      </TableCell>
                      <TableCell>{token.token_prefix}</TableCell>
                      <TableCell>
                        <Badge
                          variant={token.is_active ? "default" : "secondary"}
                        >
                          {token.is_active ? "Active" : "Disabled"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {token.expires_at
                          ? new Date(token.expires_at).toLocaleDateString()
                          : "Never"}
                      </TableCell>
                      <TableCell>
                        {token.last_used_at
                          ? new Date(token.last_used_at).toLocaleString()
                          : "Never"}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={!token.is_active}
                            onClick={() => disableMutation.mutate(token.id)}
                          >
                            <Ban className="mr-2 h-4 w-4" />
                            Disable
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={deleteMutation.isPending}
                            onClick={() => {
                              if (
                                window.confirm(
                                  `Delete API token "${token.name}" permanently?`,
                                )
                              ) {
                                deleteMutation.mutate(token.id)
                              }
                            }}
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!tokensQuery.isLoading && tokens.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        No API tokens yet.
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
