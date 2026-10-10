import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { createRequire } from "node:module";

const require = createRequire(new URL("../uis/backoffice/package.json", import.meta.url));
const { chromium } = require("@playwright/test");
const frontend = process.env.TELEMETRY_TEST_FRONTEND ?? "http://127.0.0.1:3001";
const backend = process.env.TELEMETRY_TEST_BACKEND ?? "http://127.0.0.1:8000";
const browser = await chromium.launch();
const context = await browser.newContext();
const page = await context.newPage();
const batches = [];
const responses = [];
const devtools = await context.newCDPSession(page);
await devtools.send("Network.enable");
let devtoolsBatches = 0;
devtools.on("Network.requestWillBeSent", ({ request }) => {
  if (request.url.endsWith("/telemetry/events") && request.method === "POST") devtoolsBatches += 1;
});
page.on("request", (request) => {
  if (request.url().endsWith("/telemetry/events") && request.method() === "POST") batches.push(JSON.parse(request.postData()));
});
page.on("response", (response) => {
  if (response.url().endsWith("/telemetry/events")) responses.push(response.status());
});
const email = `telemetry-${randomUUID()}@example.com`;
const password = `Test.${randomUUID()}!`;
const vendor = `vendor-canary-${randomUUID()}`;
const sku = `tel-${randomUUID().slice(0, 8)}`;

try {
  const registered = await context.request.post(`${backend}/users`, { data: { email, password } });
  assert.equal(registered.status(), 201);
  const signedIn = await context.request.post(`${backend}/auth/login`, { data: { email, password } });
  const { access_token: token } = await signedIn.json();
  const headers = { Authorization: `Bearer ${token}` };
  const product = await context.request.post(`${backend}/inventory/products`, { headers, data: {
    name: `Telemetry ${sku}`, sku, category: "ppe", unit: "box", country: "US",
  } });
  assert.equal(product.status(), 201);
  const { id: productId } = await product.json();

  await page.goto(`${frontend}/login`);
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.locator('input[type="password"]').fill("Invalid.Test.Password!");
  await page.getByRole("button", { name: "Iniciar sesión", exact: true }).click();
  await page.getByText("No se pudo iniciar sesión. Comprueba tus credenciales.").waitFor();
  await page.locator('input[type="password"]').fill(password);
  await page.getByRole("button", { name: "Iniciar sesión", exact: true }).click();
  await page.waitForURL(`${frontend}/`);
  await page.goto(`${frontend}/inventory/products`);
  await page.getByLabel("Suministro de política").selectOption(String(productId));
  await page.getByLabel("Mínimo de unidades").fill("5");
  const expiry = new Date(Date.now() + 10 * 86400000).toISOString().slice(0, 10);
  await page.getByLabel("Caducidad del suministro").fill(expiry);
  await page.getByRole("button", { name: "Guardar política" }).click();
  await page.getByText("Política de inventario guardada.").waitFor();

  await page.goto(`${frontend}/inventory/orders/inbound`);
  await page.locator("#supply").selectOption(String(productId));
  await page.locator("#clinic").selectOption("1");
  await page.locator("#quantity").fill("10");
  await page.locator('form input[type="text"]').fill(vendor);
  await page.getByRole("button", { name: "Registrar entrada", exact: true }).click();
  await page.getByText(/Entrada registrada correctamente/).waitFor();

  await page.goto(`${frontend}/inventory/orders/outbound`);
  await page.locator("#supply").selectOption(String(productId));
  await page.locator("#clinic").selectOption("1");
  await page.locator("#quantity").fill("6");
  await page.locator("#consumptionType").selectOption("clinical_use");
  await page.locator("#department").selectOption("primary_care");
  await page.getByRole("button", { name: "Registrar salida", exact: true }).click();
  await page.getByText(/Salida registrada correctamente/).waitFor();

  const direct = await context.request.patch(`${backend}/inventory/products/${productId}/stock`, {
    headers, data: { clinic_id: 1, quantity: 4 },
  });
  assert.equal(direct.status(), 403);
  await page.evaluate(() => {
    setTimeout(() => { throw new Error("frontend-error-canary"); }, 0);
    Promise.reject(new Error("rejection-canary"));
  });
  const containsAll = () => {
    const types = new Set(batches.flatMap((batch) => batch.events.map((event) => event.event_type)));
    return ["auth_login_failed", "auth_login_succeeded", "backoffice_page_viewed", "frontend_error_captured", "client_performance_recorded"].every((name) => types.has(name));
  };
  const deadline = Date.now() + 60000;
  while (!containsAll() && Date.now() < deadline) await page.waitForResponse((response) => response.url().endsWith("/telemetry/events"), { timeout: 20000 });
  assert(containsAll(), "Missing frontend events; backend mandatory delivery is verified by test_telemetry_delivery.py");
  await page.goto(`${frontend}/suppliers`);
  await page.getByRole("heading", { name: /proveedores/i }).first().waitFor();
  await page.waitForResponse((response) => response.url().endsWith("/telemetry/events"), { timeout: 20000 });
  await page.screenshot({ path: "/tmp/healthcore-telemetry-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${frontend}/inventory/products`);
  await page.getByRole("heading", { name: "Política de inventario" }).waitFor();
  await page.screenshot({ path: "/tmp/healthcore-telemetry-mobile.png", fullPage: true });

  assert(batches.length > 0 && devtoolsBatches > 0);
  assert(responses.every((status) => status === 200));
  const serialized = JSON.stringify(batches);
  for (const sensitive of [email, password, vendor, "frontend-error-canary", "rejection-canary"]) assert(!serialized.includes(sensitive));
  for (const batch of batches) {
    assert(Array.isArray(batch.events) && batch.events.length <= 20);
    for (const event of batch.events) assert.deepEqual(Object.keys(event).sort(), ["eventId", "timestamp", "sessionId", "userId", "event_type", "schemaVersion", "requestId", "properties"].sort());
  }
  console.log(JSON.stringify({ scope: "frontend Network; server mandatory events require backend integration tests", batches: batches.length, devtoolsBatches, statuses: responses, events: [...new Set(batches.flatMap((batch) => batch.events.map((event) => event.event_type)))].sort(), privacyCanariesAbsent: true }, null, 2));
} finally {
  await browser.close();
}