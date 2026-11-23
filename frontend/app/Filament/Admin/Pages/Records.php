<?php

namespace App\Filament\Admin\Pages;

use App\Filament\Shared\GatewayPage;
use Filament\Actions\Action;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\Textarea;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Concerns\InteractsWithTable;
use Filament\Tables\Contracts\HasTable;
use Filament\Tables\Table;
use Illuminate\Contracts\View\View;
use Livewire\Attributes\Url;

class Records extends GatewayPage implements HasTable
{
    use InteractsWithTable;

    protected static string $role = 'admin';

    protected static ?string $slug = 'records';

    protected static ?string $title = 'Records';

    protected static ?string $navigationLabel = 'Manage records';

    protected static string|\BackedEnum|null $navigationIcon = 'heroicon-o-rectangle-stack';

    protected static ?int $navigationSort = 2;

    protected string $view = 'filament.admin.records';

    protected ?string $subheading = 'Review worker applications, maintain categories, and inspect records.';

    #[Url]
    public string $entity = 'workers';

    #[Url]
    public string $recordId = '';

    #[Url]
    public string $detailTab = 'profile';

    #[Url]
    public bool $pendingOnly = false;

    public string $search = '';

    #[Url]
    public int $pageNumber = 1;

    private ?array $listResult = null;

    private bool $listLoaded = false;

    public function updatedEntity(): void
    {
        $this->pageNumber = 1;
        $this->recordId = '';
        $this->detailTab = 'profile';
        $this->search = '';
        $this->pendingOnly = false;
        $this->resetTable();
    }

    public function updatedSearch(): void
    {
        $this->pageNumber = 1;
        $this->resetTable();
    }

    public function updatedPendingOnly(): void
    {
        $this->pageNumber = 1;
        $this->resetTable();
    }

    public function updatedPageNumber(): void
    {
        $this->resetTable();
    }

    private function recordsPage(): ?array
    {
        if (! $this->listLoaded) {
            abort_unless(in_array($this->entity, ['workers', 'customers', 'categories', 'requests', 'bookings', 'reviews', 'complaints'], true), 404);
            $this->pageNumber = max(1, min(1000000, $this->pageNumber));
            $this->listResult = $this->loadData(fn () => $this->gateway()->adminRecordsPage(auth()->user(), $this->entity, ['search' => $this->search, 'pendingOnly' => $this->pendingOnly], $this->pageNumber));
            if ($this->listResult && $this->pageNumber > $this->listResult['meta']['lastPage']) {
                $this->pageNumber = $this->listResult['meta']['lastPage'];
                $this->listResult = $this->loadData(fn () => $this->gateway()->adminRecordsPage(auth()->user(), $this->entity, ['search' => $this->search, 'pendingOnly' => $this->pendingOnly], $this->pageNumber));
            }
            $this->listLoaded = true;
        }

        return $this->listResult;
    }

    public function table(Table $table): Table
    {
        return $table->records(function (): array {
            abort_unless(in_array($this->entity, ['workers', 'customers', 'categories', 'requests', 'bookings', 'reviews', 'complaints'], true), 404);

            return collect($this->recordsPage()['data'] ?? [])->keyBy('id')->all();
        })->columns([
            TextColumn::make('displayName')->label('Record')->state(fn (array $record): string => $record['name'] ?? $record['label'] ?? $record['title'] ?? $record['id'])->description(fn (array $record): string => $record['id'])->wrap(),
            TextColumn::make('details')->label('Details')->state(fn (array $record): string => $record['town'] ?? $record['description'] ?? $record['email'] ?? $record['comment'] ?? (isset($record['workerId']) ? 'Worker '.$record['workerId'] : 'Record'))->wrap()->limit(100),
            TextColumn::make('context')->label('Status / context')->state(fn (array $record): string => isset($record['status']) ? ucfirst(str_replace('_', ' ', $record['status'])) : ($this->entity === 'workers' ? ucfirst(str_replace('_', ' ', $record['approvalStatus'] ?? 'pending')) : 'Record'))->badge()->color('gray'),
        ])->recordActionsColumnLabel('Actions')->recordActions([
            Action::make('details')->label('View')->icon('heroicon-o-eye')->button()->outlined()->labeledFrom('sm')
                ->tooltip('View details')->extraAttributes(['class' => 'ss-record-view-button', 'aria-label' => 'View details'])
                ->action(function (array $record): void {
                    $this->recordId = $record['id'];
                    $this->detailTab = 'profile';
                }),
        ])->paginated(false)->emptyStateHeading('No matching records')->emptyStateDescription('Try another search or record type.');
    }

