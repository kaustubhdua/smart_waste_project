const { test, expect } = require("@playwright/test");

test("driver can view cached stops and safely sync an offline action once", async ({ page, context }) => {
  let jobStatus = "assigned";
  let receivedKey = null;
  let transitionRequests = 0;

  await page.route("**/api/v1/driver/jobs", async route => {
    const jobs = jobStatus === "verified" ? [] : [{
      id: "job-offline-123456",
      bin_id: "bin-offline-01",
      status: jobStatus,
      demand_liters: 120,
      priority: 85,
      latitude: 28.6,
      longitude: 77.2,
    }];
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(jobs) });
  });

  await page.route("**/api/v1/driver/jobs/job-offline-123456/transition", async route => {
    transitionRequests += 1;
    receivedKey = route.request().headers()["idempotency-key"];
    expect(receivedKey).toMatch(/^[0-9a-f-]{36}$/i);
    const body = route.request().postDataJSON();
    expect(body.status).toBe("in_progress");
    jobStatus = "in_progress";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "job-offline-123456", previous_status: "assigned", status: "in_progress" }),
    });
  });

  await page.goto("/driver.html");
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  // The first load installs the service worker; reload once so it controls this page.
  await page.reload();
  await expect(page.locator("#driverId")).toBeVisible();
  await page.getByLabel("Driver ID").fill("driver-offline-01");
  await page.getByLabel("Driver token").fill("driver-token-for-e2e");
  await page.getByRole("button", { name: "Load assigned stops" }).click();
  await expect(page.locator("#jobs")).toContainText("bin-offline-01");
  expect(await page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);

  await context.setOffline(true);
  await expect(page.locator("#connection")).toContainText(/Offline/i);
  await page.getByRole("button", { name: "Start stop" }).click();
  await expect(page.locator("#status")).toContainText(/Saved in_progress locally/i);
  await expect(page.locator("#pendingActions")).toContainText("IN_PROGRESS");
  expect(transitionRequests).toBe(0);

  // The shell, cached stop and pending action survive a reload without a network.
  await page.reload();
  await expect(page.locator("#jobs")).toContainText("bin-offline-01");
  await expect(page.locator("#pendingActions")).toContainText("IN_PROGRESS");

  await context.setOffline(false);
  await expect(page.locator("#pendingActions")).toContainText("No pending actions for this driver.", { timeout: 10000 });
  await expect(page.locator("#jobs")).toContainText("IN_PROGRESS");
  expect(transitionRequests).toBe(1);
  expect(receivedKey).toBeTruthy();
});
