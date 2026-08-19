import { useMutation, useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"

import { LoginService, type UserPublic, UsersService } from "@/client"
import { handleError } from "@/utils"
import useCustomToast from "./useCustomToast"

export type LoginCredentials = {
  username: string
  password: string
  mfa_code?: string
}

const isLoggedIn = () => {
  return localStorage.getItem("access_token") !== null
}

const useAuth = () => {
  const navigate = useNavigate()
  const { showErrorToast } = useCustomToast()

  const { data: user } = useQuery<UserPublic | null, Error>({
    queryKey: ["currentUser"],
    queryFn: UsersService.readUserMe,
    enabled: isLoggedIn(),
  })

  const login = async (data: LoginCredentials) => {
    const response = await LoginService.loginAccessToken({
      formData: data,
    })
    localStorage.setItem("access_token", response.access_token)
  }

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: () => {
      const returnTo = sessionStorage.getItem("post_login_redirect")
      sessionStorage.removeItem("post_login_redirect")
      if (returnTo?.startsWith("/") && !returnTo.startsWith("//")) {
        window.location.assign(returnTo)
        return
      }
      navigate({ to: "/" })
    },
    onError: handleError.bind(showErrorToast),
  })

  const logout = () => {
    localStorage.removeItem("access_token")
    navigate({ to: "/login" })
  }

  return {
    loginMutation,
    logout,
    user,
  }
}

export { isLoggedIn }
export default useAuth
