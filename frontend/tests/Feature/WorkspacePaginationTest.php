<?php

namespace Tests\Feature;

use App\Contracts\SkillSyncGateway;
use App\Filament\Admin\Pages\Records;
use App\Filament\Customer\Pages\Bookings;
use App\Livewire\Shared\Notifications;
use App\Models\User;
use Filament\Facades\Filament;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Http;
use Livewire\Livewire;
use Tests\TestCase;

class WorkspacePaginationTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
        config(['skillsync.fastapi_base_url' => 'http://backend.test']);
        Http::preventStrayRequests();
        $this->actingAs(User::factory()->create(['role' => 'customer', 'backend_id' => 'account-id', 'town' => 'Colombo']));
        session(['backend_token' => Crypt::encryptString('test-token')]);
        Filament::setCurrentPanel(Filament::getPanel('customer'));
    }

    private function page(Request $request, int $total = 45): array
    {
        return ['data' => [], 'meta' => ['page' => (int) ($request['page'] ?? 1), 'perPage' => 20, 'total' => $total, 'lastPage' => max(1, (int) ceil($total / 20))]];
    }

    public function test_profile_update_fetches_identity_once_and_preserves_account_id(): void
    {
        $user = auth()->user();
        $user->update(['role' => 'worker', 'worker_id' => 'worker-id']);
        Http::fake(function (Request $request) use ($user) {
            return Http::response(['data' => str_ends_with($request->url(), '/me')
                ? ['id' => 'account-id', 'name' => 'Updated Name', 'email' => $user->email, 'role' => 'worker', 'town' => 'Kandy', 'workerId' => 'worker-id']
                : ['id' => 'worker-id', 'name' => 'Updated Name']]);
        });
        $profile = app(SkillSyncGateway::class)->updateProfile($user, ['name' => 'Updated Name']);
        Http::assertSentCount(3);
        $this->assertSame(1, Http::recorded(fn (Request $request) => str_ends_with($request->url(), '/me'))->count());
        $this->assertSame('worker-id', $profile['data']['id']);
        $this->assertSame('account-id', $user->fresh()->backend_id);
        $this->assertSame('Updated Name', $user->fresh()->name);
    }

    public function test_booking_pages_request_only_the_selected_page_and_reset_on_filters(): void
    {
        Http::fake(fn (Request $request) => Http::response($this->page($request)));
        $page = Livewire::test(Bookings::class)->assertSee('Page 1 of 3');
        $page->set('pageNumber', 2)->assertSee('Page 2 of 3');
        Http::assertSent(fn (Request $request) => $request['page'] === 2 && $request['perPage'] === 20);
        $page->set('status', 'completed')->assertSet('pageNumber', 1);
        $page->set('pageNumber', 2)->set('search', 'Kitchen')->assertSet('pageNumber', 1)->assertSee('No matching bookings');
        Http::assertSent(fn (Request $request) => ($request['search'] ?? null) === 'Kitchen' && $request['status'] === 'completed' && $request['page'] === 1);
        $page->call('clearFilters')->assertSet('search', '')->assertSet('status', '');
        Http::assertNotSent(fn (Request $request) => $request['perPage'] === 100);
    }

    public function test_booking_failure_shows_retry_without_false_empty_state_and_recovers(): void
    {
        $failing = true;
        Http::fake(function (Request $request) use (&$failing) {
            return $failing ? Http::response([], 503) : Http::response($this->page($request, 0));
        });
        $page = Livewire::test(Bookings::class)->assertSee('Try again')->assertDontSee('bookings yet.');
        $failing = false;
        $page->call('$refresh')->assertDontSee('Try again')->assertSee('bookings yet.');
    }

    public function test_admin_list_is_loaded_once_per_render_and_details_use_single_record_endpoint(): void
    {
        auth()->user()->update(['role' => 'admin']);
        Filament::setCurrentPanel(Filament::getPanel('admin'));
        Http::fake(fn (Request $request) => Http::response(str_ends_with($request->url(), '/customers/customer-id')
            ? ['data' => ['id' => 'customer-id', 'name' => 'Selected Customer', 'role' => 'customer']]
            : $this->page($request)));
        $page = Livewire::test(Records::class);
        Http::assertSentCount(1);
        $page->set('pageNumber', 2)->set('pendingOnly', true)->assertSet('pageNumber', 1);
        Http::assertSent(fn (Request $request) => $request['pendingOnly'] === 'true');
        $page->set('entity', 'customers')->set('recordId', 'customer-id')->assertSee('Selected Customer');
        Http::assertSent(fn (Request $request) => str_ends_with($request->url(), '/customers/customer-id'));
    }

    public function test_notification_failure_does_not_show_caught_up_and_unread_resets_page(): void
    {
        $failing = true;
        Http::fake(function (Request $request) use (&$failing) {
            return $failing ? Http::response([], 503) : Http::response($this->page($request));
        });
        $page = Livewire::test(Notifications::class)->assertSee('Try again')->assertDontSee("You're all caught up");
        $failing = false;
        $page->call('$refresh')->assertDontSee('Try again')->set('pageNumber', 2)->set('filter', 'unread')->assertSet('pageNumber', 1);
        Http::assertSent(fn (Request $request) => $request['unread'] === 'true' && $request['page'] === 1);
    }
}
