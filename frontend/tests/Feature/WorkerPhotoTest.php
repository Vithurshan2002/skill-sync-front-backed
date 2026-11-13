<?php

namespace Tests\Feature;

use App\Filament\Worker\Pages\Profile;
use App\Models\User;
use Filament\Facades\Filament;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Factory;
use Illuminate\Http\Client\Request;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Http;
use Livewire\Livewire;
use Tests\TestCase;

class WorkerPhotoTest extends TestCase
{
    use RefreshDatabase;

    private ?string $photoUrl = null;

    private bool $failUpload = false;

    private User $worker;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withoutVite();
        config(['skillsync.fastapi_base_url' => 'http://backend.test']);
        $this->worker = User::factory()->create(['role' => 'worker', 'backend_id' => 'worker-user', 'worker_id' => 'worker-id']);
        $this->actingAs($this->worker)->withSession(['backend_token' => Crypt::encryptString('photo-test-token')]);
        Filament::setCurrentPanel(Filament::getPanel('worker'));
        Http::preventStrayRequests();
        Http::fake(function (Request $request) {
            if ($request->method() === 'PUT') {
                if ($this->failUpload) {
                    return Http::response(['error' => ['message' => 'Invalid photo', 'fields' => ['photo' => ['Photo could not be processed.']]]], 422);
                }
                $this->photoUrl = '/api/v1/worker-photos/'.str_repeat('a', 32).'.jpg';
            } elseif ($request->method() === 'DELETE') {
                $this->photoUrl = null;
            }
            if (str_contains($request->url(), '/categories')) {
                return Http::response(['data' => [['id' => 'plumbing', 'label' => 'Plumbing']]]);
            }

            return Http::response(['data' => [
                'id' => 'worker-id', 'workerId' => 'worker-id', 'name' => 'Arul Test', 'role' => 'worker',
                'email' => $this->worker->email, 'town' => 'Colombo', 'phone' => null, 'contactPreference' => 'email',
                'categories' => ['Plumbing'], 'serviceTowns' => ['Colombo'], 'bio' => 'Careful plumbing repairs.',
                'yearsExperience' => 5, 'rateLkr' => 2500, 'rateUnit' => 'visit', 'available' => true,
                'approvalStatus' => 'approved', 'verified' => true, 'photoUrl' => $this->photoUrl,
            ]]);
        });
    }

    private function photo(): UploadedFile
    {
        return UploadedFile::fake()->createWithContent('portrait.png', base64_decode('iVBORw0KGgoAAAANSUhEUgAAAGQAAABQCAIAAABga0e4AAAAvklEQVR4nO3SsREAIAwDscDkjM4K+V6qXf35zLxh5y53iNV4ViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViDW7H3OBAEg1VOHKQAAAABJRU5ErkJggg=='));
    }

    public function test_upload_sends_image_bytes_and_remove_restores_initials(): void
    {
        $image = $this->photo();
        $bytes = $image->get();
        $component = Livewire::test(Profile::class)->set('photo', $image)->call('uploadPhoto')
            ->assertHasNoErrors()->assertSet('photo', null)->assertSee('/api/v1/worker-photos/'.str_repeat('a', 32).'.jpg');
        Http::assertSent(fn (Request $request) => $request->method() === 'PUT'
            && $request->hasHeader('Content-Type', 'image/png') && $request->body() === $bytes
            && $request->hasHeader('Authorization', 'Bearer photo-test-token'));
        $component->callAction('removePhoto')->assertHasNoErrors()->assertDontSee('/api/v1/worker-photos/'.str_repeat('a', 32).'.jpg');
        Http::assertSent(fn (Request $request) => $request->method() === 'DELETE');
    }

    public function test_invalid_file_is_rejected_before_calling_backend(): void
    {
        Livewire::test(Profile::class)->set('photo', UploadedFile::fake()->createWithContent('bad.svg', '<svg/>'))
            ->call('uploadPhoto')->assertHasErrors('photo');
        Http::assertNotSent(fn (Request $request) => $request->method() === 'PUT');
    }

    public function test_selecting_photo_clears_previous_required_error(): void
    {
        Livewire::test(Profile::class)->call('uploadPhoto')->assertHasErrors('photo')
            ->set('photo', $this->photo())->assertHasNoErrors('photo')
            ->call('uploadPhoto')->assertHasNoErrors();
    }

    public function test_backend_error_keeps_selection_and_existing_photo(): void
    {
        $this->photoUrl = '/api/v1/worker-photos/'.str_repeat('b', 32).'.jpg';
        $this->failUpload = true;
        Livewire::test(Profile::class)->set('photo', $this->photo())->call('uploadPhoto')
            ->assertHasErrors('photo')->assertSee('Photo could not be processed.')
            ->assertSee($this->photoUrl);
    }

    public function test_avatar_restricts_photo_urls_and_has_initials_fallback(): void
    {
        $this->blade('<x-worker-avatar :worker="$worker" />', ['worker' => ['name' => 'Nila Perera', 'photoUrl' => 'https://untrusted.test/tracker']])
            ->assertSee('NP')->assertDontSee('<img', false);
    }

    public function test_photo_proxy_serves_only_jpeg_from_configured_backend(): void
    {
        Http::swap(new Factory);
        Http::preventStrayRequests();
        Http::fake(['http://backend.test/api/v1/worker-photos/*' => Http::response('jpeg-bytes', 200, ['Content-Type' => 'image/jpeg'])]);
        $this->get('/api/v1/worker-photos/'.str_repeat('a', 32).'.jpg')->assertOk()
            ->assertHeader('Content-Type', 'image/jpeg')->assertHeader('X-Content-Type-Options', 'nosniff');
        auth()->logout();
        $this->get('/api/v1/worker-photos/'.str_repeat('a', 32).'.jpg')->assertOk();
        $this->get('/api/v1/worker-photos/invalid.jpg')->assertNotFound();
    }
}
