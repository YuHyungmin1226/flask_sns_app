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

/**
 * 구글 드라이브 비디오 동적 로드 (클릭-투-플레이 플레이스홀더)
 * @param {HTMLElement} wrapper - 비디오 프리뷰 래퍼 요소
 * @param {string} fileId - 구글 드라이브 파일 ID
 */
function loadEmbeddedVideo(wrapper, fileId) {
    const iframe = document.createElement('iframe');
    iframe.src = `https://drive.google.com/file/d/${fileId}/preview?autoplay=1`;
    iframe.className = 'w-100 h-100 border-0 animate__animated animate__fadeIn';
    iframe.allow = 'autoplay; fullscreen';
    iframe.setAttribute('allowfullscreen', 'true');
    
    wrapper.innerHTML = '';
    wrapper.removeAttribute('onclick'); // 중복 호출 방지
    wrapper.appendChild(iframe);
}
