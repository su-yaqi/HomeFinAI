import { expect, type Page } from "@playwright/test"

export async function logInUser(page: Page, email: string, password: string) {
  await page.goto("/login")

  await page
    .getByTestId("login-name-input")
    .fill(email.split("@", 1)[0] ?? email)
  await page.getByTestId("password-input").fill(password)
  await page.getByRole("button", { name: "Log In" }).click()
  await page.waitForURL("/")
  await expect(
    page.getByRole("heading", { name: "Financial Dashboard" }),
  ).toBeVisible()
}

export async function logOutUser(page: Page) {
  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log out" }).click()
  await page.goto("/login")
}
