import { useMutation, useQueryClient } from "@tanstack/react-query"
import { ShieldAlert } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { LoadingButton } from "@/components/ui/loading-button"
import { homefinApi } from "@/features/homefin/api"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface ResetUserMfaProps {
  userId: string
  loginName: string
  onSuccess: () => void
}

const ResetUserMfa = ({ userId, loginName, onSuccess }: ResetUserMfaProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { handleSubmit } = useForm()

  const mutation = useMutation({
    mutationFn: () => homefinApi.resetUserMfa(userId),
    onSuccess: () => {
      showSuccessToast("MFA reset successfully")
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast) as never,
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(event) => event.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <ShieldAlert />
        Reset MFA
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit(() => mutation.mutate())}>
          <DialogHeader>
            <DialogTitle>Reset MFA</DialogTitle>
            <DialogDescription>
              Reset MFA for <strong>{loginName}</strong>. Their existing
              authenticator binding will stop working immediately, and they will
              need to set up MFA again from Settings if they want to keep using
              it.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4">
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>
                Cancel
              </Button>
            </DialogClose>
            <LoadingButton type="submit" loading={mutation.isPending}>
              Reset MFA
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default ResetUserMfa
