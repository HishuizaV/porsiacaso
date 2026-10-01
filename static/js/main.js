const btn = document.getElementById("menuBtn");
const nav = document.getElementById("nav");

btn.addEventListener("click", () => {
    const abierto = nav.classList.toggle("open");
    btn.setAttribute("aria-expanded", abierto);
});

// Cierra los desplegables (zona y "Más") al hacer clic fuera
document.addEventListener("click", (e) => {
    document.querySelectorAll("details.ubic[open], details.mas[open]").forEach((d) => {
        if (!d.contains(e.target)) d.removeAttribute("open");
    });
});