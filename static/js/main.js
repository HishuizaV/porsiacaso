(function () {
    "use strict";

    // ---------- Menú móvil ----------
    var boton = document.getElementById("menuBoton");
    var nav = document.getElementById("nav");
    if (boton && nav) {
        boton.addEventListener("click", function () {
            var abierto = nav.classList.toggle("abierto");
            boton.setAttribute("aria-expanded", abierto ? "true" : "false");
        });
    }
    // Cierra el desplegable "Temas" al hacer clic fuera
    document.addEventListener("click", function (e) {
        document.querySelectorAll("details.nav-temas[open]").forEach(function (d) {
            if (!d.contains(e.target)) d.removeAttribute("open");
        });
    });
    // En móvil los filtros empiezan cerrados para no empujar los resultados
    var filtros = document.getElementById("filtros");
    if (filtros && window.matchMedia("(max-width: 979px)").matches && !location.search) {
        filtros.removeAttribute("open");
    }

    // ---------- Asistente PorSiAcaso ----------
    var panel = document.getElementById("asisPanel");
    var abrir = document.getElementById("asisBoton");
    if (!panel || !abrir) return;
    var cerrar = document.getElementById("asisCerrar");
    var lista = document.getElementById("asisMensajes");
    var form = document.getElementById("asisForm");
    var entrada = document.getElementById("asisTexto");
    var estado = {};
    var ocupado = false;
    var iniciado = false;

    function rutaInterna(url) {
        // Solo se aceptan rutas del propio sitio
        return typeof url === "string" && url.charAt(0) === "/" && url.charAt(1) !== "/";
    }

    function burbuja(clase) {
        var div = document.createElement("div");
        div.className = "asis-msg " + clase;
        lista.appendChild(div);
        return div;
    }

    function mostrarRespuesta(datos) {
        var div = burbuja("asis-bot");
        var p = document.createElement("p");
        p.textContent = datos.respuesta || "";
        div.appendChild(p);
        if (Array.isArray(datos.resultados) && datos.resultados.length) {
            var ul = document.createElement("ul");
            ul.className = "asis-resultados";
            datos.resultados.forEach(function (r) {
                if (!rutaInterna(r.url)) return;
                var li = document.createElement("li");
                var a = document.createElement("a");
                a.href = r.url;
                var t = document.createElement("strong");
                t.textContent = r.titulo;
                var m = document.createElement("small");
                m.textContent = [r.tipo, r.meta].filter(Boolean).join(" · ");
                a.appendChild(t);
                a.appendChild(m);
                li.appendChild(a);
                ul.appendChild(li);
            });
            div.appendChild(ul);
        }
        if (datos.enlace && rutaInterna(datos.enlace.url)) {
            var enl = document.createElement("a");
            enl.className = "enlace";
            enl.href = datos.enlace.url;
            enl.textContent = datos.enlace.texto + " →";
            var pe = document.createElement("p");
            pe.style.marginTop = "8px";
            pe.appendChild(enl);
            div.appendChild(pe);
        }
        if (Array.isArray(datos.opciones) && datos.opciones.length) {
            var op = document.createElement("div");
            op.className = "asis-opciones";
            datos.opciones.forEach(function (o) {
                var b = document.createElement("button");
                b.type = "button";
                b.textContent = o.texto;
                b.addEventListener("click", function () { enviar(o.valor); });
                op.appendChild(b);
            });
            div.appendChild(op);
        }
        lista.scrollTop = lista.scrollHeight;
    }

    function enviar(texto) {
        texto = (texto || "").trim();
        if (!texto || ocupado) return;
        ocupado = true;
        burbuja("asis-usuario").textContent = texto;
        var espera = burbuja("asis-bot escribiendo");
        espera.textContent = "Buscando…";
        lista.scrollTop = lista.scrollHeight;
        fetch(panel.getAttribute("data-url"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({ mensaje: texto.slice(0, 300), estado: estado })
        }).then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (d) { d._codigo = r.status; return d; });
        }).then(function (datos) {
            espera.remove();
            if (datos._codigo !== 200 && !datos.respuesta) {
                datos = { respuesta: "No pude responder ahora. Usa el buscador del sitio, por favor." };
            }
            if (datos.estado && typeof datos.estado === "object") estado = datos.estado;
            mostrarRespuesta(datos);
        }).catch(function () {
            espera.remove();
            mostrarRespuesta({ respuesta: "Sin conexión. Inténtalo de nuevo en un momento." });
        }).then(function () { ocupado = false; });
    }

    function abrirPanel() {
        panel.hidden = false;
        abrir.hidden = true;
        abrir.setAttribute("aria-expanded", "true");
        if (!iniciado) {
            iniciado = true;
            mostrarRespuesta({
                respuesta: "Hola, soy el Asistente PorSiAcaso (automático). Te ayudo a encontrar lo que está publicado en este sitio. ¿Qué buscas?",
                opciones: [
                    { texto: "Busco trabajo", valor: "Busco trabajo" },
                    { texto: "Becas", valor: "Quiero becas para estudiar" },
                    { texto: "Cursos", valor: "Cursos" },
                    { texto: "Bonos", valor: "Bonos y beneficios" },
                    { texto: "Trámites", valor: "Trámites" }
                ]
            });
        }
        entrada.focus();
    }
    function cerrarPanel() {
        panel.hidden = true;
        abrir.hidden = false;
        abrir.setAttribute("aria-expanded", "false");
        abrir.focus();
    }
    abrir.addEventListener("click", abrirPanel);
    cerrar.addEventListener("click", cerrarPanel);
    panel.addEventListener("keydown", function (e) { if (e.key === "Escape") cerrarPanel(); });
    form.addEventListener("submit", function (e) {
        e.preventDefault();
        var t = entrada.value;
        entrada.value = "";
        enviar(t);
    });
})();
