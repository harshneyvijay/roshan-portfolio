(function () {
  var b = document.getElementById("sideBtn"),
    s = document.getElementById("side");
  if (b)
    b.addEventListener("click", function () {
      var o = s.classList.toggle("open");
      b.setAttribute("aria-expanded", o);
    });
  document.querySelectorAll("form[data-confirm]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!confirm(f.dataset.confirm)) e.preventDefault();
    });
  });
})();
