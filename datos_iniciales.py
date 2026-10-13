CATEGORIAS_INICIALES = [
    ("empleo", "Empleo", "Empleo y oportunidades", "💼",
     "Convocatorias, ofertas laborales y consejos prácticos para postular con más opciones."),
    ("educacion", "Educación", "Educación", "🎓",
     "Becas, cursos gratuitos y programas de formación disponibles para estudiantes y profesionales."),
    ("beneficios", "Beneficios", "Beneficios y ayudas", "💰",
     "Bonos, subsidios y programas sociales: quién califica, cómo consultar y cuándo cobrar."),
    ("tramites", "Trámites", "Guías y trámites", "📋",
     "Paso a paso para los trámites más frecuentes: documentos, plazos y costos."),
    ("turismo", "Turismo", "Turismo y experiencias", "📍",
     "Destinos, rutas y planes de fin de semana para recorrer el Perú sin gastar de más."),
    ("gastronomia", "Gastronomía", "Gastronomía", "🍔",
     "Sabores peruanos, recetas caseras y lugares donde comer rico a buen precio."),
    ("actualidad", "Actualidad", "Actualidad y tendencias", "🔥",
     "Lo que está pasando en el país explicado de forma clara, sin rodeos y con datos."),
]

PAGINAS_INICIALES = [
    ("sobre-nosotros", "Sobre nosotros", """
<h2>Quiénes somos</h2>
<p><strong>Por Si Acaso</strong> es un portal peruano que reúne y explica información útil para el día a día: empleo, becas, beneficios, trámites, turismo, gastronomía y actualidad.</p>
<h2>Qué encontrarás</h2>
<ul>
<li>Convocatorias y oportunidades explicadas con requisitos, fechas y cómo postular.</li>
<li>Guías de trámites paso a paso.</li>
<li>Información de Chiclayo, Lambayeque y todo el Perú.</li>
</ul>
<h2>Nuestro compromiso</h2>
<p>Cada artículo indica su fuente oficial para que puedas confirmar los datos. Si encuentras un error, escríbenos desde la página de contacto y lo corregiremos.</p>
"""),
    ("politica-editorial", "Política editorial", """
<h2>Cómo trabajamos</h2>
<ul>
<li><strong>Fuentes:</strong> priorizamos fuentes oficiales (entidades públicas, instituciones y comunicados) y las enlazamos en cada artículo.</li>
<li><strong>Contenido propio:</strong> explicamos la información con nuestras palabras y agregamos contexto útil; no copiamos textos de otros medios.</li>
<li><strong>Verificación:</strong> revisamos fechas, requisitos y montos antes de publicar.</li>
<li><strong>Actualización:</strong> cuando una información cambia, actualizamos el artículo.</li>
<li><strong>Correcciones:</strong> si detectamos o nos reportan un error, lo corregimos a la brevedad.</li>
<li><strong>Imágenes:</strong> usamos imágenes propias, licenciadas o de uso libre, y acreditamos su autoría cuando corresponde.</li>
<li><strong>Publicidad:</strong> los anuncios están separados del contenido y no influyen en lo que publicamos.</li>
</ul>
"""),
    ("contacto", "Contacto", """
<p>¿Tienes una consulta, quieres reportar un error o proponer información útil? Escríbenos:</p>
<p><strong>Correo:</strong> contacto@tudominio.com</p>
<p>Intentamos responder en un plazo de 2 a 3 días hábiles.</p>
"""),
    ("privacidad", "Política de privacidad", """
<p>Última actualización: 2026.</p>
<h2>Información que recopilamos</h2>
<p>Por Si Acaso no requiere registro para leer sus contenidos. Como casi todos los sitios web, nuestro servidor puede registrar datos técnicos anónimos (dirección IP, navegador, páginas visitadas) para seguridad y estadísticas.</p>
<h2>Cookies y publicidad</h2>
<p>Este sitio puede usar cookies para medir el tráfico y mostrar anuncios. Google y sus socios publicitarios utilizan cookies para mostrar anuncios basados en tus visitas a este y otros sitios web. Puedes gestionar o desactivar la publicidad personalizada en la <a href="https://adssettings.google.com" target="_blank" rel="noopener">Configuración de anuncios de Google</a>.</p>
<h2>Enlaces externos</h2>
<p>Nuestros artículos enlazan a sitios oficiales y de terceros. No somos responsables de sus políticas de privacidad ni de su contenido.</p>
<h2>Tus derechos</h2>
<p>De acuerdo con la Ley N.° 29733, Ley de Protección de Datos Personales del Perú, puedes solicitar acceso, rectificación, cancelación u oposición sobre tus datos personales escribiéndonos a contacto@tudominio.com.</p>
<h2>Cambios en esta política</h2>
<p>Podemos actualizar esta política. Los cambios se publicarán en esta página.</p>
"""),
    ("terminos", "Términos y condiciones", """
<h2>Uso del sitio</h2>
<p>La información de Por Si Acaso es <strong>referencial y con fines informativos</strong>. Aunque buscamos que sea precisa y actual, siempre debes confirmarla en la fuente oficial antes de realizar un trámite, postulación o pago.</p>
<h2>Propiedad intelectual</h2>
<p>Los textos y el diseño del sitio pertenecen a Por Si Acaso. No está permitido copiar el contenido de forma masiva sin autorización. Las marcas e imágenes de terceros pertenecen a sus respectivos dueños.</p>
<h2>Enlaces</h2>
<p>Podemos enlazar sitios de terceros por conveniencia; no controlamos ni respaldamos su contenido.</p>
<h2>Limitación de responsabilidad</h2>
<p>No nos hacemos responsables por decisiones tomadas únicamente con base en la información publicada aquí.</p>
<h2>Cambios</h2>
<p>Estos términos pueden modificarse en cualquier momento.</p>
"""),
]

