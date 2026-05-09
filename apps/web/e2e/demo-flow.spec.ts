import { expect, test } from "@playwright/test";

test("judge demo flow is visible end to end", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Crucible Compute" })).toBeVisible();
  await page.getByRole("link", { name: "Start deployment" }).click();
  await expect(page.getByRole("heading", { name: "Create account" })).toBeVisible();
  const email = `judge-${Date.now()}@example.com`;
  const password = "correct horse battery staple";
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  await page.goto("/deployments/new");
  await page.getByLabel("Deployment request").fill("Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.");
  await page.getByRole("button", { name: "Generate plan" }).click();
  await expect(page.getByRole("button", { name: "Generating plan" })).toBeVisible();
  await expect(page.getByText("Approval required")).toBeVisible({ timeout: 20000 });

  await page.goto("/providers");
  await expect(page.getByText("Live deploy supported")).toBeVisible();

  await page.goto("/context");
  await expect(page.getByText("Context snippets used in agent decisions")).toBeVisible();

  await page.goto("/agent");
  await expect(page.getByText("crucible_plan_deployment")).toBeVisible();
});
