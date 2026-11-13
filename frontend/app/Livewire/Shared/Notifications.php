<?php

namespace App\Livewire\Shared;

use App\Contracts\SkillSyncGateway;
use Livewire\Attributes\Layout;
use Livewire\Component;
use Symfony\Component\HttpKernel\Exception\HttpException;

#[Layout('components.layout')]
class Notifications extends Component
{
    public string $filter = 'all';

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
        $items = app(SkillSyncGateway::class)->notifications(auth()->user())['data'];
        $unread = collect($items)->whereNull('readAt')->count();
        if ($this->filter === 'unread') {
            $items = array_values(array_filter($items, fn ($item) => $item['readAt'] === null));
        }

        return view('livewire.shared.notifications', compact('items', 'unread'));
    }
}
