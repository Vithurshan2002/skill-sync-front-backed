@props(['meta'])
@if($meta && $meta['lastPage'] > 1)
@php
    $visiblePages = collect([1, ...range(max(1, $meta['page'] - 1), min($meta['lastPage'], $meta['page'] + 1)), $meta['lastPage']])->unique()->sort()->values();
@endphp
<nav class="ss-api-pagination" aria-label="Results pages">
    <div class="ss-pagination-controls">
        <button type="button" class="ss-pagination-button" wire:click="$set('pageNumber', {{ max(1, $meta['page'] - 1) }})" wire:loading.attr="disabled" @disabled($meta['page'] <= 1)>
            <x-filament::icon icon="heroicon-m-chevron-left" /><span>Previous</span>
        </button>
        <div class="ss-pagination-numbers">
            @foreach($visiblePages as $number)
                @if($loop->index > 0 && $number - $visiblePages[$loop->index - 1] > 1)
                    <span class="ss-pagination-gap" aria-hidden="true">&hellip;</span>
                @endif
                <button type="button" @class(['ss-pagination-button', 'ss-pagination-number', 'is-current' => $number === $meta['page']])
                    wire:key="pagination-page-{{ $number }}" wire:click="$set('pageNumber', {{ $number }})" wire:loading.attr="disabled"
                    aria-label="Page {{ $number }}" @if($number === $meta['page']) aria-current="page" @endif>{{ $number }}</button>
            @endforeach
        </div>
        <button type="button" class="ss-pagination-button" wire:click="$set('pageNumber', {{ min($meta['lastPage'], $meta['page'] + 1) }})" wire:loading.attr="disabled" @disabled($meta['page'] >= $meta['lastPage'])>
            <span>Next</span><x-filament::icon icon="heroicon-m-chevron-right" />
        </button>
    </div>
</nav>
@endif
