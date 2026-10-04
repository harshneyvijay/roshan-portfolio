(function () {
  var btn = document.getElementById("menuBtn"),
    nav = document.getElementById("nav");
  if (btn) {
    btn.addEventListener("click", function () {
      var o = nav.classList.toggle("open");
      btn.setAttribute("aria-expanded", o);
    });
    nav.addEventListener("click", function (e) {
      if (e.target.tagName === "A") {
        nav.classList.remove("open");
        btn.setAttribute("aria-expanded", "false");
      }
    });
  }
  var links = [].slice.call(document.querySelectorAll("nav a[data-s]"));
  function mark(id) {
    links.forEach(function (a) {
      var on = a.dataset.s === id;
      a.classList.toggle("on", on);
      on
        ? a.setAttribute("aria-current", "true")
        : a.removeAttribute("aria-current");
    });
  }
  var cur = document.body.dataset.section;
  if (cur && cur !== "home") {
    mark(cur);
  } else if ("IntersectionObserver" in window) {
    var secs = links
      .map(function (a) {
        return document.getElementById(a.dataset.s);
      })
      .filter(Boolean);
    var io = new IntersectionObserver(
      function (es) {
        es.forEach(function (e) {
          if (e.isIntersecting) mark(e.target.id);
        });
      },
      { rootMargin: "-40% 0px -55% 0px" },
    );
    secs.forEach(function (s) {
      io.observe(s);
    });
  }
  var rv = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    var ro = new IntersectionObserver(
      function (es) {
        es.forEach(function (e) {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            ro.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12 },
    );
    rv.forEach(function (r) {
      ro.observe(r);
    });
  } else
    rv.forEach(function (r) {
      r.classList.add("in");
    });
})();
