import { test, expect } from '@playwright/test';

const password = 'Integration-test-password!';
const backend = process.env.BACKEND_TEST_URL;
test.skip(!backend, 'Run through backend/tests/test_frontend_browser.py for an isolated PostgreSQL schema.');

test.beforeEach(async ({ page }) => {
    // Exercise map interactions without sending automated tile traffic to OSM.
    await page.route('https://tile.openstreetmap.org/**', route => route.fulfill({
        contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aP1sAAAAASUVORK5CYII=', 'base64'),
    }));
});

async function register(page, role, name, email) {
    await page.goto('/register');
    await page.locator('input[name=role][value=' + role + ']').check();
    await page.getByLabel('Name', { exact: true }).fill(name);
    await page.getByLabel('Email address', { exact: true }).fill(email);
    await page.getByLabel('Town', { exact: true }).selectOption('Colombo');
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByLabel('Confirm password', { exact: true }).fill(password);
    await page.getByRole('button', { name: 'Create account', exact: true }).click({ noWaitAfter: true });
    await expect(page).toHaveURL(new RegExp('/' + role + '/'), { timeout: 60000 });
}

async function logout(page) {
    await page.goto('/settings');
    await page.getByRole('button', { name: 'Log out', exact: true }).click();
    await expect(page).toHaveURL(/\/$/);
}

async function login(page, email, loginPassword = password) {
    await page.goto('/login');
    await page.getByLabel('Email address').fill(email);
    await page.getByLabel('Password', { exact: true }).fill(loginPassword);
    await page.getByRole('button', { name: 'Log in', exact: true }).click({ noWaitAfter: true });
    await expect(page).toHaveURL(/\/(customer|worker|admin)\/dashboard/, { timeout: 60000 });
}

async function checkWorkspaceLayout(page, name) {
    for (const width of [1440, 1024, 768, 390, 360]) {
        await page.setViewportSize({ width, height: 1000 });
        await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
        await expect(page.locator('h1').first()).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), name + ' overflow at ' + width).toBe(true);
        if ([1440, 390].includes(width)) {
            await page.screenshot({ path: test.info().outputPath(name + '-' + width + '.png'), fullPage: true });
        }
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
}

