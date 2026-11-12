const canvas = document.querySelector("#garden");
const ctx = canvas.getContext("2d");
const flowerName = document.querySelector("#flower");
const note = document.querySelector("#note");
const water = document.querySelector("#water");
const reset = document.querySelector("#reset");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
const view = { x: 230, y: 128, width: 540, height: 460 };
const lastFrame = bouquet.frames.length - 1;
let started = null;
let ready = false;
let selected = null;
let sparkleStarted = 0;
let animation;

function reveal(flower) {
  selected = flower;
  sparkleStarted = performance.now();
  flowerName.textContent = flower.name;
  note.textContent = flower.note;
  draw(sparkleStarted);
}

function draw(now) {
  cancelAnimationFrame(animation);
  const ratio = Math.min(window.devicePixelRatio || 1, 3);
  canvas.width = Math.round(view.width * ratio);
  canvas.height = Math.round(view.height * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, -view.x * ratio, -view.y * ratio);
  ctx.font = "9px Consolas, monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const age = started === null ? 0 : now - started;
  const index = started !== null && reducedMotion.matches
    ? lastFrame : Math.min(lastFrame, Math.floor(age / 100));
  const frame = bouquet.frames[index];
  for (let i = 0; i < frame.length; i += 4) {
    ctx.fillStyle = bouquet.colors[frame[i + 2]];
    ctx.fillText(bouquet.glyphs[frame[i + 3]], frame[i + 1] * 5, frame[i] * 6);
  }
  if (started === null) {
    ctx.fillStyle = "#fff2cf";
    ctx.fillText("*", 500, 549);
  } else if (age < 750 && !reducedMotion.matches) {
    ctx.fillStyle = "#a7dce6";
    for (let i = 0; i < 16; i++) {
      const fall = (age - i * 16) / 500;
      if (fall >= 0 && fall <= 1) ctx.fillText(":", 500 + Math.sin(i * 2.4) * 33, 456 + fall * fall * 109);
    }
  }
  if (started !== null && index === lastFrame && !ready) {
    ready = true;
    note.textContent = "Tap a bloom to find a little note.";
  }
  const sparkleAge = (now - sparkleStarted) / 750;
  const sparkling = selected && sparkleAge < 1 && !reducedMotion.matches;
  if (sparkling) {
    ctx.fillStyle = "#ffd2a4";
    ctx.globalAlpha = 1 - sparkleAge;
    for (let i = 0; i < 16; i++) {
      const angle = i * 2.4;
      const radius = (22 + i % 5 * 7) * sparkleAge;
      ctx.fillText(i % 2 ? "+" : "*", selected.x + Math.cos(angle) * radius,
                   selected.y + Math.sin(angle) * radius - 22 * sparkleAge);
    }
    ctx.globalAlpha = 1;
  }
  if ((started !== null && !ready) || sparkling) animation = requestAnimationFrame(draw);
}

function begin() {
  if (started !== null) return;
  started = performance.now();
  reset.disabled = false;
  note.textContent = "Your flowers are growing…";
  water.disabled = true;
  draw(started);
}

function clearGarden() {
  started = null;
  ready = false;
  selected = null;
  flowerName.textContent = "";
  note.textContent = "Water the seed to grow your bouquet.";
  water.disabled = false;
  reset.disabled = true;
  draw(performance.now());
}

canvas.addEventListener("click", event => {
  if (started === null) return begin();
  if (!ready) return;
  const bounds = canvas.getBoundingClientRect();
  const x = view.x + (event.clientX - bounds.left) * view.width / bounds.width;
  const y = view.y + (event.clientY - bounds.top) * view.height / bounds.height;
  let closest;
  let distance = Infinity;
  for (const flower of bouquet.flowers) {
    const delta = Math.hypot(x - flower.x, y - flower.y);
    if (delta <= flower.r && delta < distance) {
      closest = flower;
      distance = delta;
    }
  }
  if (closest) reveal(closest);
});
water.addEventListener("click", begin);
reset.addEventListener("click", clearGarden);
window.addEventListener("keydown", event => {
  if (event.target.closest("button")) return;
  if (event.code === "Space") {
    event.preventDefault();
    begin();
  } else if (event.key.toLowerCase() === "r") {
    clearGarden();
  }
});
window.addEventListener("resize", () => draw(performance.now()));
clearGarden();

