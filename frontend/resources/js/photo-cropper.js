export function photoCropper(wire) {
    return {
        canvas: null, image: null, ready: false, busy: false, error: '',
        zoom: 1, horizontal: 50, vertical: 0, sequence: 0,
        async select(event) {
            const sequence = ++this.sequence;
            this.ready = false;
            this.image = null;
            this.error = '';
            const file = event.target.files[0];
            if (!file) return;
            if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 2 * 1024 * 1024) {
                this.error = 'Choose a JPG, PNG or WebP image up to 2 MB.';
                return;
            }
            const url = URL.createObjectURL(file);
            try {
                const image = new Image();
                image.src = url;
                await image.decode();
                if (sequence !== this.sequence) return;
                if (Math.min(image.naturalWidth, image.naturalHeight) < 64 || Math.max(image.naturalWidth, image.naturalHeight) > 8192 || image.naturalWidth * image.naturalHeight > 16000000) {
                    throw new Error('Choose a photo at least 64 × 64, up to 16 megapixels and 8192 pixels per side.');
                }
                this.image = image;
                this.resetPosition();
                this.ready = true;
            } catch (error) {
                if (sequence === this.sequence) this.error = error.message.startsWith('Choose') ? error.message : 'This image could not be opened. Please choose another photo.';
            } finally {
                URL.revokeObjectURL(url);
            }
        },
        resetPosition() {
            this.zoom = 1;
            this.horizontal = 50;
            this.vertical = 0;
            this.draw();
        },
        draw() {
            if (!this.image || !this.canvas) return;
            const side = Math.min(this.image.naturalWidth, this.image.naturalHeight) / Number(this.zoom);
            const left = (this.image.naturalWidth - side) * Number(this.horizontal) / 100;
            const top = (this.image.naturalHeight - side) * Number(this.vertical) / 100;
            const context = this.canvas.getContext('2d');
            context.fillStyle = '#ffffff';
            context.fillRect(0, 0, 512, 512);
            context.imageSmoothingEnabled = true;
            context.imageSmoothingQuality = 'high';
            context.drawImage(this.image, left, top, side, side, 0, 0, 512, 512);
        },
        cancel(input) {
            this.sequence++;
            this.ready = false;
            this.image = null;
            this.error = '';
            input.value = '';
        },
        async save(input) {
            if (!this.ready || this.busy) return;
            this.busy = true;
            this.error = '';
            try {
                this.draw();
                const blob = await new Promise(resolve => this.canvas.toBlob(resolve, 'image/png'));
                if (!blob) throw new Error('Could not prepare your photo. Please try again.');
                await new Promise((resolve, reject) => wire.upload('photo', new File([blob], 'profile-crop.png', { type: 'image/png' }), resolve, () => reject(new Error('Upload failed. Please try again.'))));
                if (await wire.uploadPhoto()) this.cancel(input);
            } catch (error) {
                this.error = error.message || 'Could not save your photo. Please try again.';
            } finally {
                this.busy = false;
            }
        },
    };
}

window.skillSyncPhotoCropper = photoCropper;