test('real registration, worker profile, request, booking, completion and review', async ({ page, request }) => {
    test.setTimeout(600000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const unique = Date.now();
    const workerEmail = 'worker-' + unique + '@example.com';
    const customerEmail = 'customer-' + unique + '@example.com';
    const workerName = 'Browser Plumber ' + unique;
    await register(page, 'worker', workerName, workerEmail);
    await expect(page).toHaveURL(/\/worker\/profile/);
    await expect(page.getByRole('button', { name: 'Use map centre', exact: true })).toBeVisible();
    await page.getByLabel('About your work').fill('Careful household tap and pipe repairs in Colombo.');
    await page.getByLabel('Plumbing', { exact: true }).check();
    await page.getByLabel('Towns you serve').fill('Colombo');
    await page.getByLabel('Towns you serve').press('Enter');
    await page.getByLabel('Years of experience').fill('5');
    await page.getByLabel('Service rate').fill('2500');
    await page.getByRole('switch', { name: 'Available for new jobs' }).click();
    await expect(page.getByRole('region', { name: 'Location map' })).toBeVisible();
    await page.getByRole('button', { name: 'Use map centre', exact: true }).click();
    await expect(page.getByLabel('Latitude', { exact: true })).not.toHaveValue('');
    await page.getByRole('button', { name: 'Clear location', exact: true }).click();
    await page.getByLabel('Latitude', { exact: true }).fill('6.9271');
    await page.getByLabel('Longitude', { exact: true }).fill('79.8612');
    await page.getByLabel('Service radius (km)', { exact: true }).fill('15');
    await page.getByRole('button', { name: 'Save profile', exact: true }).click();
    await expect(page.getByText('Your profile has been updated.').first()).toBeVisible();
    await page.reload();
    await expect(page.getByLabel('Service rate')).toHaveValue('2500');
    await expect(page.getByLabel('Latitude', { exact: true })).toHaveValue('6.9271');
    await expect(page.getByText('Request sent. Waiting for admin approval.')).toBeVisible();
    await checkWorkspaceLayout(page, 'worker-profile');
    await logout(page);

    await login(page, process.env.TEST_ADMIN_EMAIL, process.env.TEST_ADMIN_PASSWORD);
    await page.goto('/admin/records?entity=workers&pendingOnly=1');
    await page.getByLabel('Search records').fill(workerName);
    await page.locator('.fi-ta tbody tr').first().getByRole('button', { name: 'Details', exact: true }).click();
    await page.getByRole('button', { name: 'Change requests', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Changes awaiting review' })).toBeVisible();
    await page.getByRole('button', { name: 'Review changes', exact: true }).click();
    const approval = page.getByRole('alertdialog');
    await approval.getByLabel('Decision', { exact: false }).selectOption('approve');
    await approval.getByLabel('Feedback for worker').fill('Profile and service area checked for this test.');
    await approval.getByRole('button', { name: 'Save decision', exact: true }).click();
    await expect(approval).toHaveCount(0);
    await logout(page);

    await register(page, 'customer', 'Browser Customer ' + unique, customerEmail);
    await page.goto('/customer/requests/new');
    await expect(page.getByRole('button', { name: 'Use map centre', exact: true })).toBeVisible();
    await page.getByLabel('Give your request a title').fill('Repair the browser test kitchen tap');
    await page.getByLabel('Tell us about the job').fill('The kitchen tap leaks continuously even when it is closed.');
    const future = new Date(Date.now() + 4 * 86400000);
    const appointment = future.toISOString().slice(0, 10) + 'T10:00';
    await page.getByLabel('Preferred date and time').fill(appointment);
    await page.route('**/locations/search', route => route.fulfill({ json: { data: [{ label: 'Colombo test landmark', latitude: 6.93, longitude: 79.86 }] } }));
    await page.getByLabel('Search address or place in Sri Lanka').fill('Colombo test landmark');
    await page.getByRole('button', { name: 'Search address', exact: true }).click();
    await page.getByRole('button', { name: 'Colombo test landmark', exact: true }).click();
    await expect(page.getByLabel('Latitude', { exact: true })).toHaveValue('6.93');
    await page.getByRole('button', { name: 'Save and continue', exact: true }).click();
    await expect(page).toHaveURL(/\/customer\/requests\/[a-f0-9-]+$/);
    const requestId = new URL(page.url()).pathname.split('/').at(-1);
    await page.getByRole('link', { name: 'Find suitable workers' }).click();
    await expect(page).toHaveURL(/\/recommendations/);
    await page.getByRole('combobox', { name: 'Service category', exact: true }).selectOption('Plumbing');
    const card = page.locator('.ss-recommendation').filter({ hasText: workerName });
    await expect(card).toBeVisible();
    await expect(card).toContainText('Not available yet');
    await card.getByRole('checkbox', { name: 'Compare' }).check();
    await expect(page.locator('.ss-comparison')).toBeVisible();
    await checkWorkspaceLayout(page, 'customer-recommendations');
    await card.getByRole('button', { name: 'Choose professional' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Expected end time', { exact: false }).fill(appointment.replace('T10:00', 'T12:00'));
    await expect(dialog.getByLabel('Completion deadline', { exact: true })).toHaveCount(0);
    await dialog.getByRole('checkbox', { name: 'I understand the rate basis and want to request this booking.' }).check();
    await dialog.getByRole('button', { name: 'Confirm booking', exact: true }).click();
    await expect(page).toHaveURL(/\/customer\/bookings\/[a-f0-9-]+$/);
    const bookingId = new URL(page.url()).pathname.split('/').at(-1);
    await expect(page.locator('.ss-status-pending').first()).toBeVisible();
    await logout(page);

    await login(page, workerEmail);
    expect((await page.goto('/customer/dashboard')).status()).toBe(403);
    await page.goto('/worker/jobs/' + bookingId);
    for (const label of ['Accept job', 'Start job', 'Request completion confirmation']) {
        await page.getByRole('button', { name: label, exact: true }).click();
        const confirmation = page.getByRole('alertdialog');
        await confirmation.getByRole('button', { name: 'Confirm', exact: true }).click();
        await expect(confirmation).toHaveCount(0);
    }
    await expect(page.locator('.ss-status-awaiting-confirmation').first()).toBeVisible();
    await logout(page);
    await login(page, customerEmail);
    await page.goto('/customer/bookings/' + bookingId);
    await expect(page.getByRole('button', { name: 'Leave a review', exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Confirm completed', exact: true }).click();
    await page.getByRole('alertdialog').getByRole('button', { name: 'Confirm', exact: true }).click();
    await expect(page.getByRole('alertdialog')).toHaveCount(0);
    await page.getByRole('button', { name: 'Leave a review', exact: true }).click();
    const review = page.getByRole('dialog');
    await review.getByLabel('Rating').selectOption('5');
    await review.getByLabel('Your review').fill('Careful repairs and clear communication throughout the job.');
    await review.getByRole('button', { name: 'Submit', exact: true }).click();
    await expect(review).toHaveCount(0);
    await page.reload();
    await expect(page.getByText('Careful repairs and clear communication throughout the job.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Leave a review', exact: true })).toHaveCount(0);
    await checkWorkspaceLayout(page, 'completed-booking');
    await page.getByRole('button', { name: 'Submit complaint', exact: true }).click();
    const complaintDialog = page.getByRole('dialog');
    await complaintDialog.getByLabel('Describe the issue and supporting details').fill('A follow-up leak needs to be investigated by the administrator.');
    await complaintDialog.getByRole('button', { name: 'Submit', exact: true }).click();
    await expect(complaintDialog).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'Complaint: Pending' })).toBeVisible();
    await page.goto('/notifications');
    await expect(page.locator('h1')).toBeVisible();

    const response = await request.post(backend + '/api/v1/auth/login', { data: { email: customerEmail, password } });
    expect(response.ok()).toBeTruthy();
    const token = (await response.json()).data.accessToken;
    const saved = await request.get(backend + '/api/v1/bookings/' + bookingId, { headers: { Authorization: 'Bearer ' + token } });
    const record = (await saved.json()).data;
    expect(record.status).toBe('completed');
    expect(record.review.rating).toBe(5);
    expect(record.requestId).toBe(requestId);
    // The form's 10:00 Colombo appointment must arrive as 04:30 UTC.
    expect(record.scheduledAt.slice(11, 16)).toBe('04:30');
    expect(record.scheduledEndAt.slice(11, 16)).toBe('06:30');
    expect(record.deadlineAt).toBe(record.scheduledEndAt);
    expect(record.request.latitude).toBe(6.93);
    await logout(page);
    await login(page, workerEmail);
    await page.goto('/worker/performance');
    await expect(page.getByText('1 completed job', {exact: true}).first()).toBeVisible();
    await logout(page);
    await login(page, process.env.TEST_ADMIN_EMAIL, process.env.TEST_ADMIN_PASSWORD);
    await page.goto('/admin/records?entity=complaints&recordId=' + record.complaint.id);
    await page.getByRole('button', { name: 'Review complaint', exact: true }).click();
    const resolution = page.getByRole('dialog');
    await resolution.getByLabel('Status', { exact: false }).selectOption('upheld');
    await resolution.getByLabel('Evidence reviewed and reason for decision').fill('Both participants confirmed that the follow-up leak remains unresolved.');
    await resolution.getByRole('button', { name: 'Submit', exact: true }).click();
    await expect(resolution).toHaveCount(0);
    const resolved = await request.get(backend + '/api/v1/bookings/' + bookingId, { headers: { Authorization: 'Bearer ' + token } });
    expect((await resolved.json()).data.complaint.status).toBe('upheld');
    expect(errors).toEqual([]);
});

test('public API data fits desktop and phone without demo content', async ({ page, request }) => {
    const workers = await request.get(backend + '/api/v1/workers');
    const records = (await workers.json()).data;
    const paths = ['/', '/services', '/workers', '/about', '/login', '/register'];
    if (records.length) paths.push('/workers/' + records[0].id);
    for (const width of [1440, 1024, 768, 390, 360]) {
        await page.setViewportSize({ width, height: 1000 });
        for (const path of paths) {
            expect((await page.goto(path)).status()).toBe(200);
            await expect(page.locator('h1').first()).toBeVisible();
            await expect(page.getByText('Demo mode', { exact: true })).toHaveCount(0);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), path + ' overflow').toBe(true);
            if (path === '/' && [1440, 390].includes(width)) {
                await page.screenshot({ path: test.info().outputPath('home-' + width + '.png'), fullPage: true });
            }
        }
    }
});

test('administrator inspects API records and records verification with a note', async ({ page, request }) => {
    await login(page, process.env.TEST_ADMIN_EMAIL, process.env.TEST_ADMIN_PASSWORD);
    await page.goto('/admin/records?entity=workers');
    const workerResponse = await request.get(backend + '/api/v1/workers');
    const worker = (await workerResponse.json()).data[0];
    expect(worker).toBeTruthy();
    await page.getByLabel('Search records').fill(worker.name);
    await page.locator('.fi-ta tbody tr').first().getByRole('button', { name: 'Details', exact: true }).click();
    await expect(page.locator('.fi-ta tbody')).toHaveCount(0);
    await expect(page.getByRole('button', {name: 'Back to records'})).toBeVisible();
    await checkWorkspaceLayout(page, 'admin-worker-details');
    await page.getByRole('button', { name: 'Review application', exact: true }).click();
    const dialog = page.getByRole('alertdialog');
    await dialog.getByLabel('Decision', { exact: false }).selectOption('approve');
    await dialog.getByLabel('Feedback for worker').fill('Profile checked during isolated integration testing.');
    await dialog.getByRole('button', { name: 'Save decision', exact: true }).click();
    await expect(dialog).toHaveCount(0);
    const verified = await request.get(backend + '/api/v1/workers/' + worker.id);
    expect((await verified.json()).data.verified).toBe(true);
    await page.goto('/admin/records?entity=categories');
    await page.locator('.fi-ta tbody tr').filter({ hasText: 'Plumbing' }).getByRole('button', { name: 'Details', exact: true }).click();
    await page.getByRole('button', { name: 'Edit description', exact: true }).click();
    const categoryDialog = page.getByRole('dialog');
    await categoryDialog.getByLabel('Description', { exact: false }).fill('Plumbing repairs updated through the integrated admin panel.');
    await categoryDialog.getByRole('button', { name: 'Submit', exact: true }).click();
    await expect(categoryDialog).toHaveCount(0);
    await page.reload();
    await expect(page.getByText('Plumbing repairs updated through the integrated admin panel.').first()).toBeVisible();
});


test('worker photo upload replacement and removal', async ({ page, request }) => {
    const email = 'photo-' + Date.now() + '@example.com';
    const registration = await request.post(backend + '/api/v1/auth/register', { data: {
        name: 'Photo Test Worker', email, password, role: 'worker', town: 'Colombo',
    }});
    expect(registration.ok()).toBeTruthy();
    const identity = (await registration.json()).data;
    const headers = { Authorization: 'Bearer ' + identity.accessToken };
    expect((await request.patch(backend + '/api/v1/worker/profile', { headers, data: {
        bio: 'Careful household plumbing services.', categories: ['Plumbing'], serviceTowns: ['Colombo'],
        rateLkr: 2500, rateUnit: 'visit', yearsExperience: 5, available: true,
    }})).ok()).toBeTruthy();
    const admin = await request.post(backend + '/api/v1/auth/login', { data: {
        email: process.env.TEST_ADMIN_EMAIL, password: process.env.TEST_ADMIN_PASSWORD,
    }});
    const adminToken = (await admin.json()).data.accessToken;
    expect((await request.patch(backend + '/api/v1/admin/workers/' + identity.user.workerId + '/verification', {
        headers: { Authorization: 'Bearer ' + adminToken }, data: { verified: true, note: 'Profile checked for isolated photo testing.' },
    })).ok()).toBeTruthy();
    await login(page, email);
    await page.goto('/worker/profile');
    await expect(page.getByRole('button', { name: 'Save photo', exact: true })).toBeDisabled();
    const image = { name: 'portrait.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAGQAAABQCAIAAABga0e4AAAAvklEQVR4nO3SsREAIAwDscDkjM4K+V6qXf35zLxh5y53iNV4ViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViDW7H3OBAEg1VOHKQAAAABJRU5ErkJggg==', 'base64') };
    await expect(page.getByLabel('Choose a photo', { exact: true })).toBeEnabled();
    await page.getByLabel('Choose a photo', { exact: true }).setInputFiles(image);
    await expect(page.getByRole('img', { name: 'Square photo crop preview' })).toBeVisible();
    await page.getByLabel('Zoom', { exact: true }).fill('1.5');
    await page.getByLabel('Vertical position', { exact: true }).fill('35');
    await checkWorkspaceLayout(page, 'worker-photo-crop');
    await page.getByRole('button', { name: 'Reset crop', exact: true }).click();
    await expect(page.getByLabel('Zoom', { exact: true })).toHaveValue('1');
    await page.getByRole('button', { name: 'Cancel selection', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Save photo', exact: true })).toBeDisabled();
    await expect(page.getByLabel('Choose a photo', { exact: true })).toBeEnabled();
    await page.getByLabel('Choose a photo', { exact: true }).setInputFiles(image);
    await expect(page.getByRole('img', { name: 'Square photo crop preview' })).toBeVisible();
    await page.getByRole('button', { name: 'Save photo', exact: true }).click();
    const saved = page.locator('.ss-photo-editor .ss-worker-avatar-photo');
    await expect(saved).toBeVisible();
    await expect.poll(() => saved.evaluate(el => el.complete && el.naturalWidth === 512 && el.naturalHeight === 512)).toBe(true);
    const firstUrl = await saved.getAttribute('src');
    await page.reload();
    await expect(saved).toHaveAttribute('src', firstUrl);
    await checkWorkspaceLayout(page, 'worker-photo');
    await page.goto('/');
    await expect(page.locator('.ss-match-person .ss-worker-avatar-photo')).toHaveAttribute('src', firstUrl);
    await expect(page.locator('.ss-worker-grid .ss-worker-avatar-photo')).toHaveAttribute('src', firstUrl);
    await page.goto('/workers');
    await expect(page.locator('.ss-worker-grid .ss-worker-avatar-photo')).toHaveAttribute('src', firstUrl);
    await page.goto('/workers/' + identity.user.workerId);
    await expect(page.locator('.ss-profile-header .ss-worker-avatar-photo')).toHaveAttribute('src', firstUrl);
    await page.goto('/worker/profile');
    await expect(page.getByLabel('Choose a photo', { exact: true })).toBeEnabled();
    await page.getByLabel('Choose a photo', { exact: true }).setInputFiles(image);
    await expect(page.getByRole('img', { name: 'Square photo crop preview' })).toBeVisible();
    await page.getByRole('button', { name: 'Save photo', exact: true }).click();
    await expect(saved).not.toHaveAttribute('src', firstUrl);
    expect((await request.get(backend + firstUrl)).status()).toBe(404);
    await page.getByRole('button', { name: 'Remove photo', exact: true }).click();
    const dialog = page.getByRole('alertdialog');
    await expect(dialog.getByRole('heading', { name: 'Remove your profile photo?' })).toBeVisible();
    await dialog.getByRole('button', { name: 'Confirm', exact: true }).click();
    await expect(saved).toHaveCount(0);
    await expect(page.locator('.ss-photo-editor .ss-worker-avatar')).toContainText('PT');
});
