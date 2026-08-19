import { AxiosError } from "axios"
import { ApiError } from "./client"

function extractErrorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)
      ?.detail
    if (Array.isArray(detail) && detail.length > 0) {
      const firstDetail = detail[0] as { msg?: string }
      return firstDetail.msg || err.message
    }
    return typeof detail === "string" ? detail : err.message
  }

  if (err instanceof ApiError) {
    const errDetail = (err.body as { detail?: unknown } | undefined)?.detail
    if (Array.isArray(errDetail) && errDetail.length > 0) {
      const firstDetail = errDetail[0] as { msg?: string }
      return firstDetail.msg || err.message
    }
    return typeof errDetail === "string" ? errDetail : err.message
  }
  return err instanceof Error ? err.message : "Something went wrong."
}

export const handleError = function (
  this: (msg: string) => void,
  err: unknown,
) {
  const errorMessage = extractErrorMessage(err)
  this(errorMessage)
}

export const isAuthSessionInvalid = (err: unknown): boolean => {
  if (err instanceof AxiosError) {
    const detail = (err.response?.data as { detail?: string } | undefined)
      ?.detail
    return (
      err.response?.status === 401 ||
      err.response?.status === 403 ||
      (err.response?.status === 404 && detail === "User not found")
    )
  }

  const apiError = err as
    | {
        status?: number
        body?: { detail?: string }
      }
    | undefined

  return (
    apiError?.status === 401 ||
    apiError?.status === 403 ||
    (apiError?.status === 404 && apiError.body?.detail === "User not found")
  )
}

export const getInitials = (name: string): string => {
  return name
    .split(" ")
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase()
}
