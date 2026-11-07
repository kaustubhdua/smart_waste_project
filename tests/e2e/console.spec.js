const { test, expect } = require("@playwright/test");

test("operator console renders controls and reports invalid API token", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/WasteOps \| Collection Control/);
  await expect(page.getByText("WasteOps / Collection Control")).toBeVisible();
  await expect(page.getByLabel("Operator bearer token")).toHaveAttribute("type", "password");
  await expect(page.getByRole("note")).toContainText(/operator token is sent to this host/i);
  await expect(page.getByRole("button", { name: "Connect & load bins" })).toBeVisible();

  await page.route("**/api/v1/bins", async route => {
    await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Not authenticated" }) });
  });
  await page.getByLabel("API base URL").fill("https://api.test");
  await page.getByLabel("Operator bearer token").fill("invalid-token");
  await page.getByRole("button", { name: "Connect & load bins" }).click();
  await expect(page.getByRole("status")).toContainText(/not authenticated/i);
});

test("operator console rejects insecure remote API hosts before sending credentials", async ({ page }) => {
  let requestSent = false;
  page.on("request", request => { if (request.url().startsWith("http://api.test/")) requestSent = true; });
  await page.goto("/");
  await page.getByLabel("API base URL").fill("http://api.test");
  await page.getByLabel("Operator bearer token").fill("must-not-leave-browser");
  await page.getByRole("button", { name: "Connect & load bins" }).click();
  await expect(page.getByRole("status")).toContainText(/remote API hosts must use HTTPS/i);
  expect(requestSent).toBe(false);
});

test("driver view rejects insecure remote API hosts before sending credentials", async ({ page }) => {
  let requestSent = false;
  page.on("request", request => { if (request.url().startsWith("http://api.test/")) requestSent = true; });
  await page.goto("/driver.html");
  await page.getByLabel("API base URL").fill("http://api.test");
  await page.getByLabel("Driver ID").fill("DRIVER-E2E");
  await page.getByLabel("Driver token").fill("must-not-leave-browser");
  await page.getByRole("button", { name: "Load assigned stops" }).click();
  await expect(page.getByRole("status")).toContainText(/remote API hosts must use HTTPS/i);
  expect(requestSent).toBe(false);
});

test("driver view reports authentication failure and does not invent jobs", async ({ page }) => {
  await page.route("**/api/v1/driver/jobs", async route => {
    await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Invalid driver credentials" }) });
  });
  await page.goto("/driver.html");
  await expect(page).toHaveTitle(/WasteOps \| Driver/);
  await expect(page.getByRole("heading", { name: "Driver sign-in" })).toBeVisible();
  await expect(page.getByRole("note")).toContainText(/driver credentials are sent to this host/i);
  await page.getByLabel("API base URL").fill("https://api.test");
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
  await page.getByLabel("API base URL").fill("https://api.test");
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

test("operator console treats API-controlled labels as text, not executable markup", async ({ page }) => {
  const hostileId = '<img src=x onerror=alert(1)>BIN-XSS';
  let dialogOpened = false;
  page.on("dialog", async dialog => {
    dialogOpened = true;
    await dialog.dismiss();
  });
  await page.route("**/api/v1/bins", async route => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([{
        id: hostileId,
        latitude: 28.6,
        longitude: 77.2,
        capacity_liters: 1000,
        criticality: 2,
        source: "imported",
      }]),
    });
  });
  await page.route("**/api/v1/bins/**/history*", async route => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/v1/jobs**", async route => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/v1/vehicles", async route => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await page.goto("/");
  await page.getByLabel("Operator bearer token").fill("test-only-token");
  await page.getByRole("button", { name: "Connect & load bins" }).click();
  await expect(page.locator("#bins")).toContainText(hostileId);
  await expect(page.locator("#bins img")).toHaveCount(0);
  await expect(page.locator("#status")).toContainText(/loaded 1 bin from api/i);
  expect(dialogOpened).toBe(false);
});

test("operator and driver views fit a narrow mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Connect & load bins" })).toBeVisible();
  const operatorWidth = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth,
  }));
  expect(operatorWidth.document).toBeLessThanOrEqual(operatorWidth.viewport);

  await page.goto("/driver.html");
  await expect(page.getByRole("button", { name: "Load assigned stops" })).toBeVisible();
  const driverWidth = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth,
  }));
  expect(driverWidth.document).toBeLessThanOrEqual(driverWidth.viewport);
});

