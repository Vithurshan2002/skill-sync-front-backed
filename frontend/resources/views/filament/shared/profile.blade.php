<x-filament-panels::page>
    <div class="ss-panel-columns {{ isset($workerReview) ? 'ss-worker-profile' : 'ss-customer-profile' }}">
        <section class="{{ isset($workerReview) ? 'ss-worker-profile-form' : 'ss-customer-profile-form' }}">
            @include('filament.shared.error')
            @if(isset($workerReview))
                <section class="ss-card ss-photo-editor" aria-labelledby="worker-photo-heading">
                    <div class="ss-photo-heading"><span class="ss-icon-tile"><x-icon name="heroicon-o-camera" /></span><div><h2 id="worker-photo-heading">Profile photo</h2></div><span class="ss-photo-optional">Optional</span></div>
                    <div class="ss-photo-form" x-data="{ crop: null }" x-init="await import('{{ Vite::asset('resources/js/photo-cropper.js') }}'); crop = window.skillSyncPhotoCropper($wire); crop.canvas = $refs.cropCanvas">
                        <div class="ss-photo-upload-row">
                            <div class="ss-photo-editor-preview"><x-worker-avatar :worker="$workerReview" class="ss-avatar-large" /></div>
                            <div class="ss-photo-upload-copy">
                                <label for="worker-photo">Choose a photo</label>
                                <input id="worker-photo" x-ref="photoInput" type="file" accept="image/jpeg,image/png,image/webp" x-on:change="crop?.select($event)" x-bind:disabled="!crop || crop.busy" aria-describedby="worker-photo-help worker-photo-error">
                                <p id="worker-photo-help">JPG, PNG or WebP &middot; Max 2 MB</p>
                            </div>
                        </div>
                        <div class="ss-photo-crop" x-show="crop?.ready" x-cloak wire:ignore>
                            <div class="ss-photo-crop-preview">
                                <canvas x-ref="cropCanvas" width="512" height="512" role="img" aria-label="Square photo crop preview"></canvas>
                            </div>
                            <fieldset class="ss-photo-crop-controls" x-bind:disabled="crop?.busy">
                                <legend>Adjust your photo</legend>
                                <label for="photo-zoom">Zoom</label>
                                <input id="photo-zoom" type="range" min="1" max="3" step="0.01" value="1" x-bind:value="crop?.zoom" x-on:input="crop.zoom = $event.target.value; crop.draw()">
                                <label for="photo-horizontal">Horizontal position</label>
                                <input id="photo-horizontal" type="range" min="0" max="100" value="50" x-bind:value="crop?.horizontal" x-on:input="crop.horizontal = $event.target.value; crop.draw()">
                                <label for="photo-vertical">Vertical position</label>
                                <input id="photo-vertical" type="range" min="0" max="100" value="0" x-bind:value="crop?.vertical" x-on:input="crop.vertical = $event.target.value; crop.draw()">
                                <div class="ss-photo-actions">
                                    <button type="button" class="ss-text-link" x-on:click="crop.resetPosition()">Reset crop</button>
                                    <button type="button" class="ss-text-link" x-on:click="crop.cancel($refs.photoInput)">Cancel selection</button>
                                </div>
                            </fieldset>
                        </div>
                        <p class="ss-field-error" x-show="crop?.error" x-text="crop?.error" role="alert" x-cloak></p>
                        <div id="worker-photo-error">@error('photo')<p class="ss-field-error" role="alert">{{ $message }}</p>@enderror</div>
                        <div class="ss-photo-footer">
                            <p>Visible on your public profile.</p>
                            <div class="ss-photo-actions">
                                @if($workerReview['photoUrl'] ?? null)<span x-show="!crop?.ready">{{ $this->removePhotoAction }}</span>@endif
                                <x-filament::button type="button" x-bind:disabled="!crop?.ready || crop?.busy" x-on:click="crop.save($refs.photoInput)">
                                    <span x-text="crop?.busy ? 'Saving photo...' : 'Save photo'">Save photo</span>
                                </x-filament::button>
                            </div>
                        </div>
                    </div>
                </section>
            @endif
            <form wire:submit="save" class="ss-form">
                {{ $this->form }}
                <div class="ss-form-actions {{ isset($workerReview) ? 'ss-profile-save-actions' : 'ss-customer-save-actions' }}">
                    @if(isset($workerReview))
                        <p class="ss-profile-save-status" role="status" aria-live="polite" aria-atomic="true">
                            {{ match($workerReview['approvalStatus'] ?? 'pending') {
                                'approved' => $profileSaved ? 'Profile saved.' : 'Profile approved.',
                                'changes_requested' => 'Changes requested. ' . (($workerReview['reviewNote'] ?? null) ?: 'Update your profile and save again.'),
                                default => ($workerReview['reviewReady'] ?? false) ? 'Request sent. Waiting for admin approval.' : 'Complete your profile and save to request approval.',
                            } }}
                        </p>
                    @else
                        <p class="ss-small ss-muted">Save your changes to update your account details.</p>
                    @endif
                    <x-filament::button type="submit" wire:loading.attr="disabled" wire:target="save">
                        <span wire:loading.remove wire:target="save">Save profile</span>
                        <span wire:loading wire:target="save">Saving&hellip;</span>
                    </x-filament::button>
                </div>
            </form>
        </section>
        @if(isset($workerReview))
        <aside class="ss-card ss-worker-profile-guide" aria-labelledby="profile-guide-title">
            <div class="ss-worker-profile-identity">
                <x-worker-avatar :worker="$workerReview" />
                <div><h2>{{ auth()->user()->name }}</h2><span>Worker profile</span></div>
            </div>
            <h3 id="profile-guide-title">Help customers choose you</h3>
            <p>A clear profile helps customers understand what you offer.</p>
            <ul class="ss-worker-profile-tips">
                <li><x-icon name="heroicon-o-pencil-square" /><div><strong>Describe your skills</strong><p>Mention the jobs you handle and your experience.</p></div></li>
                <li><x-icon name="heroicon-o-map-pin" /><div><strong>Check your service area</strong><p>Keep your towns and travel radius up to date.</p></div></li>
                <li><x-icon name="heroicon-o-calendar-days" /><div><strong>Keep availability current</strong><p>Let customers know when you can take new jobs.</p></div></li>
            </ul>
            @if($workerReview['verified'] ?? false)
                <a class="ss-button ss-button-secondary" href="/workers/{{ auth()->user()->worker_id }}">Preview public profile <x-icon name="heroicon-o-arrow-up-right" /></a>
            @endif
        </aside>
        @else
        <aside class="ss-card ss-customer-profile-guide" aria-labelledby="customer-profile-guide-title">
            <div class="ss-customer-profile-identity">
                <div class="ss-avatar" aria-hidden="true">{{ collect(explode(' ', auth()->user()->name))->filter()->take(2)->map(fn($part) => mb_substr($part, 0, 1))->join('') }}</div>
                <div><h2>{{ auth()->user()->name }}</h2><span>Customer account</span></div>
            </div>
            <h3 id="customer-profile-guide-title">Make booking coordination easier</h3>
            <p>Accurate contact details help professionals coordinate the work with you.</p>
            <ul class="ss-customer-profile-tips">
                <li><x-icon name="heroicon-o-phone" /><div><strong>Add a reachable phone number</strong><p>It gives your professional another way to coordinate the job.</p></div></li>
                <li><x-icon name="heroicon-o-chat-bubble-left-right" /><div><strong>Choose how to be contacted</strong><p>Your preference helps set expectations before a booking.</p></div></li>
                <li><x-icon name="heroicon-o-map-pin" /><div><strong>Keep your town current</strong><p>Your town can help with local service requests.</p></div></li>
            </ul>
        </aside>
        @endif
    </div>
</x-filament-panels::page>
