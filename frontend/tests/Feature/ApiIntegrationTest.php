<?php

namespace Tests\Feature;

use App\Contracts\SkillSyncGateway;
use App\Filament\Customer\Pages\BookingDetails;
use App\Filament\Customer\Pages\NewRequest;
use App\Filament\Customer\Pages\RequestDetails;
use App\Filament\Worker\Pages\JobDetails;
use App\Livewire\Shared\NotificationBell;
use App\Livewire\Shared\Notifications;
use App\Models\User;
use App\Services\SkillSync\BackendClient;
use Filament\Facades\Filament;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Factory;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Http;
use Livewire\Livewire;
use Tests\TestCase;

class ApiIntegrationTest extends TestCase
{
    use RefreshDatabase;

    private string $role = 'customer';

    private string $requestStatus = 'submitted';

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
        config(['skillsync.fastapi_base_url' => 'http://backend.test']);
        Http::preventStrayRequests();
        $this->fakeApi();
    }

    private function identity(): array
    {
        return ['id' => '11111111-1111-4111-8111-111111111111', 'name' => 'API Account',
            'email' => 'account@example.com', 'role' => $this->role, 'town' => 'Colombo',
            'workerId' => $this->role === 'worker' ? '22222222-2222-4222-8222-222222222222' : null,
            'phone' => '0771234567', 'contactPreference' => 'phone'];
    }

    private function worker(): array
    {
        return ['id' => '22222222-2222-4222-8222-222222222222', 'name' => 'API Professional',
            'town' => 'Colombo', 'serviceTowns' => ['Colombo'], 'categories' => ['Plumbing'],
            'bio' => 'Careful household plumbing repairs.', 'yearsExperience' => 5,
            'rateLkr' => 2500, 'rateUnit' => 'visit', 'available' => true,
            'rating' => null, 'reviewCount' => 0, 'verified' => false, 'reviews' => [],
            'reliabilityProbability' => null,
            'performance' => [['category' => 'Plumbing', 'completedJobs' => 0, 'skillScore' => null]]];
    }

    private function job(): array
    {
        return ['id' => '33333333-3333-4333-8333-333333333333',
            'customerId' => $this->identity()['id'], 'title' => 'API kitchen tap repair',
            'description' => 'The kitchen tap leaks and needs a repair.', 'town' => 'Colombo',
            'address' => null, 'preferredAt' => now()->addDays(2)->toIso8601String(),
            'budgetLkr' => null, 'category' => null, 'status' => $this->requestStatus,
            'createdAt' => now()->toIso8601String()];
    }

    private function page(array $data): array
    {
        return ['data' => $data, 'meta' => ['page' => 1, 'perPage' => 100, 'total' => count($data), 'lastPage' => 1]];
    }

    private function stub(array|callable $callback): void
    {
        Http::swap(new Factory);
        Http::preventStrayRequests();
        Http::fake($callback);
    }

    private function fakeApi(): void
    {
        $this->stub(function (Request $request) {
            $path = parse_url($request->url(), PHP_URL_PATH);
            $identity = $this->identity();
            $worker = $this->worker();
            $job = $this->job();
            $category = ['id' => 'cat08', 'label' => 'Plumbing', 'slug' => 'plumbing',
                'icon' => 'heroicon-o-wrench-screwdriver', 'description' => 'Household plumbing repairs.',
                'exampleRequest' => 'Please repair my leaking kitchen tap.'];
            if (in_array($path, ['/api/v1/auth/login', '/api/v1/auth/register'])) {
                return Http::response(['data' => ['accessToken' => 'secret-api-token', 'tokenType' => 'bearer',
                    'expiresAt' => now()->addHours(8)->toIso8601String(), 'user' => $identity]], $path === '/api/v1/auth/register' ? 201 : 200);
            }
            $result = match ($path) {
                '/api/v1/auth/logout' => ['data' => ['message' => 'Signed out.']],
                '/api/v1/me' => ['data' => $identity],
                '/api/v1/categories' => ['data' => [$category]],
                '/api/v1/workers' => $this->page([$worker]),
                '/api/v1/workers/'.$worker['id'], '/api/v1/worker/profile' => ['data' => $worker],
                '/api/v1/worker/performance' => ['data' => ['performance' => $worker['performance'], 'completedJobs' => 0,
                    'rating' => null, 'reviewCount' => 0, 'reliabilityProbability' => null, 'modelStatus' => 'not_configured']],
                '/api/v1/requests' => $request->method() === 'POST' ? ['data' => $job] : $this->page([$job]),
                '/api/v1/requests/'.$job['id'] => ['data' => $job],
                '/api/v1/requests/'.$job['id'].'/recommendations' => ['data' => ['requestId' => $job['id'], 'category' => 'Plumbing', 'source' => 'rule_based',
                    'recommendations' => [['workerId' => $worker['id'], 'rank' => 1, 'matchScore' => null,
                        'categorySkillScore' => null, 'reliabilityProbability' => null, 'source' => 'rule_based',
                        'worker' => $worker, 'reasons' => ['Offers Plumbing in Colombo.']]]]],
                '/api/v1/bookings', '/api/v1/notifications' => $this->page([]),
                '/api/v1/dashboard' => ['data' => ['role' => $this->role, 'requests' => 145, 'bookings' => 120,
                    'bookingsByStatus' => ['pending' => 20, 'completed' => 100], 'unreadNotifications' => 0]],
                '/api/v1/admin/dashboard' => ['data' => ['counts' => ['workers' => 121, 'customers' => 135, 'categories' => 10,
                    'requests' => 145, 'bookings' => 120, 'reviews' => 90],
                    'models' => ['classification' => 'not_configured', 'recommendations' => 'rule_based', 'performance' => 'not_configured']]],
                '/api/v1/admin/workers' => $this->page([$worker]),
                '/api/v1/admin/customers' => $this->page([$identity]),
                '/api/v1/admin/categories' => $this->page([$category]),
                '/api/v1/admin/requests' => $this->page([$job]),
                '/api/v1/admin/bookings', '/api/v1/admin/reviews' => $this->page([]),
                default => null,
            };

            return $result === null
                ? Http::response(['error' => ['code' => 'not_found', 'message' => 'Not found.']], 404)
                : Http::response($result);
        });
    }

    private function login(string $role = 'customer'): User
    {
        $this->role = $role;
        $this->post('/login', ['email' => 'ACCOUNT@example.com', 'password' => 'PasswordForTest!'])
            ->assertRedirect('/'.$role.'/dashboard');

        return User::firstOrFail();
    }

    public function test_public_pages_display_api_records_without_demo_accounts_or_fixed_worker_ids(): void
    {
        foreach (['/', '/services', '/workers', '/about', '/login', '/register', '/workers/'.$this->worker()['id']] as $path) {
            $this->get($path)->assertOk()->assertDontSee('Demo mode')->assertDontSee('Arul Selvan');
        }
        $this->get('/')->assertSee('API Professional');
        $this->get('/workers/'.$this->worker()['id'])->assertSee('Not available yet');
        $this->get('/workers/missing')->assertNotFound();
        $this->post('/demo/login', ['role' => 'admin'])->assertStatus(405);
        $this->assertDatabaseCount('users', 0);
        Http::assertNotSent(fn (Request $request) => str_contains($request->url(), '/w01'));
    }

    public function test_login_encrypts_token_forwards_it_and_uses_backend_identity(): void
    {
        $user = $this->login();
        $this->assertAuthenticatedAs($user);
        $this->assertSame($this->identity()['id'], $user->backend_id);
        $this->assertNotSame('secret-api-token', session('backend_token'));
        $this->assertSame('secret-api-token', Crypt::decryptString(session('backend_token')));
        $this->get('/customer/dashboard')->assertOk()->assertDontSee('secret-api-token');
        $this->assertSame(145, app(SkillSyncGateway::class)->dashboard($user)['data']['requests']);
        Http::assertSent(fn (Request $request) => str_ends_with($request->url(), '/me') && $request->hasHeader('Authorization', 'Bearer secret-api-token'));
        Http::assertSent(fn (Request $request) => str_ends_with($request->url(), '/auth/login') && $request['email'] === 'account@example.com');
        $this->get('/worker/dashboard')->assertForbidden();
        $this->get('/admin/dashboard')->assertForbidden();
    }

    public function test_worker_registration_uses_api_accepts_normal_email_and_opens_profile(): void
    {
        $this->role = 'worker';
        $this->post('/register', ['name' => 'New Worker', 'email' => 'new@skillsync.test', 'role' => 'worker',
            'town' => 'Colombo', 'password' => 'PasswordForTest!', 'password_confirmation' => 'PasswordForTest!'])
            ->assertRedirect('/worker/profile');
        Http::assertSent(fn (Request $request) => str_ends_with($request->url(), '/auth/register')
            && $request['email'] === 'new@skillsync.test' && ! isset($request['password_confirmation']));
        $this->assertSame('worker', User::firstOrFail()->role);
    }

    public function test_public_registration_cannot_request_admin_role(): void
    {
        $this->post('/register', ['name' => 'Admin', 'email' => 'admin@example.com', 'role' => 'admin',
            'town' => 'Colombo', 'password' => 'PasswordForTest!', 'password_confirmation' => 'PasswordForTest!'])
            ->assertSessionHasErrors('role');
        Http::assertNothingSent();
        $this->assertGuest();
    }

    public function test_invalid_login_and_duplicate_registration_show_field_errors(): void
    {
        $this->stub(['*' => Http::response(['error' => ['message' => 'Invalid credentials.']], 401)]);
        $this->post('/login', ['email' => 'bad@example.com', 'password' => 'bad'])->assertSessionHasErrors('email');
        $this->assertGuest();
        $this->assertDatabaseCount('users', 0);
        $this->stub(['*' => Http::response(['error' => ['message' => 'An account already exists.']], 409)]);
        $this->post('/register', ['name' => 'Duplicate', 'email' => 'duplicate@example.com', 'role' => 'customer',
            'town' => 'Colombo', 'password' => 'PasswordForTest!', 'password_confirmation' => 'PasswordForTest!'])
            ->assertSessionHasErrors('email');
    }

    public function test_expired_token_clears_local_session_and_redirects_to_login(): void
    {
        $this->login();
        $this->stub(['*' => Http::response(['error' => ['message' => 'Expired.']], 401)]);
        $this->get('/customer/dashboard')->assertRedirect('/login');
        $this->assertGuest();
        $this->assertNull(session('backend_token'));
    }

    public function test_logout_revokes_token_and_clears_session(): void
    {
        $this->login();
        $this->post('/logout')->assertRedirect('/');
        Http::assertSent(fn (Request $request) => str_ends_with($request->url(), '/auth/logout')
            && $request->hasHeader('Authorization', 'Bearer secret-api-token'));
        $this->assertGuest();
        $this->assertNull(session('backend_token'));
    }

    public function test_panel_menu_logout_also_revokes_the_backend_token(): void
    {
        $this->login('worker');
        $this->post('/worker/logout')->assertRedirect('/');
        Http::assertSent(fn (Request $request) => str_ends_with($request->url(), '/auth/logout')
            && $request->hasHeader('Authorization', 'Bearer secret-api-token'));
        $this->assertGuest();
        $this->assertNull(session('backend_token'));
    }

    public function test_backend_failure_never_displays_fallback_profiles_and_logout_still_works(): void
    {
        $this->login();
        $this->stub(['*' => Http::failedConnection()]);
        $this->get('/customer/dashboard')->assertStatus(503);
        $this->post('/logout')->assertRedirect('/');
        $this->assertGuest();
        $this->get('/')->assertOk()->assertSee('temporarily unavailable')->assertDontSee('API Professional')->assertDontSee('Arul Selvan');
    }

    public function test_customer_pages_and_manual_category_flow_render(): void
    {
        $this->login();
        foreach (['/customer/requests/new', '/customer/requests/'.$this->job()['id'],
            '/customer/requests/'.$this->job()['id'].'/recommendations', '/customer/bookings',
            '/customer/profile', '/customer/notifications', '/customer/settings'] as $path) {
            $this->get($path)->assertOk();
        }
        Filament::setCurrentPanel(Filament::getPanel('customer'));
        Livewire::test(RequestDetails::class, ['requestId' => $this->job()['id']])
            ->call('findWorkers')->assertRedirect('/customer/requests/'.$this->job()['id'].'/recommendations');
        Http::assertNotSent(fn (Request $request) => str_ends_with($request->url(), '/classify'));
    }

    public function test_worker_pages_merge_contact_and_performance_details(): void
    {
        $user = $this->login('worker');
        foreach (['/worker/dashboard', '/worker/jobs', '/worker/profile', '/worker/performance', '/worker/notifications', '/worker/settings'] as $path) {
            $this->get($path)->assertOk();
        }
        $profile = app(SkillSyncGateway::class)->profile($user)['data'];
        $this->assertSame('0771234567', $profile['phone']);
        $this->assertSame('phone', $profile['contactPreference']);
        $this->assertSame('API Professional', $profile['name']);
        $this->get('/customer/dashboard')->assertForbidden();
    }

    public function test_admin_pages_use_backend_counts_and_roles(): void
    {
        $this->login('admin');
        $this->get('/admin/dashboard')->assertOk()->assertSee('121')->assertSee('135');
        foreach (['workers', 'customers', 'categories', 'requests', 'bookings', 'reviews'] as $entity) {
            $this->get('/admin/records?entity='.$entity)->assertOk();
        }
        $this->get('/customer/dashboard')->assertForbidden();
        $this->get('/worker/dashboard')->assertForbidden();
    }

    public function test_gateway_normalizes_filters_and_sends_only_allowed_fields(): void
    {
        $user = $this->login();
        app(SkillSyncGateway::class)->recommendations($user, $this->job()['id'], ['available' => true, 'maxRate' => '', 'demoState' => 'normal']);
        Http::assertSent(fn (Request $request) => str_ends_with($request->url(), '/recommendations')
            && $request->data() === ['available' => true, 'maxRate' => null]);
        app(SkillSyncGateway::class)->createRequest($user, ['title' => 'Repair leaking tap',
            'description' => 'Repair the leaking kitchen tap.', 'town' => 'Colombo',
            'preferredAt' => '2099-01-15 10:00:00', 'budgetLkr' => '', 'category' => '', 'role' => 'admin']);
        Http::assertSent(fn (Request $request) => $request->method() === 'POST' && str_ends_with($request->url(), '/requests')
            && $request['preferredAt'] === '2099-01-15T10:00:00+05:30' && $request['budgetLkr'] === null && ! isset($request['role']));
    }

    public function test_pagination_includes_records_after_first_page(): void
    {
        $this->login();
        $this->stub(function (Request $request) {
            $page = (int) $request['page'];

            return Http::response(['data' => [['id' => 'record-'.$page]], 'meta' => ['page' => $page, 'lastPage' => 3, 'total' => 3, 'perPage' => 1]]);
        });
        $result = app(BackendClient::class)->all('/bookings');
        $this->assertSame(['record-1', 'record-2', 'record-3'], array_column($result['data'], 'id'));
    }

    public function test_livewire_request_maps_backend_validation_errors_to_form_fields(): void
    {
        $this->login();
        Filament::setCurrentPanel(Filament::getPanel('customer'));
        $component = Livewire::test(NewRequest::class);
        $this->stub(function (Request $request) {
            if ($request->method() === 'POST') {
                return Http::response(['error' => ['message' => 'Please check your input.',
                    'fields' => ['preferredAt' => ['Choose a future appointment.']]]], 422);
            }

            return Http::response(['data' => str_ends_with($request->url(), '/me')
                ? $this->identity() : [['label' => 'Plumbing']]]);
        });
        $component->fillForm(['title' => 'Repair kitchen tap', 'description' => 'The kitchen tap keeps leaking.',
            'town' => 'Colombo', 'preferredAt' => now()->addDays(2)->format('Y-m-d H:i:s')])
            ->call('save')->assertHasFormErrors(['preferredAt']);
    }

    public function test_guest_cannot_open_role_workspaces(): void
    {
        foreach (['/customer/dashboard', '/worker/dashboard', '/admin/dashboard', '/settings', '/notifications'] as $path) {
            $this->get($path)->assertRedirect('/login');
        }
    }

    public function test_shared_account_pages_redirect_to_the_current_role_workspace(): void
    {
        foreach (['customer', 'worker', 'admin'] as $role) {
            $this->login($role);
            foreach (['settings', 'notifications'] as $page) {
                $this->get('/'.$page)->assertRedirect('/'.$role.'/'.$page);
                $this->get('/'.$role.'/'.$page)->assertOk();
            }
            $this->post('/logout');
        }
    }

    public function test_registration_confirmation_error_is_attached_to_confirmation_without_calling_api(): void
    {
        $this->post('/register', ['name' => 'New Customer', 'email' => 'new@example.com',
            'role' => 'customer', 'town' => 'Colombo', 'password' => 'PasswordForTest!',
            'password_confirmation' => 'DifferentPassword!'])
            ->assertSessionHasErrors('password_confirmation')->assertSessionDoesntHaveErrors('password');
        Http::assertNothingSent();
        $this->assertDatabaseCount('users', 0);
    }

    public function test_customer_can_edit_submitted_request_through_the_backend(): void
    {
        $this->login();
        Filament::setCurrentPanel(Filament::getPanel('customer'));
        Livewire::test(RequestDetails::class, ['requestId' => $this->job()['id']])
            ->callAction('edit', data: ['title' => 'Updated kitchen tap repair',
                'description' => 'Repair the tap and inspect the pipe below it.', 'town' => 'Colombo',
                'address' => 'Updated test address', 'preferredAt' => '2099-01-15 10:00:00',
                'budgetLkr' => 4000])
            ->assertHasNoActionErrors();
        Http::assertSent(fn (Request $request) => $request->method() === 'PATCH'
            && str_ends_with($request->url(), '/requests/'.$this->job()['id'])
            && $request['title'] === 'Updated kitchen tap repair'
            && $request['preferredAt'] === '2099-01-15T10:00:00+05:30'
            && ! array_key_exists('category', $request->data())
            && ($request['latitude'] ?? null) === null);
    }

    public function test_booked_and_closed_requests_cannot_open_the_edit_action(): void
    {
        $this->login();
        Filament::setCurrentPanel(Filament::getPanel('customer'));
        foreach (['booked', 'closed'] as $status) {
            $this->requestStatus = $status;
            Livewire::test(RequestDetails::class, ['requestId' => $this->job()['id']])
                ->assertActionHidden('edit')->mountAction('edit')->assertActionNotMounted('edit');
        }
        Http::assertNotSent(fn (Request $request) => $request->method() === 'PATCH');
    }

    public function test_request_edit_outage_keeps_the_dialog_open_and_shows_failure(): void
    {
        $this->login();
        Filament::setCurrentPanel(Filament::getPanel('customer'));
        $component = Livewire::test(RequestDetails::class, ['requestId' => $this->job()['id']]);
        $this->stub(fn (Request $request) => $request->method() === 'PATCH'
            ? Http::response(['error' => ['message' => 'Unavailable.']], 503)
            : Http::response(['data' => str_ends_with($request->url(), '/me') ? $this->identity() : $this->job()]));
        $component->callAction('edit', data: ['title' => 'Updated kitchen tap repair',
            'description' => 'Repair the tap and inspect the pipe below it.', 'town' => 'Colombo',
            'preferredAt' => '2099-01-15 10:00:00', 'latitude' => null, 'longitude' => null])
            ->assertActionMounted('edit')
            ->assertSet('gatewayError', 'The service is temporarily unavailable. Please try again.')
            ->assertNoRedirect();
    }

    public function test_gateway_preserves_location_and_booking_times_and_rejects_extra_fields(): void
    {
        $user = $this->login();
        $this->stub(fn () => Http::response(['data' => []]));
        $gateway = app(SkillSyncGateway::class);
        $gateway->updateRequest($user, 'request-id', ['latitude' => 6.93, 'longitude' => 79.86, 'customerId' => 'forged']);
        Http::assertSent(fn (Request $request) => $request->data() === ['latitude' => 6.93, 'longitude' => 79.86]);
        $gateway->createBooking($user, ['requestId' => 'request-id', 'workerId' => 'worker-id',
            'scheduledAt' => '2099-01-15 10:00:00', 'scheduledEndAt' => '2099-01-15 12:00:00',
            'deadlineAt' => '2099-01-15 13:00:00', 'status' => 'completed']);
        Http::assertSent(fn (Request $request) => str_ends_with($request->url(), '/bookings')
            && $request['scheduledAt'] === '2099-01-15T10:00:00+05:30'
            && $request['scheduledEndAt'] === '2099-01-15T12:00:00+05:30'
            && $request['deadlineAt'] === '2099-01-15T13:00:00+05:30'
            && ! isset($request['status']));
        $gateway->submitComplaint($user, 'booking-id', ['reason' => 'Please inspect the follow-up leak.', 'status' => 'upheld']);
        Http::assertSent(fn (Request $request) => str_ends_with($request->url(), '/complaint')
            && $request->data() === ['reason' => 'Please inspect the follow-up leak.']);
    }

    public function test_notification_read_error_does_not_redirect_or_claim_success(): void
    {
        $this->login();
        $this->stub(function (Request $request) {
            if ($request->method() === 'PATCH') {
                return Http::response(['error' => ['message' => 'Unavailable.']], 503);
            }

            return Http::response(['data' => [], 'meta' => ['page' => 1, 'lastPage' => 1]]);
        });
        Livewire::test(Notifications::class)
            ->call('openNotification', 'notification-id')
            ->assertSet('readError', 'Could not mark this notification as read. Please try again.')
            ->assertNoRedirect();
    }

    public function test_notification_bell_uses_filtered_total_and_refreshes_without_loading_pages(): void
    {
        $this->login();
        $total = 125;
        $this->stub(function (Request $request) use (&$total) {
            return Http::response(['data' => [], 'meta' => ['total' => $total, 'page' => 1, 'perPage' => 1, 'lastPage' => 125]]);
        });
        $component = Livewire::test(NotificationBell::class)
            ->assertSet('unreadCount', 125)->assertSee('99+');
        Http::assertSentCount(1);
        Http::assertSent(fn (Request $request) => $request['unread'] === 'true' && $request['perPage'] === 1 && $request['page'] === 1);
        $total = 0;
        $component->dispatch('notifications-updated')->assertSet('unreadCount', 0)->assertDontSee('99+');
    }

    public function test_notification_bell_does_not_report_zero_for_invalid_counts_or_outages(): void
    {
        $this->login();
        foreach ([null, -1, '12'] as $total) {
            $this->stub(fn () => Http::response(['data' => [], 'meta' => ['total' => $total]]));
            Livewire::test(NotificationBell::class)->assertSet('unreadCount', null);
        }
        $this->stub(fn () => Http::response([], 503));
        Livewire::test(NotificationBell::class)->assertSet('unreadCount', null);
    }

    public function test_worker_accept_conflict_stays_visible_in_dialog(): void
    {
        $this->assertBookingConflict('worker', 'pending', 'accepted', null);
    }

    public function test_worker_start_conflict_preserves_field_errors_and_shows_summary(): void
    {
        $this->assertBookingConflict('worker', 'accepted', 'in_progress', ['scheduledAt' => ['Choose another time.']]);
    }

    public function test_customer_reopen_conflict_stays_visible_in_dialog(): void
    {
        $this->assertBookingConflict('customer', 'awaiting_confirmation', 'in_progress', ['note' => ['The worker is already booked.']]);
    }

    private function assertBookingConflict(string $role, string $status, string $nextStatus, ?array $fields): void
    {
        $this->login($role);
        Filament::setCurrentPanel(Filament::getPanel($role));
        $booking = ['id' => 'booking-test', 'requestId' => $this->job()['id'], 'workerId' => $this->worker()['id'],
            'status' => $status, 'scheduledAt' => now()->addDay()->toIso8601String(), 'quotedRateLkr' => 2500,
            'rateUnit' => 'visit', 'request' => $this->job(), 'worker' => $this->worker(), 'history' => []];
        $message = 'This appointment overlaps another booking. Choose a different time.';
        $this->stub(fn (Request $request) => $request->method() === 'PATCH'
            ? Http::response(['error' => ['code' => 'booking_time_conflict', 'message' => $message, 'fields' => $fields]], 409)
            : Http::response(['data' => str_ends_with($request->url(), '/me') ? $this->identity() : $booking]));
        $action = $role === 'worker' ? 'transition' : 'disputeCompletion';
        $component = Livewire::test($role === 'worker' ? JobDetails::class : BookingDetails::class, ['bookingId' => $booking['id']]);
        $component->callAction($action, data: ['note' => 'Please finish the remaining work.'], arguments: ['status' => $nextStatus])
            ->assertActionMounted($action)->assertHasActionErrors(['operation'])->assertNoRedirect();
        $this->assertStringContainsString($message, $component->instance()->getMountedAction()->getModalContent()->render());
        Http::assertSent(fn (Request $request) => $request->method() === 'PATCH' && $request['status'] === $nextStatus);
    }

    public function test_notification_icons_match_event_prefix_and_ignore_job_title_keywords(): void
    {
        $component = new Notifications;
        $cases = [
            'New booking: Review the pipe' => 'calendar-days',
            'Booking accepted: Repair' => 'check-circle',
            'Booking in progress: Repair' => 'wrench-screwdriver',
            'Booking awaiting confirmation: Repair' => 'clock',
            'Booking completed: Repair' => 'check-circle',
            'Booking rejected: Repair' => 'x-circle',
            'Booking cancelled: Repair' => 'x-circle',
            'New review for: Booking repair' => 'star',
            'Profile approved: Ready' => 'check-badge',
            'Profile changes requested: Add details' => 'pencil-square',
            'Review worker profile: Anu' => 'user-circle',
            'Complaint submitted: Repair' => 'flag',
            'Complaint requires review: Repair' => 'flag',
            'Complaint upheld: Repair' => 'flag',
            'Complaint dismissed: Repair' => 'flag',
            'Unknown update: Profile approved' => 'bell',
            '' => 'bell',
        ];
        foreach ($cases as $message => $icon) {
            $name = 'heroicon-o-'.$icon;
            $this->assertSame($name, $component->notificationIcon($message));
            $this->assertStringContainsString('<svg', svg($name)->toHtml());
        }
    }
}
