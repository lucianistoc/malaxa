// Content data — edit here to update the homepage cards.
const specialties = [
  { icon: "🩺", name: "Ambulatoriu integrat", desc: "Consultații de specialitate și investigații fără internare.", doctors: 12 },
  { icon: "❤️", name: "Cardiologie", desc: "Diagnostic și tratament pentru afecțiunile inimii și vaselor.", doctors: 8 },
  { icon: "🔪", name: "Chirurgie generală", desc: "Intervenții clasice și minim invazive, laparoscopice.", doctors: 10 },
  { icon: "🫁", name: "ATI", desc: "Anestezie și terapie intensivă pentru pacienții critici.", doctors: 9 },
  { icon: "🧠", name: "Neurologie", desc: "Evaluare și tratament pentru afecțiuni neurologice.", doctors: 6 },
  { icon: "🏥", name: "Medicină internă", desc: "Abordare completă a pacientului cu boli cronice.", doctors: 11 },
  { icon: "🧪", name: "Laborator analize", desc: "Analize de biochimie, hematologie și imunologie.", doctors: 5 },
  { icon: "🩻", name: "Radiologie și imagistică", desc: "Radiografie, ecografie, CT și RMN.", doctors: 7 },
];

const doctors = [
  { name: "Dr. Nume Prenume", role: "Medic primar Cardiologie" },
  { name: "Dr. Nume Prenume", role: "Medic primar Chirurgie" },
  { name: "Dr. Nume Prenume", role: "Medic primar Neurologie" },
  { name: "Dr. Nume Prenume", role: "Medic specialist ATI" },
];

const $ = (s) => document.querySelector(s);

$("#specialtyCards").innerHTML = specialties.map((s) => `
  <article class="card">
    <div class="card-icon">${s.icon}</div>
    <h3>${s.name}</h3>
    <p>${s.desc}</p>
    <div class="card-meta"><span>${s.doctors} medici</span><a href="#">Detalii →</a></div>
  </article>`).join("");

$("#teamGrid").innerHTML = doctors.map((d) => `
  <div class="doctor">
    <div class="doctor-photo" aria-hidden="true">${d.name.replace("Dr. ", "").split(" ").map((w) => w[0]).join("")}</div>
    <h3>${d.name}</h3><span>${d.role}</span>
  </div>`).join("");

// Mobile menu
const nav = $("#nav"), menuToggle = $("#menuToggle");
menuToggle.addEventListener("click", () => {
  const open = nav.classList.toggle("open");
  menuToggle.setAttribute("aria-expanded", open);
  menuToggle.textContent = open ? "✕" : "☰";
});
nav.querySelectorAll(".has-sub > a").forEach((a) => a.addEventListener("click", (e) => {
  if (window.innerWidth <= 980) { e.preventDefault(); a.parentElement.classList.toggle("open"); }
}));
nav.querySelectorAll(".submenu a, .nav > ul > li:not(.has-sub) > a").forEach((a) =>
  a.addEventListener("click", () => { nav.classList.remove("open"); menuToggle.textContent = "☰"; }));

// Search
const searchToggle = $("#searchToggle"), searchPanel = $("#searchPanel");
searchToggle.addEventListener("click", () => {
  const open = searchPanel.classList.toggle("open");
  searchToggle.setAttribute("aria-expanded", open);
  if (open) searchPanel.querySelector("input").focus();
});

// Animated counters
const fmt = (n) => n.toLocaleString("ro-RO");
const io = new IntersectionObserver((entries) => entries.forEach((e) => {
  if (!e.isIntersecting) return;
  const el = e.target, target = +el.dataset.count, prefix = el.dataset.prefix || "";
  const start = performance.now(), dur = 1400;
  const tick = (t) => {
    const p = Math.min((t - start) / dur, 1);
    el.textContent = prefix + fmt(Math.round(target * (1 - Math.pow(1 - p, 3))));
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  io.unobserve(el);
}), { threshold: 0.4 });
document.querySelectorAll("[data-count]").forEach((el) => io.observe(el));

// Contact form (front-end only — connect to a backend/email service)
$("#contactForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const f = e.target;
  $("#formMsg").textContent = f.checkValidity()
    ? "Mulțumim! Mesajul a fost înregistrat."
    : "Te rugăm să completezi câmpurile obligatorii.";
  if (f.checkValidity()) f.reset();
});

// Back to top + year
const backTop = $("#backTop");
window.addEventListener("scroll", () => backTop.classList.toggle("show", scrollY > 600));
backTop.addEventListener("click", () => scrollTo({ top: 0 }));
$("#year").textContent = new Date().getFullYear();
