import { expect, test } from "@playwright/test"

test("Legacy items route redirects to transactions", async ({ page }) => {
  await page.goto("/items")
  await page.waitForURL("/transactions")
  await expect(
    page.getByRole("heading", { name: "Transactions" }),
  ).toBeVisible()
  await expect(
    page.getByRole("button", { name: "New Transaction" }),
  ).toBeVisible()
})
