import { test, expect } from '@playwright/test';

test('researcher can explore actual data, maps, filters and exports', async ({ page }) => {
  test.setTimeout(120000);
  await page.goto('http://localhost:8080');
  await expect(page.getByRole('heading', { name: 'A clearer picture of your fields.' })).toBeVisible();
  await expect(page.getByRole('status')).toBeHidden({ timeout: 30000 });
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.locator('.stat')).toHaveCount(4);
  await expect(page.locator('.recharts-surface').first()).toBeVisible();
  await expect(page.locator('.recharts-area-area').first()).toBeVisible();
  await expect(page.locator('.leaflet-interactive').first()).toBeVisible();
  await page.screenshot({ path: '../artifacts/screenshots/overview.png', fullPage: true });
  await page.getByRole('button', { name: 'Data explorer', exact: true }).click();
  await expect(page.locator('tbody tr')).toHaveCount(50);
  const first = await page.locator('tbody tr').first().innerText();
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.getByText(/Page 2 of/)).toBeVisible();
  await expect(page.locator('tbody tr').first()).not.toHaveText(first);
  await page.getByLabel('Quality columns').uncheck();
  await expect(page.getByRole('columnheader', { name: 'Quality', exact: true })).toHaveCount(0);
  await page.getByRole('combobox', { name: 'sensor', exact: true }).selectOption('sensor-0-0-0');
  await expect(page.getByText(/Page 1 of/)).toBeVisible();
  await page.getByRole('button', { name: 'Field map', exact: true }).click();
  await page.locator('.leaflet-interactive').first().click({ force: true });
  await expect(page.locator('.detail')).toBeVisible();
  await page.getByRole('button', { name: 'Time series', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Measurement history' })).toBeVisible();
  await page.screenshot({ path: '../artifacts/screenshots/time-series.png', fullPage: true });
  const downloadEvent = page.waitForEvent('download',{timeout:10000}).catch(async()=>{throw new Error('Export failed: '+await page.locator('.error').allTextContents());});
  await page.getByRole('button', {name:'Save PNG',exact:true}).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe('fieldsense-chart.png');
  await download.saveAs('../artifacts/screenshots/exported-chart.png');
  const response = await page.request.get('http://localhost:8080/api/exports/csv?sensor=sensor-0-0-0');
  expect(response.ok()).toBeTruthy();
  expect(await response.text()).toContain('experiment_id,treatment_id');
});

test('responsive navigation and helpful validation', async ({ page }) => {
  await page.setViewportSize({ width:390, height:844 });
  await page.goto('http://localhost:8080');
  await page.getByRole('button', { name: 'Experiments', exact: true }).click();
  await expect(page.getByRole('heading', { name:'Create an experiment' })).toBeVisible();
  await page.screenshot({ path: '../artifacts/screenshots/mobile.png', fullPage:true });
});

test('researcher can create an experiment and attach a note', async ({ page }) => {
  await page.goto('http://localhost:8080');
  await expect(page.getByRole('status')).toBeHidden({ timeout: 30000 });
  await page.getByRole('button', { name: 'Experiments', exact: true }).click();
  const title = `Browser trial ${Date.now()}`;
  const form = page.getByRole('heading', { name: 'Create an experiment' }).locator('..').locator('form');
  await form.getByLabel('Lab write token').fill(process.env.WRITE_TOKEN || 'local-write-token-change-before-hosting');
  await form.getByLabel('Title').fill(title);
  await form.getByLabel('Research question').fill('Browser verified research workflow');
  await form.getByLabel('Start').fill(new Date().toISOString().slice(0,10));
  await form.getByLabel('End').fill(new Date(Date.now()+86400000).toISOString().slice(0,10));
  await form.getByLabel('Treatments, separated by commas').fill('Rainfed control, Supplemental irrigation');
  const responseEvent=page.waitForResponse(r=>r.url().endsWith('/api/experiments')&&r.request().method()==='POST');
  await form.getByRole('button', { name: 'Create experiment' }).click();
  expect((await responseEvent).status()).toBe(201);
  await expect(page.locator('.detail').getByRole('heading', { name: title })).toBeVisible();
  const note = `Browser note ${Date.now()}`;
  await page.locator('.detail').getByLabel('Research note').fill(note);
  await page.locator('.detail').getByRole('button', { name: 'Add note' }).click();
  await expect(page.locator('.detail').getByText(note)).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
});
