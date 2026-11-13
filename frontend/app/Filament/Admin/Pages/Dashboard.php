<?php

namespace App\Filament\Admin\Pages;

use App\Filament\Shared\GatewayPage;

class Dashboard extends GatewayPage
{
    protected static string $role = 'admin';

    protected static ?string $slug = 'dashboard';

    protected static ?string $title = 'Administration';

    protected static ?string $navigationLabel = 'Overview';

    protected static string|\BackedEnum|null $navigationIcon = 'heroicon-o-squares-2x2';

    protected static ?int $navigationSort = 1;

    protected string $view = 'filament.admin.dashboard';

    protected ?string $subheading = 'Manage workers, customers, services, and bookings.';

    protected function getViewData(): array
    {
        $data = $this->gateway()->dashboard(auth()->user())['data'];
        $counts = $data['counts'];
        $models = $data['models'];
        $pendingWorkers = $data['pendingWorkers'] ?? 0;

        return compact('counts', 'models', 'pendingWorkers');
    }
}