REGIONES_INICIALES = [
    "Amazonas", "Áncash", "Apurímac", "Arequipa", "Ayacucho", "Cajamarca", "Callao",
    "Cusco", "Huancavelica", "Huánuco", "Ica", "Junín", "La Libertad", "Lambayeque",
    "Lima", "Loreto", "Madre de Dios", "Moquegua", "Pasco", "Piura", "Puno",
    "San Martín", "Tacna", "Tumbes", "Ucayali",
]

# (ciudad, región). Las demás las agregas tú desde el panel.
CIUDADES_INICIALES = [("Chiclayo", "Lambayeque")]

# Páginas que se agregan con `flask completar-paginas`. Se crean OCULTAS: el administrador
# debe revisarlas y completar los datos marcados como [PENDIENTE] antes de mostrarlas.
PAGINAS_NUEVAS = [
    ("descargo-de-responsabilidad", "Descargo de responsabilidad sobre convocatorias", """
<h2>Somos un medio informativo, no la entidad convocante</h2>
<p>Por Si Acaso difunde convocatorias de empleo, becas, cursos, bonos y trámites publicados por terceros (entidades públicas, empresas e instituciones). <strong>No participamos en los procesos de selección, no cobramos por postular y no gestionamos pagos de beneficios.</strong></p>
<h2>Confirma siempre en la fuente oficial</h2>
<p>Cada publicación indica su fuente y la fecha en que la revisamos. Las bases, requisitos, montos y plazos pueden cambiar: antes de postular, pagar o presentar documentos, revisa la información en el enlace oficial.</p>
<h2>Nunca pedimos dinero ni datos personales</h2>
<p>Desconfía de cualquier persona que pida pagos o tu DNI, contraseñas o datos bancarios en nombre de Por Si Acaso. Nuestro asistente automático tampoco solicita datos personales.</p>
"""),
    ("publicidad", "Información sobre publicidad", """
<h2>Cómo se financia este sitio</h2>
<p>Por Si Acaso puede mostrar anuncios de Google AdSense para cubrir sus costos. Los anuncios se identifican con la palabra «Publicidad» y están separados del contenido.</p>
<h2>Independencia editorial</h2>
<p>Los anunciantes no deciden qué publicamos. No aceptamos pagos para publicar convocatorias ni para presentarlas como oficiales.</p>
<h2>Cookies publicitarias</h2>
<p>Cuando los anuncios estén activos, Google y sus socios pueden usar cookies para mostrarlos. Más información en nuestra <a href="/privacidad">Política de privacidad</a> y en la <a href="https://policies.google.com/technologies/ads" target="_blank" rel="noopener">página de Google sobre publicidad</a>.</p>
"""),
    ("correcciones", "Correcciones y actualización de información", """
<h2>Cómo actualizamos la información</h2>
<p>Las convocatorias y beneficios cambian. Cada publicación muestra la fecha de su última verificación en la fuente oficial. Cuando una convocatoria vence, lo indicamos en la misma página.</p>
<h2>Reporta un error</h2>
<p>Si encuentras un dato incorrecto o un enlace roto, escríbenos indicando la dirección de la página y el dato a corregir: [PENDIENTE: correo de contacto real].</p>
<h2>Qué hacemos con tu reporte</h2>
<p>Revisamos el dato en la fuente oficial y, si corresponde, corregimos la publicación y actualizamos su fecha de verificación.</p>
"""),
]
