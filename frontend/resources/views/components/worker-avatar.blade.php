@props(['worker'])
@php
    $initials = collect(explode(' ', $worker['name'] ?? 'Worker'))->filter()->take(2)->map(fn ($part) => mb_strtoupper(mb_substr($part, 0, 1)))->join('');
    $photo = $worker['photoUrl'] ?? null;
    $validPhoto = is_string($photo) && preg_match('#^/api/v1/worker-photos/[a-f0-9]{32}\.jpg$#', $photo);
@endphp
<span {{ $attributes->class(['ss-avatar', 'ss-worker-avatar']) }} aria-hidden="true" x-data="{ failed: false }">
    <span>{{ $initials }}</span>
    @if($validPhoto)
        <img src="{{ $photo }}" alt="" loading="lazy" decoding="async" width="512" height="512"
             x-show="!failed" x-on:error="failed = true" class="ss-worker-avatar-photo">
    @endif
</span>
