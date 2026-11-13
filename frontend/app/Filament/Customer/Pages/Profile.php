<?php

namespace App\Filament\Customer\Pages;

use App\Filament\Shared\ProfilePage;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\TextInput;
use Filament\Schemas\Components\Section;
use Filament\Schemas\Schema;

class Profile extends ProfilePage
{
    protected static ?string $title = 'Your profile';

    protected static ?int $navigationSort = 4;

    protected ?string $subheading = 'The details that help us make your next job easier.';

    public function form(Schema $schema): Schema
    {
        return $schema->components([
            Section::make('Personal details')
                ->description('The name shown on your bookings and the email used to sign in.')
                ->icon('heroicon-o-identification')
                ->schema([
                    TextInput::make('name')->required()->maxLength(100),
                    TextInput::make('email')->disabled()->dehydrated(false),
                ])->columns(2)->columnSpanFull(),
            Section::make('Contact details')
                ->description('Choose how professionals can reach you about your bookings.')
                ->icon('heroicon-o-chat-bubble-left-right')
                ->schema([
                    TextInput::make('phone')->tel()->maxLength(30)->helperText('Enter a number your professional can use to coordinate the job.'),
                    TextInput::make('town')->required()->maxLength(80),
                    Select::make('contactPreference')->label('Preferred contact method')->options(['email' => 'Email', 'phone' => 'Phone'])->required(),
                ])->columns(2)->columnSpanFull(),
        ])->columns(2)->statePath('data');
    }
}
