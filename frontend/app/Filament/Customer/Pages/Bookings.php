<?php

namespace App\Filament\Customer\Pages;

use App\Filament\Shared\GatewayPage;
use Livewire\Attributes\Url;

class Bookings extends GatewayPage
{
    protected static ?string $slug = 'bookings';

    protected static ?string $title = 'Your bookings';

    protected static ?string $navigationLabel = 'Bookings';

    protected static string|\BackedEnum|null $navigationIcon = 'heroicon-o-calendar-days';

    protected static ?int $navigationSort = 3;

    protected string $view = 'filament.shared.bookings';

    protected ?string $subheading = 'From the first request to the finishing touches.';

    #[Url]
    public string $status = '';

    #[Url]
    public string $search = '';

    #[Url]
    public int $pageNumber = 1;

    public function clearFilters(): void
    {
        $this->status = '';
        $this->search = '';
        $this->pageNumber = 1;
    }

    public function updatedStatus(): void
    {
        $this->pageNumber = 1;
    }

    public function updatedSearch(): void
    {
        $this->pageNumber = 1;
    }

    protected function getViewData(): array
    {
        $this->pageNumber = max(1, min(1000000, $this->pageNumber));
        $result = $this->loadData(fn () => $this->gateway()->bookingsPage(auth()->user(), ['status' => $this->status, 'search' => $this->search], $this->pageNumber));
        if ($result && $this->pageNumber > $result['meta']['lastPage']) {
            $this->pageNumber = $result['meta']['lastPage'];
            $result = $this->loadData(fn () => $this->gateway()->bookingsPage(auth()->user(), ['status' => $this->status, 'search' => $this->search], $this->pageNumber));
        }

        return ['bookings' => $result['data'] ?? [], 'meta' => $result['meta'] ?? null, 'area' => static::$role, 'recordPath' => static::$role === 'worker' ? 'jobs' : 'bookings'];
    }
}
