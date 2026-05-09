// ============================================
// ESWATINI CLASSIFIEDS - GLOBAL INTERACTIVITY
// ============================================

document.addEventListener('DOMContentLoaded', function () {
    
    // ============================================
    // SCROLL REVEAL ANIMATIONS
    // ============================================
    const revealElements = document.querySelectorAll('.scroll-reveal');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('revealed');
            }
        });
    }, { threshold: 0.1 });
    
    revealElements.forEach(el => observer.observe(el));
    
    // ============================================
    // CAROUSEL FUNCTIONALITY
    // ============================================
    const carousel = document.querySelector('.carousel-track');
    const container = document.querySelector('.carousel-container');
    
    if (carousel && container) {
        container.addEventListener('mouseenter', () => {
            carousel.style.animationPlayState = 'paused';
        });
        
        container.addEventListener('mouseleave', () => {
            carousel.style.animationPlayState = 'running';
        });
    }
    
    // ============================================
    // MOBILE MENU TOGGLE
    // ============================================
    const menuToggle = document.querySelector('.mobile-menu-toggle');
    const mobileMenu = document.querySelector('.mobile-menu');
    
    if (menuToggle && mobileMenu) {
        menuToggle.addEventListener('click', () => {
            mobileMenu.classList.toggle('active');
            menuToggle.classList.toggle('active');
        });
    }
    
    // ============================================
    // SMOOTH SCROLL FOR ANCHOR LINKS
    // ============================================
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#') {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
        });
    });
    
    // ============================================
    // IMAGE LAZY LOADING WITH FADE
    // ============================================
    const lazyImages = document.querySelectorAll('img[loading="lazy"]');
    
    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.classList.add('loaded');
                imageObserver.unobserve(img);
            }
        });
    });
    
    lazyImages.forEach(img => {
        img.classList.add('loading');
        imageObserver.observe(img);
    });
    
    // ============================================
    // QUANTITY INPUT SPINNERS
    // ============================================
    document.querySelectorAll('.quantity-input').forEach(input => {
        const decrease = input.parentElement.querySelector('.quantity-decrease');
        const increase = input.parentElement.querySelector('.quantity-increase');
        
        if (decrease) {
            decrease.addEventListener('click', () => {
                const val = parseInt(input.value) || 0;
                if (val > 1) input.value = val - 1;
            });
        }
        
        if (increase) {
            increase.addEventListener('click', () => {
                const val = parseInt(input.value) || 0;
                input.value = val + 1;
            });
        }
    });
    
    // ============================================
    // TOAST NOTIFICATIONS
    // ============================================
    window.showToast = function (message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icon = type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-times-circle' : 'fa-info-circle';
        
        toast.innerHTML = `
            <i class="fas ${icon}"></i>
            <span>${message}</span>
            <button onclick="this.parentElement.remove()">&times;</button>
        `;
        
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3A75C4'};
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            display: flex;
            align-items: center;
            gap: 0.75rem;
            z-index: 9999;
            font-weight: 500;
            max-width: 350px;
        `;
        
        document.body.appendChild(toast);
        
        // Auto-remove after 4 seconds
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    };
    
    // ============================================
    // FORM VALIDATION HIGHLIGHT
    // ============================================
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function (e) {
            const required = this.querySelectorAll('[required]');
            let isValid = true;
            
            required.forEach(field => {
                if (!field.value.trim()) {
                    field.classList.add('border-red-500');
                    field.classList.add('bg-red-50');
                    isValid = false;
                } else {
                    field.classList.remove('border-red-500');
                    field.classList.remove('bg-red-50');
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                showToast('Please fill in all required fields', 'error');
            }
        });
    });
    
    // ============================================
    // CHARACTER COUNTER FOR TEXTAREAS
    // ============================================
    document.querySelectorAll('[data-max-chars]').forEach(textarea => {
        const maxChars = parseInt(textarea.dataset.maxChars);
        const counter = document.createElement('div');
        counter.className = 'char-counter';
        counter.style.cssText = 'text-align: right; font-size: 0.75rem; color: #64748b; margin-top: 0.25rem;';
        textarea.parentElement.appendChild(counter);
        
        const updateCounter = () => {
            const remaining = maxChars - textarea.value.length;
            counter.textContent = `${textarea.value.length} / ${maxChars} characters`;
            counter.style.color = remaining < 0 ? '#ef4444' : '#64748b';
        };
        
        textarea.addEventListener('input', updateCounter);
        updateCounter();
    });
    
    // ============================================
    // PRICE FORMATTER
    // ============================================
    window.formatPrice = function (price, currency = 'SZL') {
        return new Intl.NumberFormat('en-SZ', {
            style: 'currency',
            currency: currency
        }).format(price);
    };
    
    // ============================================
    // DEBOUNCE FUNCTION FOR SEARCH
    // ============================================
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Live search with debounce
    const searchInput = document.querySelector('.search-input');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function (e) {
            const query = e.target.value.trim();
            if (query.length >= 2) {
                fetchSearchSuggestions(query);
            } else {
                // Remove suggestions if query is too short
                const dropdown = document.querySelector('.search-suggestions');
                if (dropdown) dropdown.remove();
            }
        }, 300));
    }

    // Fetch search suggestions
    function fetchSearchSuggestions(query) {
        fetch(`/api/search/suggestions?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                displaySuggestions(data);
            })
            .catch(error => {
                console.error('Search error:', error);
                // Fallback: show nothing on error
            });
    }
    
    // Display search suggestions dropdown
    function displaySuggestions(suggestions) {
        // Remove existing dropdown
        const existing = document.querySelector('.search-suggestions');
        if (existing) existing.remove();
        
        if (!suggestions || suggestions.length === 0) return;
        
        // Create suggestions dropdown
        const dropdown = document.createElement('div');
        dropdown.className = 'search-suggestions absolute top-full left-0 right-0 bg-white border rounded-lg shadow-lg mt-1 z-50 max-h-60 overflow-y-auto';
        
        suggestions.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = `px-4 py-2.5 hover:bg-blue-50 cursor-pointer text-sm flex items-center gap-3 transition ${index < suggestions.length - 1 ? 'border-b' : ''}`;
            
            const icon = item.category === 'employment' ? 'fa-briefcase' : 
                        item.category === 'motors' ? 'fa-car' : 
                        item.category === 'property' ? 'fa-home' : 
                        item.category === 'services' ? 'fa-tools' : 'fa-box';
            
            div.innerHTML = `
                <i class="fas ${icon} text-gray-400 w-5"></i>
                <div class="flex-1">
                    <p class="font-medium text-gray-800">${item.title.substring(0, 50)}</p>
                    <p class="text-xs text-gray-500">${item.location_city || 'Eswatini'} · ${item.category || 'General'}</p>
                </div>
                ${item.salary_price ? `<span class="text-blue-600 font-semibold text-xs">${item.salary_price}</span>` : ''}
            `;
            
            div.addEventListener('click', () => {
                if (item.id) {
                    window.location.href = `/ad/${item.id}`;
                } else {
                    searchInput.value = item.title;
                    dropdown.remove();
                    searchInput.closest('form').submit();
                }
            });
            
            dropdown.appendChild(div);
        });
        
        searchInput.parentElement.style.position = 'relative';
        searchInput.parentElement.appendChild(dropdown);
        
        // Close dropdown when clicking outside
        document.addEventListener('click', function closeDropdown(e) {
            if (!e.target.closest('.search-input-wrapper')) {
                dropdown.remove();
                document.removeEventListener('click', closeDropdown);
            }
        });
        
        // Close dropdown on Escape key
        document.addEventListener('keydown', function closeOnEscape(e) {
            if (e.key === 'Escape') {
                dropdown.remove();
                document.removeEventListener('keydown', closeOnEscape);
            }
        });
    }

});

// ============================================
// LOGOUT CONFIRMATION
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    const logoutLinks = document.querySelectorAll('a[href*="logout"]');
    logoutLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to sign out?')) {
                e.preventDefault();
            }
        });
    });
});