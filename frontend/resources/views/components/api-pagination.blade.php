@props(['meta'])
@if($meta && $meta['lastPage'] > 1)
<nav class="ss-form-actions" aria-label="Results pages">
    <button type="button" class="ss-btn ss-btn-secondary" wire:click="$set('pageNumber', {{ max(1, $meta['page'] - 1) }})" wire:loading.attr="disabled" @disabled($meta['page'] <= 1)>Previous</button>
    <span class="ss-muted" role="status">Page {{ $meta['page'] }} of {{ $meta['lastPage'] }} / {{ $meta['total'] }} results</span>
    <button type="button" class="ss-btn ss-btn-secondary" wire:click="$set('pageNumber', {{ min($meta['lastPage'], $meta['page'] + 1) }})" wire:loading.attr="disabled" @disabled($meta['page'] >= $meta['lastPage'])>Next</button>
</nav>
@endif
