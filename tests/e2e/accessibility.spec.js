const { test, expect } = require("@playwright/test");

for (const [path, titlePattern] of [
  ["/", /WasteOps \\| Collection Control/],
  ["/driver.html", /WasteOps \\| Driver/],
]) {
  test(`mobile layout and form labels are usable on ${path}`, async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto(path);
    await expect(page).toHaveTitle(titlePattern);

    // Every form control must have a visible, programmatically associated label.
    const controls = page.locator("input, select, textarea");
    const count = await controls.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i += 1) {
      const control = controls.nth(i);
      const id = await control.getAttribute("id");
      expect(id, "form controls need stable IDs").toBeTruthy();
      await expect(page.locator(`label[for="${id}"]`)).toHaveCount(1);
      await expect(page.locator(`label[for="${id}"]`)).toBeVisible();
    }

    // Catch accidental fixed-width layouts that force sideways scrolling on phones.
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      page: document.documentElement.scrollWidth,
    }));
    expect(dimensions.page).toBeLessThanOrEqual(dimensions.viewport + 1);
  });
}

test("operator and driver forms expose status updates to assistive technology", async ({ page }) => {
  for (const path of ["/", "/driver.html"]) {
    await page.goto(path);
    await expect(page.locator("#status")).toHaveAttribute("role", "status");
    await expect(page.locator("#status")).toHaveAttribute("aria-live", "polite");
  }
});

test("keyboard focus remains visible on the operator connection form", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  const focus = page.locator(":focus");
  await expect(focus).toBeVisible();
  const outlineStyle = await focus.evaluate(el => getComputedStyle(el).outlineStyle);
  expect(outlineStyle).not.toBe("none");
});
