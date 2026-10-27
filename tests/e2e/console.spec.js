const { test, expect } = require("@playwright/test");

test("operator console renders controls and reports invalid API token", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/WasteOps \| Collection Control/);
  await expect(page.getByText("WasteOps / Collection Control")).toBeVisible();
  await expect(page.getByLabel("Operator bearer token")).toHaveAttribute("type", "password");
  await expect(page.getByRole("button", { name: "Connect & load bins" })).toBeVisible();

  await page.route("**/api/v1/bins", async route => {
    await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Not authenticated" }) });
  });
  await page.getByLabel("API base URL").fill("http://api.test");
  await page.getByLabel("Operator bearer token").fill("invalid-token");
  await page.getByRole("button", { name: "Connect & load bins" }).click();
  await expect(page.getByRole("status")).toContainText(/not authenticated/i);
});

test("driver view reports authentication failure and does not invent jobs", async ({ page }) => {
  await page.route("**/api/v1/driver/jobs", async route => {
    await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Invalid driver credentials" }) });
  });
  await page.goto("/driver.html");
  await expect(page).toHaveTitle(/WasteOps \| Driver/);
  await expect(page.getByRole("heading", { name: "Driver sign-in" })).toBeVisible();
  await page.getByLabel("API base URL").fill("http://api.test");
  await page.getByLabel("Driver ID").fill("DRIVER-E2E");
  await page.getByLabel("Driver token").fill("invalid-token");
  await page.getByRole("button", { name: "Load assigned stops" }).click();
  await expect(page.getByRole("status")).toContainText(/invalid driver credentials/i);
  await expect(page.locator("#jobs")).toContainText("No jobs loaded.");
});

test("driver can start and complete an assigned stop", async ({ page }) => {
  let status = "assigned";
  await page.route("**/api/v1/driver/jobs", async route => {
    const jobs = status === "completed" ? [] : [{
      id: "job-e2e-0001",
      bin_id: "BIN-E2E",
      status,
      demand_liters: 120,
      priority: 88,
      latitude: 28.5355,
      longitude: 77.391,
    }];
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(jobs) });
  });
  await page.route("**/api/v1/driver/jobs/job-e2e-0001/transition", async route => {
    const body = route.request().postDataJSON();
    status = body.status;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "job-e2e-0001", status }) });
  });
  await page.goto("/driver.html");
  await page.getByLabel("API base URL").fill("http://api.test");
  await page.getByLabel("Driver ID").fill("DRIVER-E2E");
  await page.getByLabel("Driver token").fill("test-only-token");
  await page.getByRole("button", { name: "Load assigned stops" }).click();
  await expect(page.getByText("BIN-E2E")).toBeVisible();
  await expect(page.getByRole("button", { name: "Start stop" })).toBeVisible();
  await page.getByRole("button", { name: "Start stop" }).click();
  await expect(page.getByRole("button", { name: "Mark collected" })).toBeVisible();
  await page.getByRole("button", { name: "Mark collected" }).click();
  await expect(page.getByText(/No assigned or in-progress jobs/)).toBeVisible();
  await expect(page.getByRole("status")).toContainText(/loaded 0 assigned stops/i);
});


test("bin registration requires explicit measured data and provenance", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#lat")).toHaveValue("");
  await expect(page.locator("#lon")).toHaveValue("");
  await expect(page.locator("#capacity")).toHaveValue("");
  await expect(page.locator("#source")).toHaveValue("");
  await expect(page.locator("#criticality")).toHaveValue("");
  await expect(page.locator("#source")).toHaveAttribute("required", "");
});


test("operator console labels data provenance and avoids implying live telemetry", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("API records · source-labelled")).toBeVisible();
  await expect(page.getByText("Live API data")).toHaveCount(0);
  for (const id of ["capacity", "lat", "lon", "criticality", "source", "vehicleCap", "vehicleLat", "vehicleLon", "depotLat", "depotLon", "vehicleCapacity", "vehicleCount"]) {
    await expect(page.locator("#" + id)).toHaveValue("");
  }
  await expect(page.getByText(/the console does not invent telemetry/i)).toBeVisible();
});
