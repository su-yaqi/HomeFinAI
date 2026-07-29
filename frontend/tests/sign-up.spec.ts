import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

test("Public sign-up is disabled and redirects to login", async ({ page }) => {
  await page.goto("/signup")
  await page.waitForURL("/login")
  await expect(
    page.getByRole("heading", { name: "Login to your account" }),
  ).toBeVisible()
})