test("operator can register a bin through the API contract with explicit provenance", async ({ page }) => {
  const created = {
    id: "BIN-REGISTRATION-E2E",
    latitude: 28.6139,
    longitude: 77.209,
    capacity_liters: 1100,
    criticality: 3,
    source: "live",
    active: true,
  };
  let persisted = false;
  let postedPayload;

  await page.route("**/api/v1/bins", async route => {
    if (route.request().method() === "POST") {
      postedPayload = route.request().postDataJSON();
      persisted = true;
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(created) });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(persisted ? [created] : []),
    });
  });
  await page.route("**/api/v1/bins/**/history*", async route => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/v1/jobs**", async route => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/v1/vehicles", async route => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await page.goto("/");
  await page.getByLabel("Operator bearer token").fill("test-only-token");
  await page.getByRole("button", { name: "Connect & load bins" }).click();
  await expect(page.getByText(/No bins registered yet/)).toBeVisible();

  await page.getByLabel("Bin ID").fill(created.id);
  await page.locator("#capacity").fill(String(created.capacity_liters));
  await page.locator("#lat").fill(String(created.latitude));
  await page.locator("#lon").fill(String(created.longitude));
  await page.getByLabel("Criticality").selectOption(String(created.criticality));
  await page.getByLabel("Data source").selectOption(created.source);
  await page.getByRole("button", { name: "Create bin record" }).click();

  await expect(page.getByRole("status")).toContainText(/Loaded 1 bins? from API/);
  await expect(page.locator("#bins")).toContainText(created.id);
  expect(postedPayload).toEqual({
    id: created.id,
    latitude: created.latitude,
    longitude: created.longitude,
    capacity_liters: created.capacity_liters,
    criticality: created.criticality,
    source: "live",
  });
});

test("operator bin form does not submit without required source and measured fields", async ({ page }) => {
  let createRequests = 0;
  await page.route("**/api/v1/bins", async route => {
    if (route.request().method() === "POST") createRequests += 1;
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.goto("/");
  await page.getByLabel("Bin ID").fill("BIN-INCOMPLETE");
  await page.getByRole("button", { name: "Create bin record" }).click();
  expect(createRequests).toBe(0);
  await expect(page.locator("#source")).toHaveValue("");
  await expect(page.locator("#status")).toContainText(/Sign in with your named operator account/);
});

test("operator can import historical telemetry with multipart form data and honest provenance", async ({ page }) => {
  let uploadRequest;
  await page.route("https://api.test/api/v1/bins", async route => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("https://api.test/api/v1/jobs**", async route => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("https://api.test/api/v1/vehicles", async route => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("https://api.test/api/v1/telemetry/import-csv", async route => {
    uploadRequest = route.request();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ accepted: 2, duplicates_skipped: 1, source: "imported" }),
    });
  });
  await page.goto("/");
  await page.getByLabel("API base URL").fill("https://api.test");
  await page.getByLabel("Operator bearer token").fill("test-only-token");
  await page.locator("#telemetryCsv").setInputFiles({
    name: "readings.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("bin_id,device_id,message_id,fill_percent,measured_at\nBIN-001,SENSOR-001,msg-1,42,2026-10-27T10:00:00Z\n"),
  });
  await page.getByRole("button", { name: "Import historical telemetry" }).click();
  await expect(page.locator("#telemetryImportResult")).toContainText("Accepted: 2 new readings");
  await expect(page.locator("#telemetryImportResult")).toContainText("Duplicates skipped: 1");
  await expect(page.locator("#status")).toContainText(/source is labelled imported/i);
  expect(uploadRequest).toBeTruthy();
  expect(uploadRequest.method()).toBe("POST");
  expect(uploadRequest.headers()["content-type"]).toMatch(/^multipart\/form-data; boundary=/i);
  expect(uploadRequest.headers()["authorization"]).toBe("Bearer test-only-token");
});


test("operator can sign in with a named account, use an expiring session and sign out", async ({ page }) => {
  const observed = [];
  await page.route("**/api/v1/auth/login", async route => {
    expect(route.request().postDataJSON()).toEqual({
      username: "ops.dispatch",
      password: "a-long-test-password",
    });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        expires_at: "2026-11-08T12:00:00Z",
        user: { id: "user-1", username: "ops.dispatch", role: "operator" },
      }),
      headers: { "Set-Cookie": "wasteops_session=opaque-session-for-browser-test; Path=/api/v1; HttpOnly; SameSite=Strict" },
    });
  });
  await page.route("**/api/v1/auth/me", async route => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "user-1", username: "ops.dispatch", role: "operator" }) });
  });
  await page.route("**/api/v1/bins", async route => {
    observed.push(route.request().headers()["cookie"]);
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/v1/jobs**", async route => {
    observed.push(route.request().headers()["cookie"]);
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/v1/vehicles", async route => {
    observed.push(route.request().headers()["cookie"]);
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/v1/auth/logout", async route => {
    observed.push(route.request().headers()["cookie"]);
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ logged_out: true }), headers: { "Set-Cookie": "wasteops_session=; Path=/api/v1; Max-Age=0; HttpOnly; SameSite=Strict" } });
  });

  await page.goto("/");
  await page.getByLabel("Operator username").fill("ops.dispatch");
  await page.getByLabel("Password", { exact: true }).fill("a-long-test-password");
  await page.getByRole("button", { name: "Connect & load bins" }).click();
  await expect(page.getByRole("status")).toContainText(/Loaded 0 bins from API/i);
  expect(observed.length).toBeGreaterThan(0);
  expect(observed.every(value => value?.includes("wasteops_session=opaque-session-for-browser-test"))).toBe(true);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  expect(await page.evaluate(() => document.cookie)).not.toContain("wasteops_session");
  await expect(page.locator("#operatorUsersPanel")).toBeHidden();
  await expect(page.locator("#deviceAdminPanel")).toBeHidden();
  await expect(page.locator("#driverAdminPanel")).toBeHidden();
  await expect(page.locator("#passwordPanel")).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Connect & load bins" }).click();
  await expect(page.getByRole("status")).toContainText(/Loaded 0 bins from API/i);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("status")).toContainText(/Signed out/i);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
});


