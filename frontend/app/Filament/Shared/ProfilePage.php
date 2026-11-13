<?php

namespace App\Filament\Shared;

abstract class ProfilePage extends GatewayPage
{
    protected static ?string $slug = 'profile';

    protected static ?string $navigationLabel = 'My profile';

    protected static string|\BackedEnum|null $navigationIcon = 'heroicon-o-user-circle';

    protected string $view = 'filament.shared.profile';

    public ?array $data = [];

    public bool $profileSaved = false;

    public function mount(): void
    {
        $this->form->fill($this->gateway()->profile(auth()->user())['data']);
    }

    public function save(): void
    {
        $data = $this->form->getState();
        if ($this->perform(fn () => $this->gateway()->updateProfile(auth()->user(), $data), 'data')) {
            $this->profileSaved = true;
            $this->success('Your profile has been updated.');
        }
    }
}
