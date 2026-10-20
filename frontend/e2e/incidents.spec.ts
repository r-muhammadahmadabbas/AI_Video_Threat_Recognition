import { expect, test, type Page } from "@playwright/test";

const API_URL = process.env.E2E_API_URL ?? "http://127.0.0.1:8000";

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

test("incident filters are mirrored in the URL", async ({ page }) => {
  await signIn(page);
  await page.goto("/incidents?severity=high&q=weapon&status=detected");
  await expect(
    page.getByRole("heading", { name: "Incidents", level: 1 }),
  ).toBeVisible();
  await expect(page.getByLabel("Filter by event type")).toHaveValue("weapon");
  await expect(page.getByRole("button", { name: "High" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  await page.getByRole("button", { name: "All", exact: true }).click();
  await expect(page).not.toHaveURL(/severity=/);

  await page.getByLabel("Filter by status").click();
  await page.getByRole("option", { name: "pending review" }).click();
  await expect(page).toHaveURL(/status=pending_review/);

  await page.getByLabel("Filter by event type").fill("person");
  await expect(page).toHaveURL(/q=person/);
});

test("pending KPI opens the pending-review filter", async ({ page }) => {
  await signIn(page);
  await page.goto("/");
  await page.getByRole("link", { name: /Pending/ }).click();
  await expect(page).toHaveURL(/status=pending_review/);
  await expect(page.getByLabel("Filter by status")).toContainText(
    "pending review",
  );
});
