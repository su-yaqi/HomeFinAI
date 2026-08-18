import { expect, type Page, test } from "@playwright/test"
import { firstSuperuser, firstSuperuserPassword } from "./config.ts"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

const accountsUrl = "/system/accounts"

const openAddAccount = async (page: Page) => {
  await page.getByRole("button", { name: "Add Account" }).click()
}

const fillAccountIdentity = async (page: Page, email: string) => {
  await page
    .getByPlaceholder("homefin-admin")
    .fill(email.split("@", 1)[0] ?? email)
  await page.getByPlaceholder("Email").fill(email)
}

test("Accounts page is accessible and shows correct title", async ({
  page,
}) => {
  await page.goto(accountsUrl)
  await expect(page.getByRole("heading", { name: "Accounts" })).toBeVisible()
  await expect(
    page.getByText(
      "Manage login names, status, and privileges for system users.",
    ),
  ).toBeVisible()
})

test("Add Account button is visible", async ({ page }) => {
  await page.goto(accountsUrl)
  await expect(page.getByRole("button", { name: "Add Account" })).toBeVisible()
})

test.describe("Admin user management", () => {
  test("Create a new user successfully", async ({ page }) => {
    await page.goto(accountsUrl)

    const email = randomEmail()
    const password = randomPassword()
    const fullName = "Test User Admin"

    await openAddAccount(page)
    await fillAccountIdentity(page, email)
    await page.getByPlaceholder("Full name").fill(fullName)
    await page.getByPlaceholder("Password").first().fill(password)
    await page.getByPlaceholder("Password").last().fill(password)

    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User created successfully")).toBeVisible()

    await expect(page.getByRole("dialog")).not.toBeVisible()

    const userRow = page.getByRole("row").filter({ hasText: email })
    await expect(userRow).toBeVisible()
  })

  test("Create a superuser", async ({ page }) => {
    await page.goto(accountsUrl)

    const email = randomEmail()
    const password = randomPassword()

    await openAddAccount(page)
    await fillAccountIdentity(page, email)
    await page.getByPlaceholder("Password").first().fill(password)
    await page.getByPlaceholder("Password").last().fill(password)
    await page.getByLabel("Is superuser?").check()
    await page.getByLabel("Is active?").check()

    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User created successfully")).toBeVisible()

    await expect(page.getByRole("dialog")).not.toBeVisible()

    const userRow = page.getByRole("row").filter({ hasText: email })
    await expect(userRow.getByText("Superuser")).toBeVisible()
  })

  test("Edit a user successfully", async ({ page }) => {
    await page.goto(accountsUrl)

    const email = randomEmail()
    const password = randomPassword()
    const originalName = "Original Name"
    const updatedName = "Updated Name"

    await openAddAccount(page)
    await fillAccountIdentity(page, email)
    await page.getByPlaceholder("Full name").fill(originalName)
    await page.getByPlaceholder("Password").first().fill(password)
    await page.getByPlaceholder("Password").last().fill(password)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User created successfully")).toBeVisible()
    await expect(page.getByRole("dialog")).not.toBeVisible()

    const userRow = page.getByRole("row").filter({ hasText: email })
    await userRow.getByRole("button").click()

    await page.getByRole("menuitem", { name: "Edit User" }).click()

    await page.getByPlaceholder("Full name").fill(updatedName)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User updated successfully")).toBeVisible()
    await expect(userRow.getByText(updatedName, { exact: true })).toBeVisible()
  })

  test("Delete a user successfully", async ({ page }) => {
    await page.goto(accountsUrl)

    const email = randomEmail()
    const password = randomPassword()

    await openAddAccount(page)
    await fillAccountIdentity(page, email)
    await page.getByPlaceholder("Password").first().fill(password)
    await page.getByPlaceholder("Password").last().fill(password)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("User created successfully")).toBeVisible()

    await expect(page.getByRole("dialog")).not.toBeVisible()

    const userRow = page.getByRole("row").filter({ hasText: email })
    await userRow.getByRole("button").click()

    await page.getByRole("menuitem", { name: "Delete User" }).click()

    await page.getByRole("button", { name: "Delete" }).click()

    await expect(
      page.getByText("The user was deleted successfully"),
    ).toBeVisible()

    await expect(
      page.getByRole("row").filter({ hasText: email }),
    ).not.toBeVisible()
  })

  test("Cancel user creation", async ({ page }) => {
    await page.goto(accountsUrl)

    await openAddAccount(page)
    await fillAccountIdentity(page, "test@example.com")

    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(page.getByRole("dialog")).not.toBeVisible()
  })

  test("Email is required and must be valid", async ({ page }) => {
    await page.goto(accountsUrl)

    await openAddAccount(page)

    await page.getByPlaceholder("Email").fill("invalid-email")
    await page.getByPlaceholder("Email").blur()

    await expect(page.getByText("Invalid email address")).toBeVisible()
  })

  test("Password must be at least 8 characters", async ({ page }) => {
    await page.goto(accountsUrl)

    await openAddAccount(page)

    await fillAccountIdentity(page, randomEmail())
    await page.getByPlaceholder("Password").first().fill("short")
    await page.getByPlaceholder("Password").last().fill("short")
    await page.getByRole("button", { name: "Save" }).click()

    await expect(
      page.getByText("Password must be at least 8 characters"),
    ).toBeVisible()
  })

  test("Passwords must match", async ({ page }) => {
    await page.goto(accountsUrl)

    await openAddAccount(page)

    await fillAccountIdentity(page, randomEmail())
    await page.getByPlaceholder("Password").first().fill(randomPassword())
    await page.getByPlaceholder("Password").last().fill("different12345")
    await page.getByPlaceholder("Password").last().blur()

    await expect(page.getByText("The passwords don't match")).toBeVisible()
  })
})

test.describe("Accounts page access control", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Non-superuser cannot access accounts page", async ({ page }) => {
    const email = randomEmail()
    const password = randomPassword()

    await createUser({ email, password })
    await logInUser(page, email, password)

    await page.goto(accountsUrl)

    await expect(
      page.getByRole("heading", { name: "Accounts" }),
    ).not.toBeVisible()
    await expect(page).not.toHaveURL(/\/system\/accounts/)
  })

  test("Superuser can access accounts page", async ({ page }) => {
    await logInUser(page, firstSuperuser, firstSuperuserPassword)

    await page.goto(accountsUrl)

    await expect(page.getByRole("heading", { name: "Accounts" })).toBeVisible()
  })
})
