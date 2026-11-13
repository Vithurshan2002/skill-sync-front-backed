<x-filament-panels::page>
    <div class="ss-tabs" aria-label="Filter bookings by status">
        @foreach(['' => 'All jobs', 'pending' => 'Pending', 'accepted' => 'Accepted', 'in_progress' => 'In progress', 'awaiting_confirmation' => 'Awaiting confirmation', 'completed' => 'Completed', 'rejected' => 'Rejected', 'cancelled' => 'Cancelled'] as $value => $label)
            <button type="button" @class(['ss-tab', 'is-active' => $status === $value]) wire:click="$set('status', '{{ $value }}')" aria-pressed="{{ $status === $value ? 'true' : 'false' }}">{{ $label }}</button>
        @endforeach
    </div>
    <label class="ss-field"><span>Search bookings</span><input type="search" wire:model.live.debounce.300ms="search" maxlength="200" placeholder="Request title or town"></label>
    @if($loadError)
        <x-api-error :message="$loadError" />
    @else
    <x-loading-region target="status,search,pageNumber,$refresh" :count="count($bookings) ?: 4" label="Loading bookings">
    <section class="ss-card ss-bookings-list"><div class="ss-section-heading"><h2>{{ $status ? str_replace('_', ' ', ucfirst($status)) : 'All' }} bookings</h2><span class="ss-muted">{{ $meta['total'] }} {{ $meta['total'] === 1 ? 'job' : 'jobs' }}</span></div>
        @forelse($bookings as $booking)
            <a class="ss-record-row" href="/{{ $area }}/{{ $recordPath }}/{{ $booking['id'] }}" wire:key="booking-{{ $booking['id'] }}"><div class="ss-icon-tile"><x-filament::icon icon="heroicon-o-wrench-screwdriver" /></div><div class="ss-record-copy"><strong>{{ $booking['request']['title'] ?? 'Service booking' }}</strong><span>{{ $area === 'customer' ? ($booking['worker']['name'] ?? '') : ($booking['request']['town'] ?? '') }} · {{ $this->localDate($booking['scheduledAt']) }}</span></div><div class="ss-record-price">LKR {{ number_format($booking['quotedRateLkr']) }}<span>/ {{ $booking['rateUnit'] }}</span></div><x-status-badge :status="$booking['status']" /><span aria-hidden="true">↗</span></a>
        @empty
            @if($status || $search)
                <div class="ss-empty"><h3>No matching bookings</h3><p>Try another status or search.</p><button type="button" class="ss-text-button" wire:click="clearFilters">Clear filters</button></div>
            @else
            <div class="ss-empty"><x-filament::icon icon="heroicon-o-calendar-days" /><h3>No {{ str_replace('_',' ', $status) }} bookings yet.</h3><p>{{ $area === 'customer' ? 'Your next great professional is a request away.' : 'New opportunities will appear here when customers book your services.' }}</p>@if($area === 'customer')<a class="ss-btn" href="/customer/requests/new">Create a request</a>@endif</div>
            @endif
        @endforelse
    </section>
    <x-api-pagination :meta="$meta" />
    </x-loading-region>
    @endif
</x-filament-panels::page>
