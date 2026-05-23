// Flask SNS Global JavaScript

/**
 * 전역 토스트 알림 표시 함수
 * @param {string} message - 표시할 메시지
 * @param {string} type - 알림 타입 (success, danger, warning, info)
 */
function showToast(message, type = 'info') {
    let toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastContainer';
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        toastContainer.style.zIndex = '1080';
        document.body.appendChild(toastContainer);
    }

    const toastId = 'toast-' + Date.now();
    const typeClass = type === 'error' ? 'danger' : type;
    
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-white bg-${typeClass} border-0 shadow-lg" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    <div class="d-flex align-items-center">
                        <i class="bi bi-${getIconForType(typeClass)} me-2"></i>
                        <span>${message}</span>
                    </div>
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;

    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { delay: 4000 });
    toast.show();

    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

function getIconForType(type) {
    switch(type) {
        case 'success': return 'check-circle-fill';
        case 'danger': return 'exclamation-circle-fill';
        case 'warning': return 'exclamation-triangle-fill';
        default: return 'info-circle-fill';
    }
}

// 폼 처리를 위한 공통 AJAX 라이브러리 (필요시 확장)
window.SNS = {
    showToast: showToast,
    
    /**
     * CSRF 토큰 가져오기
     */
    getCsrfToken: function() {
        return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    }
};
