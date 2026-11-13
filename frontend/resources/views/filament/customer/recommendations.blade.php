<x-filament-panels::page class="ss-recommendations-page">
    <x-back-link :href="'/customer/requests/'.$requestId">Back to request</x-back-link>
    <div class="ss-stepper" aria-label="Request progress"><span><span class="ss-step-number">01</span><strong>Describe your job</strong></span><span class="is-active" aria-current="step"><span class="ss-step-number">02</span><strong>Meet your matches</strong></span><span><span class="ss-step-number">03</span><strong>Make a booking</strong></span></div>
    @include('filament.shared.error')
    <section class="ss-card ss-match-context"><div><span class="ss-eyebrow">MATCHING FOR YOUR REQUEST</span><h2>{{ $requestRecord['title'] }}</h2><p class="ss-muted">{{ $requestRecord['town'] }} · {{ $this->localDate($requestRecord['preferredAt']) }}</p></div><a class="ss-text-link" href="/customer/requests/{{ $requestId }}">View request ↗</a></section>
    <div class="ss-filter-bar ss-recommendation-filters" x-data="{ ready: false }" x-init="$nextTick(() => ready = true)">
        <label class="ss-field"><span>Service category</span>
            <span class="ss-filter-select">
                <select disabled x-bind:disabled="!ready" wire:model.live="category" aria-describedby="category-filter-help"><option value="">Choose a category</option>@foreach($categories as $label)<option value="{{ $label }}">{{ $label }}</option>@endforeach</select>
                <x-filament::icon icon="heroicon-o-chevron-down" />
            </span>
        </label>
        <label class="ss-field"><span>Maximum rate (LKR)</span><input disabled x-bind:disabled="!ready" type="number" min="1" wire:model.live.debounce.400ms="maxRate" placeholder="Any rate"></label>
        <p id="category-filter-help" class="ss-filter-help">Not quite right? Change the category.</p>
    </div>
    <x-loading-region target="category,maxRate,refreshRecommendations" variant="cards" :count="count($recommendations) ?: 3" label="Finding professionals?">
        @if(!$category)
            <div class="ss-empty ss-card"><x-filament::icon icon="heroicon-o-adjustments-horizontal" /><h2>Choose the skills your job needs.</h2><p>Select a service category above to find relevant professionals.</p></div>
        @elseif(!count($recommendations))
            <div class="ss-empty ss-card"><x-filament::icon icon="heroicon-o-magnifying-glass" /><h2>No suitable workers found</h2><p>Try another category or change the rate filter. Results must match your service category, town, and worker availability.</p><button class="ss-btn ss-btn-secondary" wire:click="refreshRecommendations" wire:loading.attr="disabled" wire:target="refreshRecommendations">Try again</button></div>
        @else
            <div class="ss-section-heading"><h2>{{ count($recommendations) }} {{ count($recommendations) === 1 ? 'professional' : 'professionals' }} to meet</h2><span class="ss-badge">Matching professionals</span></div>
            <div class="ss-recommendation-grid">
                @foreach($recommendations as $recommendation)
                    @php($worker = $recommendation['worker'])
                    <article class="ss-card ss-recommendation" wire:key="recommendation-{{ $worker['id'] }}">
                        <div class="ss-section-heading"><span class="ss-rank">{{ str_pad($recommendation['rank'], 2, '0', STR_PAD_LEFT) }} / MATCH</span><label class="ss-checkbox"><input type="checkbox" @checked(in_array($worker['id'], $comparison)) wire:click="toggleCompare('{{ $worker['id'] }}')"> Compare</label></div>
                        <div class="ss-worker-identity"><x-worker-avatar :worker="$worker" /><div><a href="/workers/{{ $worker['id'] }}"><h3>{{ $worker['name'] }}</h3></a><p>{{ $category }} · {{ $worker['town'] }}</p></div></div>
                        <div class="ss-worker-meta"><span>★ {{ $worker['rating'] ?? 'New' }} <span class="ss-muted">({{ $worker['reviewCount'] }} reviews)</span></span><span class="ss-badge">{{ $worker['available'] ? 'Available' : 'Unavailable' }}</span></div>
                        <div class="ss-score-grid"><x-score :value="$recommendation['categorySkillScore']" label="Category skill score" /><x-score :value="$recommendation['reliabilityProbability']" :probability="true" label="Reliability estimate" /></div>
                        <p class="ss-small ss-muted">{{ collect($worker['performance'])->where('category', $category)->sum('completedJobs') }} completed jobs in {{ $category }}</p>
                        <p class="ss-distance-label">@if(isset($recommendation['distanceKm'])){{ number_format($recommendation['distanceKm'], 1) }} km away <span>(straight line)</span>@else Town match &middot; GPS distance unavailable @endif</p>
                        <x-recommendation-explanation :data="$recommendation" :model="false" />
                        <div class="ss-booking-rate"><strong>LKR {{ number_format($worker['rateLkr']) }} <small>/ {{ $worker['rateUnit'] }}</small></strong>@if($worker['available'] && $requestRecord['status'] !== 'booked'){{ ($this->bookAction)(['workerId' => $worker['id']]) }}@else<a class="ss-text-link" href="/workers/{{ $worker['id'] }}">View profile →</a>@endif</div>
                    </article>
                @endforeach
            </div>
        @endif
    </x-loading-region>
    @if(count($compared))
        <section class="ss-card ss-comparison"><div class="ss-section-heading"><div><span class="ss-eyebrow">SIDE BY SIDE</span><h2>Your shortlist <span class="ss-muted">{{ count($compared) }}/3</span></h2></div><button class="ss-text-link" wire:click="$set('comparison', [])">Clear comparison</button></div><div class="ss-table-scroll" role="region" aria-label="Professional comparison" tabindex="0"><table class="ss-table"><caption class="sr-only">Compare selected professionals</caption><thead><tr><th>At a glance</th>@foreach($compared as $rec)<th>{{ $rec['worker']['name'] }}</th>@endforeach</tr></thead><tbody><tr><th>Rate basis</th>@foreach($compared as $rec)<td>LKR {{ number_format($rec['worker']['rateLkr']) }}/{{ $rec['worker']['rateUnit'] }}</td>@endforeach</tr><tr><th>Rating / reviews</th>@foreach($compared as $rec)<td>{{ $rec['worker']['rating'] ?? 'New' }} / {{ $rec['worker']['reviewCount'] }}</td>@endforeach</tr><tr><th>Category skill score</th>@foreach($compared as $rec)<td>{{ $rec['categorySkillScore'] !== null ? $rec['categorySkillScore'].'/100' : 'Not available yet' }}</td>@endforeach</tr><tr><th>Reliability estimate</th>@foreach($compared as $rec)<td>{{ $rec['reliabilityProbability'] !== null ? round($rec['reliabilityProbability']*100).'%' : 'Not available yet' }}</td>@endforeach</tr><tr><th>Availability</th>@foreach($compared as $rec)<td>{{ $rec['worker']['available'] ? 'Available' : 'Unavailable' }}</td>@endforeach</tr></tbody></table></div></section>
    @endif
    <p class="ss-small ss-muted">AI ranking is currently unavailable. You can still compare professionals and book.</p>
    <details class="ss-match-details">
        <summary>How matching works</summary>
        <p>Matches use approved profiles, your service category, availability, and rate filter. When both locations are saved, the worker's travel radius is used; otherwise, service towns are matched.</p>
        <p> Eligible professionals are listed in alphabetical order; this is not an AI quality ranking.</p>
    </details>
</x-filament-panels::page>

