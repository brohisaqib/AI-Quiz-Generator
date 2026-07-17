import re

with open('C:/Users/Saqib Brohi/Desktop/Project/AI-Quiz-Generator/stitch_ai_quiz_generator_landing_page/stitch_ai_quiz_generator_landing_page/landing_page_desktop/code.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add html { scroll-behavior: smooth; }
content = content.replace('<style>', '<style>\n        html { scroll-behavior: smooth; }')

# 2. Add Mobile Menu at start of body
mobile_menu = """
<!-- Mobile Navigation Menu (Hidden by default) -->
<div class="fixed inset-0 z-[100] bg-surface flex flex-col items-center justify-center translate-x-full transition-transform duration-300 md:hidden" id="mobile-menu">
<button class="absolute top-6 right-margin-mobile text-on-surface" id="close-menu">
<span class="material-symbols-outlined text-[32px]">close</span>
</button>
<nav class="flex flex-col gap-stack-lg items-center text-center">
<a class="font-headline-sm text-headline-sm text-on-surface mobile-nav-link" href="#features">Features</a>
<a class="font-headline-sm text-headline-sm text-on-surface mobile-nav-link" href="#how-it-works">How It Works</a>
<a class="font-headline-sm text-headline-sm text-primary" href="/app">Log In</a>
<a class="px-stack-lg py-4 btn-gradient text-white font-bold rounded-lg shadow-lg" href="/app">Sign Up</a>
</nav>
</div>
"""
content = content.replace('<body class="font-body-md antialiased">', '<body class="font-body-md antialiased overflow-x-hidden">\n' + mobile_menu)

# 3. Add Hamburger Button to Desktop Nav
hamburger = """<button class="hidden md:block btn-gradient px-6 py-2.5 rounded-lg text-white font-bold scale-95 active:scale-90 transition-transform font-body-md text-body-md" onclick="window.location.href='/app'">Sign Up</button>
<button class="md:hidden text-on-surface ml-4" id="hamburger">
<span class="material-symbols-outlined text-[32px]">menu</span>
</button>"""
content = content.replace('<button class="btn-gradient px-6 py-2.5 rounded-lg text-white font-bold scale-95 active:scale-90 transition-transform font-body-md text-body-md">Sign Up</button>', hamburger)

# 4. Make Desktop Nav Log In clickable
content = content.replace('<button class="hidden md:block text-on-surface-variant font-medium hover:text-primary transition-colors duration-200 scale-95 active:scale-90 font-body-md text-body-md">Log In</button>', '<button class="hidden md:block text-on-surface-variant font-medium hover:text-primary transition-colors duration-200 scale-95 active:scale-90 font-body-md text-body-md" onclick="window.location.href=\'/app\'">Log In</button>')

# 6. Hero Get Started Free
content = content.replace('<button class="btn-gradient px-8 py-4 rounded-lg text-white font-bold text-body-lg">Get Started Free</button>', '<button class="btn-gradient px-8 py-4 rounded-lg text-white font-bold text-body-lg w-full md:w-auto" onclick="window.location.href=\'/app\'">Get Started Free</button>')

# 7. Hero See How It Works
content = content.replace('<button class="bg-transparent border border-white/20 px-8 py-4 rounded-lg text-white font-bold hover:bg-white/5 transition-colors text-body-lg flex items-center gap-2">', '<button class="bg-transparent border border-white/20 px-8 py-4 rounded-lg text-white font-bold hover:bg-white/5 transition-colors text-body-lg flex items-center justify-center gap-2 w-full md:w-auto" onclick="document.getElementById(\'how-it-works\').scrollIntoView({behavior: \'smooth\'})">')

# 8. Final Sign Up Free
content = content.replace('<button class="btn-gradient px-12 py-5 rounded-xl text-white font-bold text-headline-sm scale-100 hover:scale-105 active:scale-95 transition-all">Sign Up Free</button>', '<button class="btn-gradient px-12 py-5 rounded-xl text-white font-bold text-headline-sm scale-100 hover:scale-105 active:scale-95 transition-all w-full sm:w-auto" onclick="window.location.href=\'/app\'">Sign Up Free</button>')

# 9. Add Mobile Menu Scripts
scripts = """
        const hamburger = document.getElementById('hamburger');
        const closeMenu = document.getElementById('close-menu');
        const mobileMenu = document.getElementById('mobile-menu');

        if (hamburger && closeMenu && mobileMenu) {
            hamburger.addEventListener('click', () => {
                mobileMenu.classList.remove('translate-x-full');
            });

            closeMenu.addEventListener('click', () => {
                mobileMenu.classList.add('translate-x-full');
            });

            document.querySelectorAll('.mobile-nav-link').forEach(link => {
                link.addEventListener('click', () => {
                    mobileMenu.classList.add('translate-x-full');
                });
            });
        }
    </script>
"""
content = content.replace('</script>\n</body>', scripts + '</body>')

with open('C:/Users/Saqib Brohi/Desktop/Project/AI-Quiz-Generator/frontend/static/landing.html', 'w', encoding='utf-8') as f:
    f.write(content)
