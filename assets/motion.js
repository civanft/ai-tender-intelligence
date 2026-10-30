// Page motion: reveal content as it scrolls in, count figures up, grow bars,
// and slide the tab underline. It plays once per visit to a tab; reruns caused
// by filters or typing update in place without replaying anything.

const REVEAL = [
  ".figure", ".notice-line", ".theme-row", ".market-row", ".fit-summary > div",
  ".registry-list__row", ".fit-row", ".method-steps li", ".research-checks > div",
  ".dossier", ".page-intro", ".section-head", ".view-summary", ".market-ledger tr",
  ".limits-note", '[class*="st-key-related_"]', ".research-metrics > div",
  '[data-testid="stPlotlyChart"]', ".buyer-identity",
].join(",");
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

function install() {
  const motion = { page: null, playUntil: 0 };
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      io.unobserve(entry.target);
      entry.target.classList.add("tm-in");
      const figure = entry.target.matches(".figure") && entry.target.querySelector("strong");
      if (figure) countUp(figure);
    });
  }, { rootMargin: "0px 0px -6% 0px", threshold: 0.01 });

  // Siblings arrive together; give each a short, capped stagger.
  function scan() {
    const fresh = [...document.querySelectorAll(REVEAL)].filter((el) => !el.dataset.tm);
    if (!fresh.length) return;
    const play = !REDUCED && performance.now() < motion.playUntil;
    const order = new Map();
    fresh.forEach((el) => {
      el.dataset.tm = "1";
      if (!play) return;
      const parent = el.parentElement;
      const index = order.get(parent) || 0;
      order.set(parent, index + 1);
      el.style.setProperty("--tm-d", `${Math.min(index * 45, 540)}ms`);
      el.classList.add("tm-reveal");
      io.observe(el);
    });
    if (play) setTimeout(() => fresh.forEach((el) => el.classList.add("tm-in")), 4000);
  }

  function countUp(el) {
    const final = el.textContent;
    const parts = final.split(/(\d[\d,]*\.?\d*)/);
    const numbers = parts.map((p) => (/^\d/.test(p) ? parseFloat(p.replace(/,/g, "")) : null));
    if (!numbers.some((n) => n !== null)) return;
    const start = performance.now(), dur = 1100;
    const decimals = parts.map((p) => (/\./.test(p) && /^\d/.test(p) ? p.split(".")[1].length : 0));
    const step = (now) => {
      const t = Math.min(1, (now - start) / dur), k = 1 - Math.pow(2, -10 * t);
      if (t >= 1) { el.textContent = final; return; }
      el.textContent = parts.map((p, i) => (numbers[i] === null ? p
        : (numbers[i] * k).toLocaleString("en-GB", { minimumFractionDigits: decimals[i], maximumFractionDigits: decimals[i] }))).join("");
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  // A single underline that travels between tabs.
  function placeInk(animate) {
    const group = document.querySelector('.st-key-workspace_page [role="radiogroup"]');
    if (!group) return;
    let ink = group.querySelector(".tm-tab-ink");
    if (!ink) {
      ink = document.createElement("span");
      ink.className = "tm-tab-ink"; ink.setAttribute("aria-hidden", "true");
      group.appendChild(ink); group.classList.add("tm-has-ink"); animate = false;
    }
    const checked = [...group.querySelectorAll("label")].find((label) => label.querySelector("input:checked"));
    if (!checked) return;
    ink.classList.toggle("tm-tab-ink--still", !animate);
    ink.style.width = `${checked.offsetWidth}px`;
    ink.style.transform = `translateX(${checked.offsetLeft}px)`;
  }

  let queued = false;
  const observer = new MutationObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; scan(); placeInk(true); });
  });
  observer.observe(document.body, { childList: true, subtree: true });
  addEventListener("resize", () => placeInk(false));

  motion.visit = (page) => {
    if (page === motion.page) return;
    motion.page = page;
    motion.playUntil = performance.now() + 2500;
    // Content of the previous tab is gone; anything new on this one may play.
    document.querySelectorAll("[data-tm]").forEach((el) => { if (!el.classList.contains("tm-reveal")) delete el.dataset.tm; });
    scan(); placeInk(true);
  };
  return motion;
}

export default function (component) {
  const page = component.data && component.data.page;
  window.__tmMotion = window.__tmMotion || install();
  window.__tmMotion.visit(page);
}
