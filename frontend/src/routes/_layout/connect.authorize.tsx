import { useMutation, useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"

import { AiConnectionsService } from "@/client"
import { PageHeader } from "@/components/Common/PageHeader"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const searchSchema = z.object({ request: z.string().min(1) })

export const Route = createFileRoute("/_layout/connect/authorize")({
  component: AuthorizeAIConnection,
  validateSearch: searchSchema,
  head: () => ({ meta: [{ title: "Authorize AI Connection - HomeFin" }] }),
})

function AuthorizeAIConnection() {
  const { request } = Route.useSearch()
  const { showErrorToast } = useCustomToast()
  const authorization = useQuery({
    queryKey: ["ai-authorization-request", request],
    queryFn: () => AiConnectionsService.readAuthorizationRequest({ request }),
  })
  const decision = useMutation({
    mutationFn: (approved: boolean) =>
      AiConnectionsService.decideAuthorizationRequest({
        requestBody: { request, approved },
      }),
    onSuccess: (result) => {
      const redirectUrl = result.redirect_url
      if (typeof redirectUrl !== "string") {
        showErrorToast("HomeFin returned an invalid OAuth redirect")
        return
      }
      window.location.assign(redirectUrl)
    },
    onError: handleError.bind(showErrorToast),
  })

  if (authorization.isLoading) {
    return (
      <p className="text-sm text-muted-foreground">
        Loading authorization request…
      </p>
    )
  }
  if (!authorization.data) {
    return (
      <p className="text-sm text-destructive">
        This authorization request is invalid or expired.
      </p>
    )
  }

  const data = authorization.data as {
    client_name?: string
    client_id?: string
    redirect_uri?: string
    scopes?: string[]
    user_name?: string
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <PageHeader
        title="Authorize AI Connection"
        description="Review exactly what this client can access in HomeFin."
      />
      <Card>
        <CardHeader>
          <CardTitle>{data.client_name || "AI client"}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <dl className="grid gap-3 text-sm sm:grid-cols-[9rem_1fr]">
            <dt className="text-muted-foreground">HomeFin user</dt>
            <dd className="break-all">{data.user_name}</dd>
            <dt className="text-muted-foreground">Client ID</dt>
            <dd className="break-all">{data.client_id}</dd>
            <dt className="text-muted-foreground">Callback</dt>
            <dd className="break-all">{data.redirect_uri}</dd>
          </dl>
          <div>
            <h3 className="mb-2 text-sm font-medium">Requested permissions</h3>
            <ul className="space-y-2 text-sm">
              {(data.scopes || []).map((scope) => (
                <li
                  key={scope}
                  className="rounded-md border px-3 py-2 font-mono text-xs"
                >
                  {scope}
                </li>
              ))}
            </ul>
          </div>
          <p className="text-sm text-muted-foreground">
            HomeFin will still require a separate confirmation before every
            write or delete.
          </p>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button
              variant="outline"
              disabled={decision.isPending}
              onClick={() => decision.mutate(false)}
            >
              Deny
            </Button>
            <Button
              disabled={decision.isPending}
              onClick={() => decision.mutate(true)}
            >
              Authorize
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
