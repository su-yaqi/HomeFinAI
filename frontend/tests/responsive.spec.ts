import { expect, test } from "@playwright/test"

const protectedRoutes = [
  { path: "/", heading: "Financial Dashboard" },
  { path: "/transactions", heading: "Transactions", hasMobileList: true },
  { path: "/budgets", heading: "Budgets", hasMobileList: true },
  {
    path: "/system/categories",
    heading: "Categories",
    hasMobileList: true,
  },
  { path: "/settings", heading: "User Settings" },
  { path: "/system/accounts", heading: "Accounts", hasMobileList: true },
  {
    path: "/system/data-management",
    heading: "Data Management",
    hasMobileList: true,
  },
]

test.describe("mobile responsive layout", () => {
  for (const route of protectedRoutes) {
    test(`${route.path} fits the mobile viewport`, async ({ page }) => {
      await page.goto(route.path)
      await expect(
        page.getByRole("heading", { name: route.heading }),
      ).toBeVisible()

      const viewport = await page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      }))
      expect(viewport.scrollWidth).toBeLessThanOrEqual(viewport.clientWidth + 1)

      if (route.hasMobileList) {
        await expect(page.locator(".mobile-record-list")).toBeVisible()
      }
    })
  }

  test("all protected pages fit a 320px viewport", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 568 })
    for (const route of protectedRoutes) {
      await page.goto(route.path)
      await expect(
        page.getByRole("heading", { name: route.heading }),
      ).toBeVisible()
      const viewport = await page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      }))
      expect(viewport.scrollWidth).toBeLessThanOrEqual(viewport.clientWidth + 1)
    }
  })

  test("public authentication pages fit the mobile viewport", async ({
    page,
  }) => {
    await page.addInitScript(() => localStorage.removeItem("access_token"))

    const publicPages = [
      { path: "/login", heading: "Login to your account" },
      { path: "/recover-password", heading: "Password Recovery" },
      {
        path: "/reset-password?token=responsive-test",
        heading: "Reset Password",
      },
    ]

    for (const route of publicPages) {
      await page.goto(route.path)
      await expect(
        page.getByRole("heading", { name: route.heading }),
      ).toBeVisible()
      const viewport = await page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      }))
      expect(viewport.scrollWidth).toBeLessThanOrEqual(viewport.clientWidth + 1)
    }
  })

  test("mobile sidebar navigates and closes", async ({ page }) => {
    await page.goto("/")
    const trigger = page.locator('[data-sidebar="trigger"]')
    await trigger.click()

    const transactionsLink = page.getByRole("link", { name: "Transactions" })
    await expect(transactionsLink).toBeVisible()
    await transactionsLink.click()
    await expect(page).toHaveURL(/\/transactions$/)
    await expect(transactionsLink).toBeHidden()
  })

  test("long transaction dialog stays inside the dynamic viewport", async ({
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
        height: rect.height,
        top: rect.top,
        viewportHeight: window.innerHeight,
      }
    })

    expect(bounds.top).toBeGreaterThanOrEqual(0)
    expect(bounds.bottom).toBeLessThanOrEqual(bounds.viewportHeight + 1)
    expect(bounds.height).toBeLessThanOrEqual(bounds.viewportHeight)
    await expect(page.getByRole("button", { name: "Save" })).toBeVisible()
  })
})
