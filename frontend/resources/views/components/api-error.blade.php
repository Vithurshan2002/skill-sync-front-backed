@props(['message'])
<div class="ss-alert ss-alert-error" role="alert">
    <p>{{ $message }}</p>
    <button type="button" class="ss-text-button" wire:click="$refresh" wire:loading.attr="disabled">
        <span wire:loading.remove wire:target="$refresh">Try again</span>
        <span wire:loading wire:target="$refresh" role="status">Retrying...</span>
    </button>
</div>
