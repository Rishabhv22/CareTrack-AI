document.addEventListener('DOMContentLoaded', function() {
    // Theme Mode Toggle Mechanic
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    const themeIcon = document.getElementById('themeIcon');
    
    if (themeToggleBtn && themeIcon) {
        // Toggle theme action
        themeToggleBtn.addEventListener('click', function() {
            const currentTheme = document.documentElement.getAttribute('data-bs-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            // Set theme on HTML node
            document.documentElement.setAttribute('data-bs-theme', newTheme);
            localStorage.setItem('caretrack-theme', newTheme);
            
            // Update icon representation
            updateThemeIcon(newTheme);
        });
        
        // Initial icon update based on current mode
        const activeTheme = document.documentElement.getAttribute('data-bs-theme') || 'light';
        updateThemeIcon(activeTheme);
    }
    
    function updateThemeIcon(theme) {
        if (theme === 'dark') {
            themeIcon.className = 'bi bi-moon-stars-fill fs-5 text-warning';
        } else {
            themeIcon.className = 'bi bi-sun-fill fs-5 text-secondary';
        }
    }
});
