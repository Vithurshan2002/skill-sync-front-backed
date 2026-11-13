@props(['category'])
<svg {{ $attributes->class(['ss-icon', 'ss-service-icon']) }} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    @switch(strtolower(trim($category)))
        @case('air conditioning repair')
            <rect x="3" y="3" width="18" height="9" rx="2" />
            <path d="M6 9h12M17 6h1M7 15v3m5-3v6m5-6v3" />
            @break
        @case('appliance repair')
            <rect x="4" y="2" width="16" height="20" rx="2" />
            <path d="M4 7h16M7 4.5h.01M10 4.5h.01M15 4.5h2" />
            <circle cx="12" cy="14" r="4.5" />
            <path d="M8 14c2-2 6 2 8 0" />
            @break
        @case('gardening')
            <path d="M12 15V9M12 12C6 12 3 9 3 4c6 0 9 3 9 8Zm0-3c0-4 3-6 8-6 0 4-3 6-8 6ZM6 15h12l-2 7H8l-2-7Z" />
            @break
        @case('masonry')
            <rect x="2" y="4" width="20" height="16" rx="1" />
            <path d="M2 9h20M2 15h20M8 4v5m8-5v5M6 9v6m8-6v6M9 15v5m9-5v5" />
            @break
        @case('painting')
            <rect x="3" y="3" width="14" height="6" rx="1.5" />
            <path d="M17 6h3v7h-9v3" />
            <rect x="9" y="16" width="4" height="6" rx="1" />
            @break
        @case('roofing')
            <path d="m2 12 10-9 10 9M5 10v11h14V10M16 6V3h3v6M7 12h10M9 9h6M9 21v-6h6v6" />
            @break
        @case('plumbing')
            <path d="M3 10v8m0-6h7V9h6v3h1a4 4 0 0 1 4 4v1h-5v-1h-6v-1H3M13 9V5m-4 0h8" />
            <path d="M18.5 19s-1.5 1.5-1.5 2a1.5 1.5 0 0 0 3 0c0-.5-1.5-2-1.5-2Z" />
            @break
        @case('electrical')
            <path d="M8 3v5m8-5v5M6 8h12v3a6 6 0 0 1-12 0V8Zm6 9v2a3 3 0 0 1-3 3H6" />
            <path d="m12.5 9.5-2 3H13l-1.5 2" />
            @break
        @case('carpentry')
            <path d="M4 4h10c3 0 5 2 6 5l-5-2-2 2H4V4Zm5 5v11h4V9M9 17h4" />
            @break
        @case('welding')
            <path d="M7 3h10l3 4v8l-4 6H8l-4-6V7l3-4Z" />
            <path d="M7 7h10v6H7zM9 17h6m-6 2h6M4 9H2v4h2m16-4h2v4h-2" />
            @break
        @default
            <path d="M14 6a5 5 0 0 0-6 6l-5 5a2.1 2.1 0 0 0 3 3l5-5a5 5 0 0 0 6-6l-3 3-3-3 3-3Z" />
    @endswitch
</svg>
