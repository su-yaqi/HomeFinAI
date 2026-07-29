import assert from "node:assert/strict"
import { access, readFile } from "node:fs/promises"
import test from "node:test"

test("frontend branding assets and footer copy are HomeFin-only", async () => {
  const [indexHtml, footerTsx] = await Promise.all([
    readFile(new URL("../index.html", import.meta.url), "utf8"),
    readFile(
      new URL("../src/components/Common/Footer.tsx", import.meta.url),
      "utf8",
    ),
  ])

  assert.equal(indexHtml.includes('/vite.svg"'), false)
  assert.equal(indexHtml.includes("/assets/images/favicon.png"), false)
  assert.equal(indexHtml.includes('/assets/images/homefin-icon.svg"'), true)

  assert.equal(footerTsx.includes("Full Stack FastAPI Template"), false)
  assert.equal(footerTsx.includes("FastAPI"), false)
  assert.equal(footerTsx.includes("HomeFin"), true)

  await assert.rejects(() =>
    access(
      new URL("../public/assets/images/fastapi-logo.svg", import.meta.url),
    ),
  )
  await assert.rejects(() =>
    access(new URL("../public/assets/images/favicon.png", import.meta.url)),
  )
})
