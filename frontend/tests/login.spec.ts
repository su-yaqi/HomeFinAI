import { expect, type Page, test } from "@playwright/test"
import { firstSuperuser, firstSuperuserPassword } from "./config.ts"
import { randomPassword } from "./utils/random.ts"
import { toLoginName } from "./utils/user.ts"

test.use({ storageState: { cookies: [], origins: [] } })

const apiBaseUrl = process.env.VITE_API_URL ?? "http://localhost:8000"

const fillForm = async (page: Page, loginName: string, password: string) => {
  await page.getByTestId("login-name-input").fill(loginName)
  await page.getByTestId("password-input").fill(password)
}

const verifyInput = async (page: Page, testId: string) => {
  const input = page.getByTestId(testId)
  await expect(input).toBeVisible()
  await expect(input).toHaveText("")
  await expect(input).toBeEditable()
}

test("Inputs are visible, empty and editable", async ({ page }) => {
  await page.goto("/login")

  await verifyInput(page, "login-name-input")
  await verifyInput(page, "password-input")
  await verifyInput(page, "mfa-code-input")
})

test("Log In button is visible", async ({ page }) => {
  await page.goto("/login")

  await expect(page.getByRole("button", { name: "Log In" })).toBeVisible()
})

test("Log in with valid login name and password", async ({ page }) => {
  await page.goto("/login")

  await fillForm(page, toLoginName(firstSuperuser), firstSuperuserPassword)
  await page.getByRole("button", { name: "Log In" }).click()

  await page.waitForURL("/")

  await expect(
    page.getByRole("heading", { name: "Financial Dashboard" }),
  ).toBeVisible()
})

test("Login name is required", async ({ page }) => {
  await page.goto("/login")

  await fillForm(page, "", firstSuperuserPassword)
  await page.getByRole("button", { name: "Log In" }).click()

  await expect(page.getByText("Login name is required")).toBeVisible()
})

test("Log in with invalid password", async ({ page }) => {
  const password = randomPassword()

  await page.goto("/login")
  await fillForm(page, toLoginName(firstSuperuser), password)
  await page.getByRole("button", { name: "Log In" }).click()

  await expect(page.getByText("Incorrect login name or password")).toBeVisible()
})

test("Successful log out", async ({ page }) => {
  await page.goto("/login")

  await fillForm(page, toLoginName(firstSuperuser), firstSuperuserPassword)
  await page.getByRole("button", { name: "Log In" }).click()

  await page.waitForURL("/")

  await expect(
    page.getByRole("heading", { name: "Financial Dashboard" }),
  ).toBeVisible()

  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log Out" }).click()
  await page.waitForURL("/login")
})

test("Logged-out user cannot access protected routes", async ({ page }) => {
  await page.goto("/login")

  await fillForm(page, toLoginName(firstSuperuser), firstSuperuserPassword)
  await page.getByRole("button", { name: "Log In" }).click()

  await page.waitForURL("/")

  await expect(
    page.getByRole("heading", { name: "Financial Dashboard" }),
  ).toBeVisible()

  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log Out" }).click()
  await page.waitForURL("/login")

  await page.goto("/settings")
  await page.waitForURL("/login")
})

test("Redirects to /login when token is wrong", async ({ page }) => {
  await page.goto("/settings")
  await page.evaluate(() => {
    localStorage.setItem("access_token", "invalid_token")
  })
  await page.goto("/settings")
  await page.waitForURL("/login")
  await expect(page).toHaveURL("/login")
})

test("Redirects to /login when token user no longer exists", async ({
  page,
  request,
}) => {
  const email = `deleted-user-${Date.now()}@example.com`
  const password = randomPassword()

  const adminLogin = await request.post(
    `${apiBaseUrl}/api/v1/login/access-token`,
    {
      form: {
        username: toLoginName(firstSuperuser),
        password: firstSuperuserPassword,
      },
    },
  )
  expect(adminLogin.ok()).toBeTruthy()
  const adminToken = (await adminLogin.json()).access_token as string

  const createUserResponse = await request.post(`${apiBaseUrl}/api/v1/users/`, {
    headers: {
      Authorization: `Bearer ${adminToken}`,
    },
    data: {
      email,
      login_name: toLoginName(email),
      password,
      full_name: "Deleted User",
    },
  })
  expect(createUserResponse.ok()).toBeTruthy()
  const createdUser = await createUserResponse.json()

  await page.goto("/login")
  await page.getByTestId("login-name-input").fill(toLoginName(email))
  await page.getByTestId("password-input").fill(password)
  await page.getByRole("button", { name: "Log In" }).click()
  await page.waitForURL("/")

  const deleteUserResponse = await request.delete(
    `${apiBaseUrl}/api/v1/users/${createdUser.id}`,
    {
      headers: {
        Authorization: `Bearer ${adminToken}`,
      },
    },
  )
  expect(deleteUserResponse.ok()).toBeTruthy()

  await page.goto("/")
  await page.waitForURL("/login")
  await expect(page).toHaveURL("/login")
})
