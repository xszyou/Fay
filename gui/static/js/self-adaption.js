window.onload = function () {
  document.body.style.zoom = "normal";//避免zoom尺寸叠加
  let scale = document.body.clientWidth / 1920;
  document.body.style.zoom = scale;
}; (function () {
    var throttle = function (type, name, obj) {
      obj = obj || window;
      var running = false;
      var func = function () {
        if (running) { return; }
        running = true;
        requestAnimationFrame(function () {
          obj.dispatchEvent(new CustomEvent(name));
          running = false;
        });
      };
      obj.addEventListener(type, func);
    };
    throttle("resize", "optimizedResize");
  })();
window.addEventListener("optimizedResize", function () {
  document.body.style.zoom = "normal";
  let scale = document.body.clientWidth / 1920;
  document.body.style.zoom = scale;
});