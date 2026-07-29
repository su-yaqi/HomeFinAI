import { useMutation, useQueryClient } from "@tanstack/react-query"
import { KeyRound, RotateCcw, ShieldAlert } from "lucide-react"
import { useState } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { homefinApi } from "@/features/homefin/api"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const MfaSettings = () => {
  const queryClient = useQueryClient()
  const { user: currentUser } = useAuth()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [setupSecret, setSetupSecret] = useState<string | null>(null)
  const [setupUri, setSetupUri] = useState<string | null>(null)
  const [verificationCode, setVerificationCode] = useState("")

  const refreshCurrentUser = async () => {
    await queryClient.invalidateQueries({ queryKey: ["currentUser"] })
  }

  const setupMutation = useMutation({
    mutationFn: () => homefinApi.setupMyMfa(),
    onSuccess: (payload) => {
      setSetupSecret(payload.secret)
      setSetupUri(payload.otpauth_uri)
      setVerificationCode("")
    },
    onError: handleError.bind(showErrorToast) as never,
  })

  const enableMutation = useMutation({
    mutationFn: () =>
      homefinApi.enableMyMfa({
        secret: setupSecret ?? "",
        code: verificationCode,
      }),
    onSuccess: async () => {
      showSuccessToast("MFA enabled successfully")
      setSetupSecret(null)
      setSetupUri(null)
      setVerificationCode("")
      await refreshCurrentUser()
    },
    onError: handleError.bind(showErrorToast) as never,
  })

  const resetMutation = useMutation({
    mutationFn: () => homefinApi.resetMyMfa(),
    onSuccess: async () => {
      showSuccessToast("MFA reset successfully")
      setSetupSecret(null)
      setSetupUri(null)
      setVerificationCode("")
      await refreshCurrentUser()
    },
    onError: handleError.bind(showErrorToast) as never,
  })

  const disableMutation = useMutation({
    mutationFn: () => homefinApi.disableMyMfa(),
    onSuccess: async () => {
      showSuccessToast("MFA disabled successfully")
      setSetupSecret(null)
      setSetupUri(null)
      setVerificationCode("")
      await refreshCurrentUser()
    },
    onError: handleError.bind(showErrorToast) as never,
  })

  const isLoading =
    setupMutation.isPending ||
    enableMutation.isPending ||
    resetMutation.isPending ||
    disableMutation.isPending

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <KeyRound className="h-5 w-5" />
          Multi-factor authentication
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-col gap-4 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="font-medium">
              {currentUser?.has_mfa ? "MFA is enabled" : "MFA is not enabled"}
            </p>
            <p className="text-sm text-muted-foreground">
              {currentUser?.has_mfa
                ? "You will need a 6-digit authenticator code the next time you sign in."
                : "Add an authenticator app to require a 6-digit code at sign-in."}
            </p>
          </div>
          {!currentUser?.has_mfa ? (
            <LoadingButton
              className="w-full sm:w-auto"
              onClick={() => setupMutation.mutate()}
              loading={setupMutation.isPending}
            >
              Set up MFA
            </LoadingButton>
          ) : (
            <div className="flex flex-col gap-2 min-[420px]:flex-row">
              <LoadingButton
                className="min-h-11 flex-1 sm:min-h-9"
                variant="outline"
                onClick={() => resetMutation.mutate()}
                loading={resetMutation.isPending}
              >
                <RotateCcw className="mr-2 h-4 w-4" />
                Reset
              </LoadingButton>
              <LoadingButton
                className="min-h-11 flex-1 sm:min-h-9"
                variant="destructive"
                onClick={() => disableMutation.mutate()}
                loading={disableMutation.isPending}
              >
                Disable
              </LoadingButton>
            </div>
          )}
        </div>

        {setupSecret && (
          <div className="space-y-4 rounded-lg border border-dashed p-4">
            <Alert>
              <ShieldAlert className="h-4 w-4" />
              <AlertTitle>Finish setup in your authenticator app</AlertTitle>
              <AlertDescription>
                Scan the QR-equivalent URI in a compatible app or enter the
                secret manually, then confirm with a current 6-digit code.
              </AlertDescription>
            </Alert>

            <div className="space-y-2">
              <p className="text-sm font-medium">Manual secret</p>
              <code className="block rounded bg-muted px-3 py-2 text-sm break-all">
                {setupSecret}
              </code>
            </div>

            {setupUri && (
              <div className="space-y-2">
                <p className="text-sm font-medium">otpauth URI</p>
                <code className="block rounded bg-muted px-3 py-2 text-xs break-all">
                  {setupUri}
                </code>
              </div>
            )}

            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="flex-1 space-y-2">
                <p className="text-sm font-medium">Verification code</p>
                <Input
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="123456"
                  value={verificationCode}
                  onChange={(event) =>
                    setVerificationCode(
                      event.target.value.replace(/\D/g, "").slice(0, 6),
                    )
                  }
                />
              </div>
              <div className="flex flex-col gap-2 min-[420px]:flex-row">
                <Button
                  className="min-h-11 flex-1 sm:min-h-9"
                  variant="outline"
                  onClick={() => {
                    setSetupSecret(null)
                    setSetupUri(null)
                    setVerificationCode("")
                  }}
                  disabled={isLoading}
                >
                  Cancel
                </Button>
                <LoadingButton
                  className="min-h-11 flex-1 sm:min-h-9"
                  onClick={() => enableMutation.mutate()}
                  loading={enableMutation.isPending}
                  disabled={verificationCode.length !== 6}
                >
                  Enable MFA
                </LoadingButton>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default MfaSettings
