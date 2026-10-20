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

test("site twin falls back to the 2D map without WebGL", async ({ page }) => {
  await signIn(page);
  await page.addInitScript(() => {
    type GetContext = HTMLCanvasElement["getContext"];
    const original: GetContext = HTMLCanvasElement.prototype.getContext;
    const patched = function (
      this: HTMLCanvasElement,
      contextId: string,
      options?: unknown,
    ): RenderingContext | null {
      if (contextId.startsWith("webgl")) return null;
      return original.call(this, contextId, options as never);
    };
    HTMLCanvasElement.prototype.getContext = patched as GetContext;
  });
  await page.goto("/site");
  await expect(
    page.getByRole("heading", { name: "Site Twin", level: 1 }),
  ).toBeVisible();
  await expect(page.getByTestId("site-map-2d")).toBeVisible();
});

test("dashboard renders KPIs and trend widget", async ({ page }) => {
  await signIn(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Dashboard", level: 1 }),
  ).toBeVisible();
  await expect(page.getByText("Incident trend")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Site Twin" })).toBeVisible();
});
