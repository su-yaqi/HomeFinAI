import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { AiConnectionsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const AIConnections = () => {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const connections = useQuery({
    queryKey: ["ai-connections"],
    queryFn: () =>
      AiConnectionsService.listAiConnections({ page: 1, pageSize: 50 }),
  })
  const revoke = useMutation({
    mutationFn: (connectionId: string) =>
      AiConnectionsService.revokeAiConnection({ connectionId }),
    onSuccess: async () => {
      showSuccessToast("AI connection revoked")
      await queryClient.invalidateQueries({ queryKey: ["ai-connections"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <Card className="mt-4 max-w-3xl">
      <CardHeader>
        <CardTitle>AI Connections</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          These MCP clients can act only with the permissions you approved.
          Tokens are never shown here.
        </p>
        {connections.data?.data.length ? (
          connections.data.data.map((connection) => (
            <div key={connection.id} className="rounded-lg border p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 space-y-1">
                  <h3 className="font-medium">{connection.client_name}</h3>
                  <p className="break-all text-xs text-muted-foreground">
                    {connection.client_id}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Status: {connection.status} · Connected{" "}
                    {new Date(connection.created_at).toLocaleString()}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {connection.scopes.join(", ")}
                  </p>
                </div>
                {connection.status === "ACTIVE" && (
                  <Button
                    variant="destructive"
                    disabled={revoke.isPending}
                    onClick={() => {
                      if (
                        window.confirm(
                          "Revoke this AI connection? The client will need authorization again.",
                        )
                      ) {
                        revoke.mutate(connection.id)
                      }
                    }}
                  >
                    Revoke
                  </Button>
                )}
              </div>
            </div>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">
            No AI clients are connected.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export default AIConnections
