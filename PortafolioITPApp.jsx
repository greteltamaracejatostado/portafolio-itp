import React, { useState, useEffect } from "react";

const API_BASE = "http://localhost:8000";

export default function PortafolioITPApp() {
  const [vistaActual, setVistaActual] = useState("landing"); // "landing" | "subir" | "portafolio"
  const [materias, setMaterias] = useState([]);
  const [competencias, setCompetencias] = useState([]);
  const [semestreFiltro, setSemestreFiltro] = useState("TODOS");

  // Estado del formulario de evidencia
  const [materiaSeleccionada, setMateriaSeleccionada] = useState("");
  const [competenciaSeleccionada, setCompetenciaSeleccionada] = useState("");
  const [titulo, setTitulo] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [tags, setTags] = useState("");
  const [urlExterna, setUrlExterna] = useState("");
  const [archivo, setArchivo] = useState(null);
  const [mensajeEstado, setMensajeEstado] = useState(null);

  // Estado del Portafolio / CV
  const [datosPortafolio, setDatosPortafolio] = useState(null);
  const [archivoPrevisualizar, setArchivoPrevisualizar] = useState(null);

  // Cargar todas las materias de la retícula ITP al iniciar
  useEffect(() => {
    fetch(`${API_BASE}/api/reticula/materias`)
      .then((res) => res.json())
      .then((data) => setMaterias(data))
      .catch(() => console.warn("Modo demostración: conecta el backend en el puerto 8000"));
  }, []);

  // SELECT DEPENDIENTE: Cuando cambia la Materia, carga automáticamente sus Competencias
  useEffect(() => {
    if (!materiaSeleccionada) {
      setCompetencias([]);
      setCompetenciaSeleccionada("");
      return;
    }
    fetch(`${API_BASE}/api/reticula/materias/${materiaSeleccionada}/competencias`)
      .then((res) => res.json())
      .then((data) => {
        setCompetencias(data);
        if (data.length > 0) setCompetenciaSeleccionada(data[0].id);
      });
  }, [materiaSeleccionada]);

  const manejarSubidaEvidencia = async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append("titulo", titulo);
    formData.append("descripcion", descripcion);
    formData.append("materia_id", materiaSeleccionada);
    formData.append("competencia_id", competenciaSeleccionada);
    formData.append("tags_tecnologias", tags);
    if (urlExterna) formData.append("url_enlace_externo", urlExterna);
    if (archivo) formData.append("archivo", archivo);

    const token = localStorage.getItem("itp_token");
    const respuesta = await fetch(`${API_BASE}/api/evidencias/subir`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });

    if (respuesta.ok) {
      const data = await respuesta.json();
      setMensajeEstado(`Evidencia guardada. Firma SHA-256: ${data.sha256?.slice(0, 16)}...`);
      setTitulo("");
      setDescripcion("");
      setArchivo(null);
    } else {
      const err = await respuesta.json();
      setMensajeEstado(`Error: ${err.detail}`);
    }
  };

  const cargarPortafolio = async (estudianteId = 1) => {
    const res = await fetch(`${API_BASE}/api/portafolio/${estudianteId}`);
    if (res.ok) {
      const data = await res.json();
      setDatosPortafolio(data);
      setVistaActual("portafolio");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      {/* BARRA DE NAVEGACIÓN INSTITUCIONAL */}
      <nav className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => setVistaActual("landing")}>
            <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-lg">
              ITP
            </div>
            <div>
              <span className="font-bold text-white block leading-none">Portafolio Académico ITP</span>
              <span className="text-xs text-blue-400">ITIC-2010-225 • Ingeniería del Conocimiento</span>
            </div>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => setVistaActual("subir")}
              className="px-4 py-2 text-sm rounded-lg bg-slate-800 hover:bg-slate-700 transition"
            >
              Subir Evidencia
            </button>
            <button
              onClick={() => cargarPortafolio(1)}
              className="px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-500 font-semibold transition"
            >
              Ver Mi CV / Portafolio
            </button>
          </div>
        </div>
      </nav>

      {/* 1. VISTA: LANDING PAGE */}
      {vistaActual === "landing" && (
        <main>
          {/* HERO SECTION */}
          <section className="max-w-6xl mx-auto px-6 py-20 text-center">
            <span className="px-3 py-1 rounded-full text-xs font-semibold bg-blue-950 text-blue-300 border border-blue-800">
              Metodología CommonKADS • TecNM Campus Puebla
            </span>
            <h1 className="text-4xl md:text-6xl font-extrabold mt-6 tracking-tight text-white">
              Transforma tus prácticas de clase en un{" "}
              <span className="text-blue-400">Portafolio Técnico Verificable</span>
            </h1>
            <p className="mt-6 text-lg text-slate-300 max-w-3xl mx-auto">
              Respalda tus calificaciones numéricas con código fuente real, diagramas, bases de datos y
              documentación vinculada directamente a las 53 asignaturas oficiales de la retícula de ITICs.
            </p>
            {/* BOTONES CTA */}
            <div className="mt-10 flex flex-wrap justify-center gap-4">
              <button
                onClick={() => setVistaActual("subir")}
                className="px-7 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 font-bold text-white shadow-lg shadow-blue-600/30 transition"
              >
                Iniciar Sesión
              </button>
              <button
                onClick={() => setVistaActual("subir")}
                className="px-7 py-3.5 rounded-xl bg-slate-800 hover:bg-slate-700 font-bold text-slate-200 border border-slate-700 transition"
              >
                Crear Cuenta Estudiantil
              </button>
            </div>
          </section>

          {/* SECCIÓN DE CARACTERÍSTICAS */}
          <section className="max-w-6xl mx-auto px-6 py-12 grid md:grid-cols-3 gap-6">
            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800">
              <h3 className="text-xl font-bold text-blue-400 mb-2">1. Vinculación con Retícula</h3>
              <p className="text-slate-300 text-sm leading-relaxed">
                Mapeo completo de los 9 semestres de ITIC-2010-225 y la especialidad en Análisis de Datos
                (ITIE-ADD-2025-01). Cada entrega se asocia a su materia y competencia oficial.
              </p>
            </div>
            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800">
              <h3 className="text-xl font-bold text-emerald-400 mb-2">2. Generación de Portafolio</h3>
              <p className="text-slate-300 text-sm leading-relaxed">
                Construye automáticamente tu CV web interactivo organizado por semestres y stack tecnológico
                para postularte a Residencias Profesionales o vacantes TI.
              </p>
            </div>
            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800">
              <h3 className="text-xl font-bold text-amber-400 mb-2">3. Evidencias Verificables</h3>
              <p className="text-slate-300 text-sm leading-relaxed">
                Soporte universal de archivos (código, PDF, ZIP, Packet Tracer, imágenes y enlaces GitHub)
                protegidos con firma criptográfica SHA-256 y bitácora de auditoría inmutable.
              </p>
            </div>
          </section>
        </main>
      )}

      {/* 2. VISTA: FORMULARIO DE SUBIDA CON SELECTS DEPENDIENTES */}
      {vistaActual === "subir" && (
        <section className="max-w-3xl mx-auto px-6 py-12">
          <div className="p-8 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl">
            <h2 className="text-2xl font-bold text-white mb-2">Registrar Nueva Evidencia Académica</h2>
            <p className="text-sm text-slate-400 mb-6">
              Selecciona la materia de tu retícula para desplegar sus competencias específicas.
            </p>

            {mensajeEstado && (
              <div className="mb-6 p-4 rounded-xl bg-blue-950/80 border border-blue-700 text-blue-200 text-sm">
                {mensajeEstado}
              </div>
            )}

            <form onSubmit={manejarSubidaEvidencia} className="space-y-5">
              {/* Filtro rápido por semestre */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase text-slate-400 mb-2">
                    Filtrar Semestre
                  </label>
                  <select
                    value={semestreFiltro}
                    onChange={(e) => setSemestreFiltro(e.target.value)}
                    className="w-full p-3 rounded-xl bg-slate-950 border border-slate-700 text-sm"
                  >
                    <option value="TODOS">Todos (1° a 9°)</option>
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((s) => (
                      <option key={s} value={s}>{s}° Semestre</option>
                    ))}
                  </select>
                </div>

                {/* SELECT 1: MATERIA DE LA RETÍCULA */}
                <div className="md:col-span-2">
                  <label className="block text-xs font-semibold uppercase text-slate-400 mb-2">
                    Materia Oficial (Retícula ITIC-2010-225) *
                  </label>
                  <select
                    required
                    value={materiaSeleccionada}
                    onChange={(e) => setMateriaSeleccionada(e.target.value)}
                    className="w-full p-3 rounded-xl bg-slate-950 border border-slate-700 text-sm"
                  >
                    <option value="">-- Selecciona una asignatura --</option>
                    {materias
                      .filter((m) => semestreFiltro === "TODOS" || m.semestre === Number(semestreFiltro))
                      .map((m) => (
                        <option key={m.id} value={m.id}>
                          [Sem {m.semestre}] {m.clave} - {m.nombre} ({m.creditos} créd.)
                        </option>
                      ))}
                  </select>
                </div>
              </div>

              {/* SELECT 2 (DEPENDIENTE): COMPETENCIA DE LA MATERIA */}
              <div>
                <label className="block text-xs font-semibold uppercase text-slate-400 mb-2">
                  Competencia Específica a la que Contribuye *
                </label>
                <select
                  required
                  disabled={!materiaSeleccionada}
                  value={competenciaSeleccionada}
                  onChange={(e) => setCompetenciaSeleccionada(e.target.value)}
                  className="w-full p-3 rounded-xl bg-slate-950 border border-slate-700 text-sm disabled:opacity-50"
                >
                  {!materiaSeleccionada ? (
                    <option value="">Primero elige una materia arriba...</option>
                  ) : (
                    competencias.map((c) => (
                      <option key={c.id} value={c.id}>
                        Unidad {c.numero_unidad}: {c.descripcion}
                      </option>
                    ))
                  )}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-400 mb-2">
                  Título del Proyecto o Práctica *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ej. Sistema Auditor RAE con Flask y Prolog / Topología VLANs"
                  value={titulo}
                  onChange={(e) => setTitulo(e.target.value)}
                  className="w-full p-3 rounded-xl bg-slate-950 border border-slate-700 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase text-slate-400 mb-2">
                  Descripción Técnica y Aprendizaje Demostrado *
                </label>
                <textarea
                  rows="3"
                  required
                  placeholder="Explica qué problema resuelve, arquitectura empleada y resultados..."
                  value={descripcion}
                  onChange={(e) => setDescripcion(e.target.value)}
                  className="w-full p-3 rounded-xl bg-slate-950 border border-slate-700 text-sm"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase text-slate-400 mb-2">
                    Tecnologías Usadas (Separadas por coma)
                  </label>
                  <input
                    type="text"
                    placeholder="Python, Kotlin, SQL, Docker, Cisco"
                    value={tags}
                    onChange={(e) => setTags(e.target.value)}
                    className="w-full p-3 rounded-xl bg-slate-950 border border-slate-700 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase text-slate-400 mb-2">
                    Enlace a Repositorio (GitHub / GitLab / Demo)
                  </label>
                  <input
                    type="url"
                    placeholder="https://github.com/usuario/proyecto"
                    value={urlExterna}
                    onChange={(e) => setUrlExterna(e.target.value)}
                    className="w-full p-3 rounded-xl bg-slate-950 border border-slate-700 text-sm"
                  />
                </div>
              </div>

              {/* INPUT UNIVERSAL DE ARCHIVOS */}
              <div className="p-4 rounded-xl border-2 border-dashed border-slate-700 bg-slate-950/60">
                <label className="block text-xs font-semibold uppercase text-blue-400 mb-1">
                  Subir Archivo o Entregable (Acepta cualquier formato: PDF, ZIP, PY, KT, SQL, PKT, DOCX, Imágenes)
                </label>
                <input
                  type="file"
                  onChange={(e) => setArchivo(e.target.files[0])}
                  className="w-full text-sm text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-600 file:text-white hover:file:bg-blue-500"
                />
              </div>

              <button
                type="submit"
                className="w-full py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 font-bold text-white transition"
              >
                Guardar Evidencia y Generar Registro de Auditoría
              </button>
            </form>
          </div>
        </section>
      )}

      {/* 3. VISTA: CV / PORTAFOLIO ESTILO LÍNEA DE TIEMPO CURRICULAR */}
      {vistaActual === "portafolio" && datosPortafolio && (
        <section className="max-w-5xl mx-auto px-6 py-12">
          {/* CABECERA DEL CV */}
          <div className="p-8 rounded-2xl bg-slate-900 border border-slate-800 mb-8 flex flex-col md:flex-row justify-between gap-6">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-blue-400">
                Portafolio Académico Verificable
              </span>
              <h2 className="text-3xl font-extrabold text-white mt-1">
                {datosPortafolio.estudiante.nombre}
              </h2>
              <p className="text-slate-300 text-sm mt-1">
                {datosPortafolio.estudiante.carrera} • Especialidad: {datosPortafolio.estudiante.especialidad}
              </p>
              <p className="text-slate-400 text-xs mt-1">
                No. Control: {datosPortafolio.estudiante.matricula} • Semestre Actual:{" "}
                {datosPortafolio.estudiante.semestre_actual}°
              </p>
              {/* STACK DOMINADO */}
              <div className="flex flex-wrap gap-2 mt-4">
                {datosPortafolio.metricas.stack_dominado.map((tech) => (
                  <span
                    key={tech}
                    className="px-2.5 py-1 rounded-md text-xs font-semibold bg-blue-950 text-blue-300 border border-blue-800"
                  >
                    {tech}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex flex-col justify-center items-start md:items-end">
              <div className="text-3xl font-extrabold text-emerald-400">
                {datosPortafolio.metricas.porcentaje_reticula}%
              </div>
              <div className="text-xs text-slate-400">
                Retícula cubierta con evidencia ({datosPortafolio.metricas.materias_con_evidencia}/53 materias)
              </div>
            </div>
          </div>

          {/* LÍNEA DE TIEMPO POR MATERIAS */}
          <div className="relative border-l-2 border-blue-700 ml-4 pl-6 space-y-10">
            {datosPortafolio.portafolio_por_materia.map((bloque) => (
              <div key={bloque.clave} className="relative">
                <div className="absolute -left-[33px] top-1 w-4 h-4 rounded-full bg-blue-500 border-4 border-slate-950" />
                <div className="flex items-center gap-3 mb-3">
                  <span className="px-2.5 py-0.5 rounded bg-blue-600 text-xs font-bold">
                    {bloque.semestre}° Semestre
                  </span>
                  <h3 className="text-xl font-bold text-white">
                    {bloque.nombre_materia}{" "}
                    <span className="text-sm font-normal text-slate-400">({bloque.clave})</span>
                  </h3>
                </div>

                <div className="grid gap-4">
                  {bloque.evidencias.map((ev) => (
                    <div key={ev.id} className="p-5 rounded-xl bg-slate-900 border border-slate-800">
                      <div className="flex justify-between items-start">
                        <h4 className="font-bold text-lg text-blue-300">{ev.titulo}</h4>
                        <span className="text-xs px-2 py-1 rounded bg-slate-800 text-slate-300">
                          {ev.estado}
                        </span>
                      </div>
                      <p className="text-sm text-slate-300 mt-2">{ev.descripcion}</p>
                      <p className="text-xs text-slate-400 mt-2 italic">
                        Competencia: {ev.competencia_acreditada}
                      </p>

                      <div className="mt-4 flex flex-wrap items-center gap-4 text-xs">
                        {ev.url_enlace_externo && (
                          <a
                            href={ev.url_enlace_externo}
                            target="_blank"
                            rel="noreferrer"
                            className="text-blue-400 hover:underline font-semibold"
                          >
                            Ver Repositorio Externo ↗
                          </a>
                        )}
                        {ev.url_archivo && (
                          <button
                            onClick={() => setArchivoPrevisualizar(ev)}
                            className="text-emerald-400 hover:underline font-semibold"
                          >
                            Abrir / Leer Archivo ({ev.nombre_archivo})
                          </button>
                        )}
                        {ev.sha256_hash && (
                          <span className="text-slate-500 font-mono">
                            SHA-256: {ev.sha256_hash.slice(0, 12)}...
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* VISOR INTEGRADO PARA LEER ARCHIVOS SIN PERDERLOS */}
          {archivoPrevisualizar && (
            <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-6 z-50">
              <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-4xl w-full p-6">
                <div className="flex justify-between items-center mb-4">
                  <h4 className="font-bold text-white">{archivoPrevisualizar.nombre_archivo}</h4>
                  <button
                    onClick={() => setArchivoPrevisualizar(null)}
                    className="text-slate-400 hover:text-white"
                  >
                    Cerrar ✕
                  </button>
                </div>
                <iframe
                  src={`${API_BASE}${archivoPrevisualizar.url_archivo}`}
                  title="Visor de Evidencia"
                  className="w-full h-96 rounded-lg bg-white"
                />
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}