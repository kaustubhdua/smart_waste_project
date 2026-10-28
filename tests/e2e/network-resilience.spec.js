const { test, expect } = require("@playwright/test");

async function installLeafletStub(page) {
  await page.addInitScript(() => {
    window.L = {
      map: () => ({ setView() { return this; }, fitBounds() {} }),
      tileLayer: () => ({ addTo() { return this; } }),
      circleMarker: () => ({ bindPopup() { return this; }, addTo() { return this; }, setStyle() {}, remove() {} }),
      geoJSON: () => ({ addTo() { return this; }, remove() { return this; } }),
    };
  });
  await page.route("https://unpkg.com/**", route => route.fulfill({
    status: 200,
    contentType: "application/javascript",
    body: "/* Leaflet is stubbed for isolated UI tests. */",
  }));
}

test("operator console shows a genuinely empty API without inventing bins", async ({ page }) => {
  await installLeafletStub(page);
  await page.route("**/api/v1/bins", route => route.fulfill({ json: [] }));
  await page.route("**/api/v1/jobs?limit=100", route => route.fulfill({ json: [] }));
  await page.route("**/api/v1/vehicles", route => route.fulfill({ json: [] }));
  await page.goto("/");
  await page.locator("#token").fill("test-only-token");
  await page.locator("#connect").click();
  await expect(page.locator("#binCount")).toHaveText("0");
  await expect(page.locator("#bins")).toContainText("No bins registered yet");
  await expect(page.locator("#status")).toContainText("Loaded 0 bins from API");
  await expect(page.locator("#bins")).not.toContainText("BIN-001");
});

test("operator console explains API network failures", async ({ page }) => {
  await installLeafletStub(page);
  await page.route("**/api/v1/bins", route => route.abort());
  await page.goto("/");
  await page.locator("#token").fill("test-only-token");
  await page.locator("#connect").click();
  await expect(page.locator("#status")).toContainText("Could not reach the API");
  await expect(page.locator("#status")).toHaveClass(/error/);
});

test("driver view explains API network failures", async ({ page }) => {
  await page.route("**/api/v1/driver/jobs", route => route.abort());
  await page.goto("/driver.html");
  await page.locator("#driverId").fill("driver-test");
  await page.locator("#token").fill("test-only-token");
  await page.locator('button[type="submit"]').click();
  await expect(page.locator("#status")).toContainText("Could not reach the API");
  await expect(page.locator("#status")).toHaveClass(/error/);
});

test("operator console does not mislabel failed telemetry lookups as empty history", async ({ page }) => {
  await installLeafletStub(page);
  await page.route("**/api/v1/bins", route => route.fulfill({ json: [
    { id: "BIN-REAL-01", capacity_liters: 120, source: "live", criticality: 3, latitude: 28.6, longitude: 77.2 },
  ] }));
  await page.route("**/api/v1/bins/BIN-REAL-01/history*", route => route.abort());
  await page.route("**/api/v1/jobs?limit=100", route => route.fulfill({ json: [] }));
  await page.route("**/api/v1/vehicles", route => route.fulfill({ json: [] }));
  await page.goto("/");
  await page.locator("#token").fill("test-only-token");
  await page.locator("#connect").click();
  await expect(page.locator("#bins")).toContainText("telemetry unavailable");
  await expect(page.locator("#bins")).not.toContainText("no readings yet");
  await expect(page.locator("#status")).toContainText("telemetry history unavailable for 1 bin");
  await expect(page.locator("#status")).toHaveClass(/error/);
});

test("operator console warns when job data cannot be refreshed", async ({ page }) => {
  await installLeafletStub(page);
  await page.route("**/api/v1/bins", route => route.fulfill({ json: [] }));
  await page.route("**/api/v1/jobs?limit=100", route => route.abort());
  await page.route("**/api/v1/vehicles", route => route.fulfill({ json: [] }));
  await page.goto("/");
  await page.locator("#token").fill("test-only-token");
  await page.locator("#connect").click();
  await expect(page.locator("#status")).toContainText("collection jobs or vehicles could not be refreshed");
  await expect(page.locator("#status")).toHaveClass(/error/);
});
