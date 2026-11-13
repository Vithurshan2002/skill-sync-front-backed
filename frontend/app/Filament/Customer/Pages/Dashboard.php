<?php

namespace App\Filament\Customer\Pages;

use App\Filament\Shared\GatewayPage;
use App\Filament\Shared\WorkspaceStats;
use Filament\Actions\Action;
use Livewire\Attributes\Url;

class Dashboard extends GatewayPage
{
    protected static ?string $slug = 'dashboard';

    protected static ?string $title = 'Your home, in good hands.';

    protected static ?string $navigationLabel = 'Overview';

    protected static string|\BackedEnum|null $navigationIcon = 'heroicon-o-squares-2x2';

    protected static ?int $navigationSort = 1;

    protected string $view = 'filament.customer.dashboard';

    protected ?string $subheading = 'A little less to do. A little more peace of mind.';

    protected function getHeaderActions(): array
    {
        return [Action::make('request')->label('New service request')->icon('heroicon-o-plus')->url('/customer/requests/new')];
    }

    protected function getHeaderWidgets(): array
    {
        return [WorkspaceStats::class];
    }

    #[Url]
    public int $pageNumber = 1;

    protected function getViewData(): array
    {
        $this->pageNumber = max(1, min(1000000, $this->pageNumber));
        $result = $this->loadData(function (): array {
            $page = $this->gateway()->requestsPage(auth()->user(), $this->pageNumber);
            if ($this->pageNumber > $page['meta']['lastPage']) {
                $this->pageNumber = $page['meta']['lastPage'];
                $page = $this->gateway()->requestsPage(auth()->user(), $this->pageNumber);
            }

            return ['requests' => $page['data'], 'meta' => $page['meta'],
                'bookings' => $this->gateway()->bookingsPage(auth()->user(), ['group' => 'active', 'order' => 'scheduled_asc'])['data'],
                'notifications' => $this->gateway()->notificationsPage(auth()->user())['data']];
        });

        return $result ?? ['requests' => [], 'meta' => null, 'bookings' => [], 'notifications' => []];
    }
}
