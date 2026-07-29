import { expect, test } from "@playwright/test"

const protectedRoutes = [
  { path: "/", heading: "Financial Dashboard" },
  { path: "/transactions", heading: "Transactions" },
  { path: "/budgets", heading: "Budgets" },
  { path: "/system/categories", heading: "Categories" },
  { path: "/settings", heading: "User Settings" },
  { path: "/system/accounts", heading: "Accounts" },
  { path: "/system/api-tokens", heading: "API Tokens" },
  { path: "/system/data-management", heading: "Data Management" },
]

test.describe("desktop responsive regression", () => {
  for (const route of protectedRoutes) {
    test(`${route.path} keeps its desktop layout`, async ({ page }) => {
      await page.goto(route.path)
      await expect(
        page.getByRole("heading", { name: route.heading }),
      ).toBeVisible()

      const viewport = await page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      }))
      expect(viewport.scrollWidth).toBeLessThanOrEqual(viewport.clientWidth + 1)

      await expect(page.locator('[data-sidebar="sidebar"]')).toBeVisible()
    })
  }

  test("desktop transaction dialog opens without leaving the viewport", async ({
    page,
  }) => {
    await page.goto("/transactions")
    await page.getByRole("button", { name: "New Transaction" }).click()

    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()
    const bounds = await dialog.evaluate((element) => {
      const rect = element.getBoundingClientRect()
      return {
        bottom: rect.bottom,
        top: rect.top,
        viewportHeight: window.innerHeight,
      }
    })

    expect(bounds.top).toBeGreaterThanOrEqual(0)
    expect(bounds.bottom).toBeLessThanOrEqual(bounds.viewportHeight + 1)
  })
})
