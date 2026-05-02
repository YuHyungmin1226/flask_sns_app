const PushNotifications = {
    swRegistration: null,
    isSubscribed: false,

    async init() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            console.warn('Push messaging is not supported');
            return;
        }

        try {
            const registration = await navigator.serviceWorker.register('/static/sw.js');
            console.log('Service Worker is registered', registration);
            this.swRegistration = registration;
            
            this.updateSubscriptionStatus();
        } catch (error) {
            console.error('Service Worker Error', error);
        }
    },

    async updateSubscriptionStatus() {
        if (!this.swRegistration) return;
        
        const subscription = await this.swRegistration.pushManager.getSubscription();
        this.isSubscribed = !(subscription === null);
        
        if (this.isSubscribed) {
            console.log('User IS subscribed.');
        } else {
            console.log('User is NOT subscribed.');
        }
        
        // Dispatch custom event to update UI if needed
        document.dispatchEvent(new CustomEvent('push-status-changed', { 
            detail: { isSubscribed: this.isSubscribed } 
        }));
    },

    async subscribeUser() {
        const response = await fetch('/push-key');
        const data = await response.json();
        const publicKey = data.public_key;
        const applicationServerKey = this.urlB64ToUint8Array(publicKey);

        try {
            const subscription = await this.swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            });

            console.log('User is subscribed:', subscription);
            await this.saveSubscription(subscription);
            this.isSubscribed = true;
            this.updateSubscriptionStatus();
            return true;
        } catch (error) {
            console.error('Failed to subscribe the user: ', error);
            return false;
        }
    },

    async unsubscribeUser() {
        try {
            const subscription = await this.swRegistration.pushManager.getSubscription();
            if (subscription) {
                await subscription.unsubscribe();
                await this.deleteSubscription(subscription);
                console.log('User is unsubscribed.');
                this.isSubscribed = false;
                this.updateSubscriptionStatus();
            }
        } catch (error) {
            console.error('Error unsubscribing', error);
        }
    },

    async saveSubscription(subscription) {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        await fetch('/subscribe', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(subscription)
        });
    },

    async deleteSubscription(subscription) {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        await fetch('/unsubscribe', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(subscription)
        });
    },

    urlB64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/\-/g, '+')
            .replace(/_/g, '/');

        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);

        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }
};

document.addEventListener('DOMContentLoaded', () => {
    PushNotifications.init();
});
