<x-filament-panels::page>
    <div class="ss-admin-dashboard">
        <section class="ss-card"><div class="ss-section-heading"><div><span class="ss-eyebrow">WORKER APPLICATIONS</span><h2>{{ $pendingWorkers }} ready for review</h2><p class="ss-muted">Approve complete profiles or request corrections before they receive new bookings.</p></div><a class="ss-btn" href="/admin/records?entity=workers&amp;pendingOnly=1">Review applications</a></div></section>
        <section class="ss-card ss-admin-models">
            <div class="ss-admin-model-heading">
                <div>
                    <span class="ss-eyebrow">MATCHING AND MODELS</span>
                    <h2>Service matching and AI status</h2>
                </div>
                <div class="ss-icon-tile" aria-hidden="true"><x-filament::icon icon="heroicon-o-cpu-chip" /></div>
            </div>
            <p class="ss-muted">Workers are filtered by category, town, availability, and rate. AI estimates depend on model availability and recorded history.</p>
            <dl class="ss-admin-model-facts">
                @foreach(['classification' => 'Category classification', 'recommendations' => 'Recommendation ranking', 'performance' => 'Worker predictions'] as $key => $label)
                    <div><dt>{{ $label }}</dt><dd>{{ str_replace('_', ' ', ucfirst($models[$key] ?? 'unavailable')) }}</dd></div>
                @endforeach
            </dl>
        </section>
    <div class="ss-admin-grid">@foreach($counts as $entity => $count)<a class="ss-stat ss-admin-stat" href="/admin/records?entity={{ $entity }}"><span class="ss-muted">{{ ucfirst($entity) }}</span><strong>{{ $count }}</strong><span>Inspect records &rarr;</span></a>@endforeach</div>
    <div class="ss-panel-columns"><section class="ss-card"><span class="ss-eyebrow">YOUR WORKSPACE</span><h2>One view of every interaction.</h2><p class="ss-muted">View customer requests, worker profiles, booking progress, and reviews. Counts above reflect current records.</p><a class="ss-btn" href="/admin/records">Explore records &rarr;</a></section><aside class="ss-card ss-soft-card"><h3>Administration</h3><p class="ss-muted">Update category descriptions and record worker verification decisions. Every verification change requires a note. Booking rules apply to everyone.</p></aside></div>
    </div>
</x-filament-panels::page>
