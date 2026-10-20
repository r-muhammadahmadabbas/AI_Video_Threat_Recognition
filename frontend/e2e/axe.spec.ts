import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const API_URL = process.env.E2E_API_URL ?? "http://127.0.0.1:8000";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

test.beforeEach(() => {
  test.setTimeout(90_000);
});

async function signIn(page: Page) {
  const response = await page.request.post(`${API_URL}/auth/login`, {
    form: {
      username: "admin@example.com",
      password: "admin123",
    },
  });
  expect(response.ok()).toBeTruthy();
  const tokens = (await response.json()) as {
    access_token: string;
    refresh_token: string;
  };
  await page.addInitScript(
    ({ access, refresh }) => {
      window.localStorage.setItem("access_token", access);
      window.localStorage.setItem("refresh_token", refresh);
    },
    { access: tokens.access_token, refresh: tokens.refresh_token },
  );
}

async function scan(page: Page, path: string) {
  await page.goto(path);
  await page.waitForLoadState("domcontentloaded");
  await expect(page.locator("h1").first()).toBeVisible();
  await page.waitForTimeout(600);
  await page.addStyleTag({
    content:
      "*,*::before,*::after{animation:none!important;transition:none!important}",
  });
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  return results.violations;
}

function summarize(violations: Awaited<ReturnType<typeof scan>>): string {
  return violations
    .map(
      (violation) =>
        `${violation.id} (${violation.nodes.length} node(s)): ${violation.nodes
          .slice(0, 3)
          .map((node) => node.target.join(" "))
          .join(", ")}`,
    )
    .join("\n");
}

test("login page has no WCAG A/AA violations", async ({ page }) => {
  const violations = await scan(page, "/login");
  expect(violations, summarize(violations)).toEqual([]);
});

for (const route of ["/", "/incidents", "/site", "/cameras", "/detect"]) {
  test(`${route} has no WCAG A/AA violations`, async ({ page }) => {
    await signIn(page);
    const violations = await scan(page, route);
    expect(violations, summarize(violations)).toEqual([]);
  });
}
