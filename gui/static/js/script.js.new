// 定义变量
const slideDistance = 500;
let currentTranslate = 0;
let menu, prevButton, nextButton;

function updateButtons() {
    if (!prevButton || !nextButton || !menu) return;
    prevButton.disabled = currentTranslate === 0;
    nextButton.disabled = currentTranslate <= -(menu.scrollWidth - menu.clientWidth);
}

function initializeSlider() {
    // 获取DOM元素
    menu = document.querySelector('.menu');
    prevButton = document.getElementById('prevButton');
    nextButton = document.getElementById('nextButton');
    
    // 确保所有元素都存在
    if (!menu || !prevButton || !nextButton) return;
    
    // 添加事件监听
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
    
    // 初始化按钮状态
    updateButtons();
}

// 在DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', initializeSlider);
