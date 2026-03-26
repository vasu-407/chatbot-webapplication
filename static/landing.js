const eyeGlow = document.getElementById("eyeGlow");
const typingInput =
  document.getElementById("input") ||
  document.getElementById("chatInput");
const robotZone = document.getElementById("robotZone");

/* Eye blink (idle) */
setInterval(() => {
  eyeGlow.style.opacity = "1.15";
  setTimeout(() => {
    eyeGlow.style.opacity = "5.0";
  }, 160);
}, 4000);

/* React while typing */
typingInput.addEventListener("input", () => {
  eyeGlow.style.opacity = "1";
  clearTimeout(window.eyeTimeout);

  window.eyeTimeout = setTimeout(() => {
    eyeGlow.style.opacity = "0.6";
  }, 600);
});

/* Mouse parallax */
document.addEventListener("mousemove", (e) => {
  const x = (window.innerWidth / 2 - e.clientX) / 40;
  const y = (window.innerHeight / 2 - e.clientY) / 40;
  robotZone.style.transform = `rotateY(${x}deg) rotateX(${y}deg)`;
});
/* SCROLL REVEAL */
const reveals = document.querySelectorAll(".reveal");

const observer = new IntersectionObserver(
  entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("show");
      }
    });
  },
  { threshold: 0.2 }
);

reveals.forEach(el => observer.observe(el));