test("administrator can provision and revoke operator accounts from the console", async ({ page }) => {
  let accounts = [{ id: "admin-1", username: "rootadmin", role: "admin", active: true }];
  page.on("dialog", dialog => dialog.accept());
  await page.route("**/api/v1/auth/login", async route => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        expires_at: "2026-11-08T12:00:00Z",
        user: { id: "admin-1", username: "rootadmin", role: "admin" },
      }),
      headers: { "Set-Cookie": "wasteops_session=admin-session; Path=/api/v1; HttpOnly; SameSite=Strict" },
    });
  });
  await page.route("**/api/v1/auth/me", async route => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "admin-1", username: "rootadmin", role: "admin" }) });
  });
  await page.route("**/api/v1/auth/users", async route => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      accounts.push({ id: "operator-1", username: body.username, role: body.role, active: true });
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: "operator-1", username: body.username, role: body.role, active: true }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(accounts) });
  });
  await page.route("**/api/v1/auth/users/field.operator/revoke", async route => {
    accounts = accounts.map(user => user.username === "field.operator" ? { ...user, active: false } : user);
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ username: "field.operator", active: false, sessions_revoked: true }) });
  });
  await page.route("**/api/v1/auth/change-password", async route => {
    expect(route.request().postDataJSON()).toEqual({ current_password: "old-password-123", new_password: "new-password-12345" });
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ password_changed: true, other_sessions_revoked: true }) });
  });
  await page.route("**/api/v1/bins", async route => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.route("**/api/v1/jobs**", async route => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.route("**/api/v1/vehicles", async route => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));

  await page.goto("/");
  await page.getByLabel("Operator username").fill("rootadmin");
  await page.getByLabel("Password", { exact: true }).fill("admin-password-123");
  await page.getByRole("button", { name: "Connect & load bins" }).click();
  await expect(page.locator("#operatorUsersPanel")).toBeVisible();
  await expect(page.locator("#deviceAdminPanel")).toBeVisible();
  await expect(page.locator("#driverAdminPanel")).toBeVisible();
  await expect(page.locator("#operatorUsers")).toContainText("rootadmin");
  await page.getByLabel("Username", { exact: true }).fill("field.operator");
  await page.getByLabel("Temporary password (12+ characters)").fill("field-operator-password");
  await page.getByLabel("Role").selectOption("operator");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.locator("#operatorUsers")).toContainText("field.operator");
  const operatorRow = page.locator("#operatorUsers .job").filter({ hasText: "field.operator" });
  await operatorRow.getByRole("button", { name: "Revoke" }).click();
  await expect(page.locator("#operatorUsers")).toContainText("field.operator · operator · disabled");
  await page.getByLabel("Current password").fill("old-password-123");
  await page.getByLabel("New password (12+ characters)").fill("new-password-12345");
  await page.getByRole("button", { name: "Update password" }).click();
  await expect(page.locator("#passwordResult")).toContainText(/Password changed/i);
});
