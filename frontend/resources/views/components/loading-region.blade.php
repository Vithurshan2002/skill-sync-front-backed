@props(['target', 'variant' => 'rows', 'count' => 4, 'label' => 'Loading results?'])
<div @class(['ss-async-region', 'ss-async-table' => $variant === 'table']) wire:loading.attr="aria-busy" wire:target="{{ $target }}">
    <div class="ss-async-content" wire:loading.delay.class="ss-async-pending" wire:loading.attr="inert" wire:target="{{ $target }}">
        {{ $slot }}
    </div>
    <div class="ss-async-placeholder" style="display: none" wire:loading.delay.block wire:target="{{ $target }}">
        <p class="sr-only" role="status">{{ $label }}</p>
        <div @class(['ss-recommendation-grid' => $variant === 'cards', 'ss-skeleton-rows' => $variant !== 'cards']) aria-hidden="true">
            @for($row = 0; $row < max(1, min($variant === 'table' ? 20 : 6, $count)); $row++)
                @if($variant === 'cards')
                    <div class="ss-card ss-skeleton-match">
                        <span class="ss-skeleton ss-skeleton-avatar"></span>
                        <div class="ss-skeleton-copy"><span class="ss-skeleton ss-skeleton-name"></span><span class="ss-skeleton ss-skeleton-service"></span></div>
                        <div class="ss-skeleton-description"><span class="ss-skeleton"></span><span class="ss-skeleton"></span><span class="ss-skeleton"></span></div>
                        <span class="ss-skeleton ss-skeleton-button"></span>
                    </div>
                @else
                    <div class="ss-skeleton-row">
                        @if($variant !== 'table')<span class="ss-skeleton ss-skeleton-avatar"></span>@endif
                        <div class="ss-skeleton-row-copy"><span class="ss-skeleton ss-skeleton-name"></span><span class="ss-skeleton ss-skeleton-service"></span></div>
                        <span class="ss-skeleton ss-skeleton-badge"></span>
                    </div>
                @endif
            @endfor
        </div>
    </div>
</div>
