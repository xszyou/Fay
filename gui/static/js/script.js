const menu = document.querySelector('.menu');
const prevButton = document.getElementById('prevButton');
const nextButton = document.getElementById('nextButton');

// 每次滑动的距离，可根据菜单项宽度和间距等实际情况调整
const slideDistance = 500;

prevButton.addEventListener('click', () => {
    menu.style.transform = `translateX(${slideDistance}px)`;
});

nextButton.addEventListener('click', () => {
    menu.style.transform = `translateX(-${slideDistance}px)`;
});