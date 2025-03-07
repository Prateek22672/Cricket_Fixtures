// Splash screen logic
const splashScreen = document.getElementById('splash-screen');
splashScreen.style.display = 'flex'; // Show splash screen

setTimeout(() => {
    splashScreen.style.opacity = '0'; // Start fading out
    setTimeout(() => {
        splashScreen.style.display = 'none'; // Hide splash screen
    }, 1000); // Duration for fade-out transition
}, 1600); // Duration to show splash screen



Object.keys(pages).forEach(buttonId => {
    const btn = document.getElementById(buttonId);
    if (btn) {
        btn.addEventListener('click', function () {
            window.location.href = pages[buttonId];
        });
    }
});

// Retrieve the name and email from local storage
const name = localStorage.getItem('name');
const greetingElement = document.getElementById('allx');

// Display the appropriate greeting
if (name) {
    greetingElement.innerHTML = `Hello ${name},<br>`;
}
