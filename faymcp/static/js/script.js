const menu = document.querySelector('.menu');
const prevButton = document.getElementById('prevButton');
const nextButton = document.getElementById('nextButton');

const slideDistance = 500;
let currentTranslate = 0;  

function updateButtons() {
    prevButton.disabled = currentTranslate === 0;
    nextButton.disabled = currentTranslate <= -(menu.scrollWidth - menu.clientWidth);
}

prevButton.addEventListener('click', () => {
    if (menu.scrollWidth > menu.clientWidth) { 
        currentTranslate = Math.min(currentTranslate + slideDistance, 0); 
        menu.style.transform = `translateX(${currentTranslate}px)`;
        updateButtons();
    }
});

nextButton.addEventListener('click', () => {
    if (menu.scrollWidth > menu.clientWidth) { 
        currentTranslate = Math.max(currentTranslate - slideDistance, -(menu.scrollWidth - menu.clientWidth)); 
        menu.style.transform = `translateX(${currentTranslate}px)`;
        updateButtons();
    }
});

updateButtons();  
