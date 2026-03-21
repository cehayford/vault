/**
 * High-level message handling system for consistent user notifications
 * Replaces scattered timeout logic across templates
 */

class MessageHandler {
    constructor() {
        this.defaultDuration = 8000; // 8 seconds for better readability
        this.init();
    }

    init() {
        // Handle Django messages (toast notifications)
        this.setupDjangoMessages();
        
        // Handle form errors (error alerts)
        this.setupFormErrors();
        
        // Handle success alerts
        this.setupSuccessAlerts();
    }

    setupDjangoMessages() {
        const toasts = document.querySelectorAll('.toast-notification');
        toasts.forEach(toast => {
            const duration = Number(toast.dataset.duration) || this.defaultDuration;
            this.autoDismiss(toast, duration);
        });

        const successAlerts = document.querySelectorAll('.success-alert');
        successAlerts.forEach(alert => {
            const duration = Number(alert.dataset.duration) || this.defaultDuration;
            this.autoDismiss(alert, duration);
        });
    }

    setupFormErrors() {
        const errorAlerts = document.querySelectorAll('#errorAlert');
        errorAlerts.forEach(alert => {
            // Form errors should stay longer for users to read
            this.autoDismiss(alert, this.defaultDuration);
        });

        // Field-level errors
        const fieldErrors = document.querySelectorAll('.field-error');
        fieldErrors.forEach(error => {
            // Field errors should persist until user interacts
            this.setupFieldErrorDismissal(error);
        });
    }

    setupSuccessAlerts() {
        const successAlerts = document.querySelectorAll('.success-alert');
        successAlerts.forEach(alert => {
            this.autoDismiss(alert, this.defaultDuration);
        });
    }

    autoDismiss(element, duration) {
        if (!element) return;
        
        // Add entrance animation
        element.classList.add('message-enter');
        
        // Set up auto-dismissal
        setTimeout(() => {
            element.classList.add('message-exit');
            setTimeout(() => {
                if (element.parentElement) {
                    element.remove();
                }
            }, 300); // Exit animation duration
        }, duration);
    }

    setupFieldErrorDismissal(fieldError) {
        // Field errors should dismiss on user interaction
        const dismissOnEvents = ['input', 'focus', 'change'];
        
        const dismissHandler = () => {
            fieldError.classList.add('message-exit');
            setTimeout(() => {
                if (fieldError.parentElement) {
                    fieldError.remove();
                }
            }, 300);
            
            // Clean up event listeners
            dismissOnEvents.forEach(event => {
                fieldError.removeEventListener(event, dismissHandler);
            });
        };

        dismissOnEvents.forEach(event => {
            fieldError.addEventListener(event, dismissHandler);
        });

        // Also add manual dismiss button
        this.addDismissButton(fieldError);
    }

    addDismissButton(element) {
        if (!element || element.querySelector('.dismiss-btn')) return;

        const dismissBtn = document.createElement('button');
        dismissBtn.className = 'dismiss-btn absolute top-2 right-2 text-muted hover:text-foreground p-1 transition-colors duration-fast';
        dismissBtn.innerHTML = `
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
            </svg>
        `;
        dismissBtn.setAttribute('aria-label', 'Dismiss message');
        dismissBtn.onclick = () => {
            element.classList.add('message-exit');
            setTimeout(() => {
                if (element.parentElement) {
                    element.remove();
                }
            }, 300);
        };

        element.style.position = 'relative';
        element.appendChild(dismissBtn);
    }

    // Public method to manually show messages
    showMessage(message, type = 'info', duration = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message-alert card px-6 py-4 bg-surface-card border-border ${type === 'error' ? 'bg-secondary border-accent/30' : ''}`;
        messageDiv.setAttribute('role', 'alert');
        
        messageDiv.innerHTML = `
            <div class="flex items-start">
                <div class="flex-shrink-0 mr-3">
                    ${type === 'success' ? '<i data-lucide="check-circle" class="w-5 h-5 text-accent"></i>' : 
                      type === 'error' ? '<i data-lucide="alert-circle" class="w-5 h-5 text-accent"></i>' : 
                      '<i data-lucide="info" class="w-5 h-5 text-accent"></i>'}
                </div>
                <div class="text-sm text-foreground">${message}</div>
            </div>
        `;

        // Add to container
        let container = document.getElementById('toastContainer') || document.body;
        container.appendChild(messageDiv);
        
        // Auto-dismiss
        this.autoDismiss(messageDiv, duration || this.defaultDuration);
        
        return messageDiv;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.messageHandler = new MessageHandler();
});

// Global function for backward compatibility
function dismissError() {
    const errorAlert = document.getElementById('errorAlert');
    if (errorAlert) {
        errorAlert.classList.add('message-exit');
        setTimeout(() => {
            if (errorAlert.parentElement) {
                errorAlert.remove();
            }
        }, 300);
    }
}
