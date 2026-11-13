@php
    use Filament\Support\View\ComponentAttributeBag;
@endphp

<div
    role="status"
    aria-busy="true"
    {{ ($attributes ?? new ComponentAttributeBag)->gridColumn($columnSpan, $columnStart)->class(['fi-wi-widget', 'ss-stats-placeholder']) }}
>
    <span class="fi-sr-only">Loading dashboard statistics...</span>
    <div class="ss-stats-placeholder-grid" aria-hidden="true">
        @for($index = 0; $index < 3; $index++)
            <div class="fi-wi-stats-overview-stat ss-stats-placeholder-card">
                <div class="ss-stats-placeholder-label">
                    <span class="ss-skeleton ss-stats-placeholder-icon"></span>
                    <span class="ss-skeleton ss-stats-placeholder-title"></span>
                </div>
                <span class="ss-skeleton ss-stats-placeholder-value"></span>
                <span class="ss-skeleton ss-stats-placeholder-description"></span>
            </div>
        @endfor
    </div>
</div>
