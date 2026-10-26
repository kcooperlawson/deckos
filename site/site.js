// DecKoOS website: the few things that need a script. Everything still reads without it.
(() => {
  const menu = document.querySelector(".menu-toggle");
  const nav = document.querySelector(".nav");
  if (menu && nav) {
    menu.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      menu.setAttribute("aria-expanded", open);
    });
  }

  // Screenshot tabs
  document.querySelectorAll("[data-tabs]").forEach((root) => {
    const tabs = [...root.querySelectorAll(".tab")];
    const shots = [...root.querySelectorAll(".shot")];
    const pick = (i) => {
      tabs.forEach((t, j) => t.setAttribute("aria-selected", i === j));
      shots.forEach((s, j) => s.classList.toggle("active", i === j));
    };
    tabs.forEach((t, i) => {
      t.addEventListener("click", () => pick(i));
      t.addEventListener("keydown", (e) => {
        if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
        const n = (i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length;
        tabs[n].focus();
        pick(n);
      });
    });
  });

  // Copy buttons: on code blocks, and anything with data-copy
  const copy = async (btn, text) => {
    try {
      await navigator.clipboard.writeText(text);
      const old = btn.innerHTML;
      btn.classList.add("done");
      btn.textContent = "Copied";
      setTimeout(() => { btn.classList.remove("done"); btn.innerHTML = old; }, 1600);
    } catch (e) { /* no clipboard (http on another host): the text is still selectable */ }
  };
  document.querySelectorAll(".prose pre").forEach((pre) => {
    const b = document.createElement("button");
    b.className = "copy";
    b.type = "button";
    b.textContent = "Copy";
    b.addEventListener("click", () => copy(b, pre.querySelector("code").innerText));
    pre.appendChild(b);
  });
  document.querySelectorAll("[data-copy]").forEach((b) => b.addEventListener("click", () => copy(b, b.dataset.copy)));

  // Screenshots open full size
  const box = document.createElement("div");
  box.className = "lightbox";
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-label", "Screenshot");
  const big = document.createElement("img");
  big.alt = "";
  box.appendChild(big);
  document.body.appendChild(box);
  const close = () => box.classList.remove("open");
  box.addEventListener("click", close);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  document.querySelectorAll("img[data-zoom]").forEach((img) => img.addEventListener("click", () => {
    big.src = img.dataset.zoom || img.src;
    big.alt = img.alt;
    box.classList.add("open");
  }));

  // On this page: follow the reader
  const links = [...document.querySelectorAll(".toc a")];
  if (links.length && "IntersectionObserver" in window) {
    const byId = new Map(links.map((a) => [decodeURIComponent(a.hash.slice(1)), a]));
    const seen = new Set();
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => (e.isIntersecting ? seen.add(e.target.id) : seen.delete(e.target.id)));
      const first = [...byId.keys()].find((id) => seen.has(id));
      if (first) links.forEach((a) => a.classList.toggle("on", a === byId.get(first)));
    }, { rootMargin: "-80px 0px -65% 0px" });
    byId.forEach((_, id) => { const h = document.getElementById(id); if (h) io.observe(h); });
  }
})();
