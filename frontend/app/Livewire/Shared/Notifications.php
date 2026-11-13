<?php

namespace App\Livewire\Shared;

use App\Contracts\SkillSyncGateway;
use Livewire\Attributes\Layout;
use Livewire\Attributes\Url;
use Livewire\Component;
use Symfony\Component\HttpKernel\Exception\HttpException;

#[Layout('components.layout')]
class Notifications extends Component
{
    public string $filter = 'all';

    #[Url]
    public int $pageNumber = 1;

    public function updatedFilter(): void
    {
        $this->pageNumber = 1;
    }

    public ?string $readError = null;

    public function markRead(string $id): void
    {
        $this->readNotification($id);
    }

    public function openNotification(string $id): void
    {
        $notification = $this->readNotification($id);
        if ($notification === null) {
            return;
        }

        $target = $notification['targetPath'] ?? '';
        if (! is_string($target) || ! str_starts_with($target, '/')
            || str_starts_with($target, '//') || preg_match('/[\\\\\x00-\x20]/', $target)) {
            $target = route('notifications', absolute: false);
        }
        $this->redirect($target);
    }

    private function readNotification(string $id): ?array
    {
        $this->readError = null;
        try {
            $notification = app(SkillSyncGateway::class)->markNotificationRead(auth()->user(), $id)['data'];
        } catch (HttpException $exception) {
            if ($exception->getStatusCode() < 500) {
                throw $exception;
            }
            $this->readError = 'Could not mark this notification as read. Please try again.';

            return null;
        }
        $this->dispatch('notifications-updated');

        return $notification;
    }

    public function notificationIcon(string $message): string
    {
        $prefix = strtolower(trim(explode(':', $message, 2)[0]));

        return match ($prefix) {
            'new booking' => 'heroicon-o-calendar-days',
            'booking accepted', 'booking completed' => 'heroicon-o-check-circle',
            'booking in progress' => 'heroicon-o-wrench-screwdriver',
            'booking awaiting confirmation' => 'heroicon-o-clock',
            'booking rejected', 'booking cancelled' => 'heroicon-o-x-circle',
            'new review for' => 'heroicon-o-star',
            'profile approved' => 'heroicon-o-check-badge',
            'profile changes requested' => 'heroicon-o-pencil-square',
            'review worker profile' => 'heroicon-o-user-circle',
            'complaint submitted', 'complaint requires review', 'complaint upheld', 'complaint dismissed' => 'heroicon-o-flag',
            default => 'heroicon-o-bell',
        };
    }

    public function render()
    {
        $items = [];
        $meta = null;
        $unread = null;
        $loadError = null;
        $this->pageNumber = max(1, min(1000000, $this->pageNumber));
        try {
            $gateway = app(SkillSyncGateway::class);
            $result = $gateway->notificationsPage(auth()->user(), $this->filter === 'unread', $this->pageNumber);
            if ($this->pageNumber > $result['meta']['lastPage']) {
                $this->pageNumber = $result['meta']['lastPage'];
                $result = $gateway->notificationsPage(auth()->user(), $this->filter === 'unread', $this->pageNumber);
            }
            $unread = $this->filter === 'unread' ? $result['meta']['total'] : $gateway->unreadNotificationCount(auth()->user());
            $items = $result['data'];
            $meta = $result['meta'];
        } catch (HttpException $exception) {
            if ($exception->getStatusCode() < 500) {
                throw $exception;
            }
            $loadError = 'Notifications could not be loaded. Please try again.';
        }

        return view('livewire.shared.notifications', compact('items', 'unread', 'meta', 'loadError'));
    }
}