    protected function getViewData(): array
    {
        abort_unless(in_array($this->detailTab, ['profile', 'changes'], true), 404);
        abort_unless(in_array($this->entity, ['workers', 'customers', 'categories', 'requests', 'bookings', 'reviews', 'complaints'], true), 404);
        $selected = null;
        $records = [];
        $meta = null;
        if ($this->recordId) {
            $result = $this->loadData(fn () => $this->gateway()->adminRecord(auth()->user(), $this->entity, $this->recordId));
            $selected = $result['data'] ?? null;
        } else {
            $result = $this->recordsPage();
            $records = $result['data'] ?? [];
            $meta = $result['meta'] ?? null;
        }

        return compact('records', 'selected', 'meta');
    }

    public function editCategoryAction(): Action
    {
        return Action::make('editCategory')->label('Edit description')->icon('heroicon-o-pencil-square')->modalHeading('Edit category')
            ->modalDescription('The exact category labels and stable identifiers are preserved for the future classifier.')
            ->fillForm(function (array $arguments) {
                return $this->gateway()->adminRecord(auth()->user(), 'categories', $arguments['id'])['data'];
            })
            ->schema([Textarea::make('description')->required()->minLength(10)->maxLength(300)->rows(3), Textarea::make('exampleRequest')->label('Example request')->required()->minLength(15)->maxLength(2000)->rows(3)])
            ->action(function (array $arguments, array $data) {
                if ($this->perform(fn () => $this->gateway()->updateCategory(auth()->user(), $arguments['id'], $data))) {
                    $this->success('Category details updated.');
                }
            });
    }

    public function resolveComplaintAction(): Action
    {
        return Action::make('resolveComplaint')->label('Review complaint')
            ->schema([
                Select::make('status')->options(['upheld' => 'Uphold complaint', 'dismissed' => 'Dismiss complaint'])->required(),
                Textarea::make('resolution')->label('Evidence reviewed and reason for decision')->required()->minLength(10)->maxLength(2000),
            ])->action(function (array $arguments, array $data): void {
                if ($this->perform(fn () => $this->gateway()->resolveComplaint(auth()->user(), $arguments['id'], $data))) {
                    $this->success('Complaint reviewed. Both parties have been notified.');
                }
            });
    }

    public function verifyAction(): Action
    {
        return $this->workerReviewAction('verify', 'Review application', 'Review worker application');
    }

    public function reviewChangesAction(): Action
    {
        return $this->workerReviewAction('reviewChanges', 'Review changes', 'Review profile changes');
    }

    private function workerReviewAction(string $name, string $label, string $heading): Action
    {
        return Action::make($name)->label($label)->color('gray')->requiresConfirmation()
            ->modalHeading($heading)->modalSubmitActionLabel('Save decision')
            ->modalContent(fn (): View => $this->actionErrorContent())
            ->modalDescription('Approval makes a complete profile visible and eligible for new bookings. Requesting changes hides it until approved again. Your feedback is visible to the worker.')
            ->schema([
                Select::make('decision')->label('Decision')->options(['approve' => 'Approve profile', 'changes' => 'Request changes / withdraw approval'])->required(),
                Textarea::make('note')->label('Feedback for worker')->required()->minLength(5)->maxLength(500),
            ])
            ->action(function (array $arguments, array $data) {
                if ($this->perform(fn () => $this->gateway()->verifyWorker(auth()->user(), $arguments['id'], $data['decision'] === 'approve', $data['note']), $this->getMountedActionSchema()->getStatePath())) {
                    $this->resetTable();
                    $this->success('Application reviewed. The worker has been notified.');
                }
            });
    }

    private function actionErrorContent(): View
    {
        $errorKey = $this->getMountedActionSchema()->getStatePath().'.operation';

        return view('filament.shared.action-error', [
            'operationErrors' => $this->getErrorBag()->get($errorKey),
            'serviceError' => $this->gatewayError,
        ]);
    }
}
