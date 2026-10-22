import os
import io
import re
import json
import uuid
import zipfile
import hashlib
import mimetypes
import random
from datetime import datetime, date, timedelta
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from models import (
    Base, Carrera, Materia, Competencia, Usuario, Evidencia, ArchivoEvidencia,
    AuditoriaEvidencia, RolUsuario, TipoEvidencia, EstadoEvidencia,
    create_engine, sessionmaker, inicializar_reticula_itp
)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./portafolio_ia_itp.db")
UPLOAD_DIR = "./storage_evidencias"
os.makedirs(UPLOAD_DIR, exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def preparar_reticula():
    db = SessionLocal()
    try:
        if db.query(Materia).count() == 0:
            inicializar_reticula_itp(db)
    finally:
        db.close()

preparar_reticula()

app = FastAPI(title="CommonKADS - Portafolio Académico ITP con IA", version="6.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/archivos", StaticFiles(directory=UPLOAD_DIR), name="archivos")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def servir_frontend():
    if os.path.exists("index.html"):
        return FileResponse("index.html", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})
    return {"mensaje": "Falta index.html"}

def calcular_semestre_vigente(usuario: Usuario) -> dict:
    sem_base = usuario.semestre_base or 1
    if usuario.modo_semestre == "MANUAL" or not usuario.fecha_fin_semestre:
        return {"semestre_calculado": sem_base, "modo": "Manual", "explicacion": f"Semestre {sem_base}° establecido manualmente."}
    try:
        hoy = date.today()
        fin_sem = datetime.strptime(usuario.fecha_fin_semestre, "%Y-%m-%d").date()
        inicio_sem = datetime.strptime(usuario.fecha_inicio_semestre, "%Y-%m-%d").date() if usuario.fecha_inicio_semestre else fin_sem

        if hoy <= fin_sem:
            return {"semestre_calculado": sem_base, "modo": "Automático (En curso)", "explicacion": f"Cursando {sem_base}° semestre (Del {inicio_sem} al {fin_sem})."}
        else:
            dias_extra = (hoy - fin_sem).days
            semestres_adicionales = (dias_extra // 180) + 1
            nuevo_semestre = min(9, sem_base + semestres_adicionales)
            return {"semestre_calculado": nuevo_semestre, "modo": "Automático (Actualizado)", "explicacion": f"El periodo terminó el {fin_sem}; actualizado a {nuevo_semestre}° semestre."}
    except Exception:
        return {"semestre_calculado": sem_base, "modo": "Respaldo Manual", "explicacion": f"Formato inválido; semestre {sem_base}° manual."}

DICCIONARIO_TECNOLOGIAS = {
    "Python": [r"\bpython\b", r"\.py\b", r"\bfastapi\b", r"\bflask\b", r"\bdjango\b", r"\bpandas\b"],
    "SQL / Bases de Datos": [r"\bsql\b", r"\bpostgres", r"\bmysql\b", r"\bsqlite\b", r"\bsupabase\b", r"entidad-relaci", r"\bselect\b", r"\bcreate table\b"],
    "Kotlin / Android": [r"\bkotlin\b", r"\.kt\b", r"\bandroid studio\b", r"\bapk\b", r"\bgradle\b"],
    "Java": [r"\bjava\b", r"\.java\b", r"\bpoo\b", r"\bspring\b"],
    "Desarrollo Web (HTML/CSS/JS)": [r"\bhtml\b", r"\bcss\b", r"\bjavascript\b", r"\breact\b", r"\btailwind\b", r"\bfrontend\b"],
    "Redes y Telecomunicaciones": [r"\bcisco\b", r"\bpacket tracer\b", r"\.pkt\b", r"\bvlan\b", r"\brouter\b", r"\bswitch\b", r"\bwireshark\b", r"\bip\b"],
    "Ciberseguridad / Linux": [r"\bkali\b", r"\blinux\b", r"\bbash\b", r"\bdocker\b", r"\bseguridad\b", r"\bauditor", r"\bhash\b", r"\bsha-?256\b"],
    "Ingeniería del Conocimiento / IA": [r"\bcommonkads\b", r"\bprolog\b", r"\.pl\b", r"\bontolog", r"\bconocimiento\b", r"\bagentes\b", r"\bgemini\b", r"\bmachine learning\b"],
    "Ingeniería de Software / UML": [r"\buml\b", r"\bcasos de uso\b", r"\brequerimientos\b", r"\bscrum\b", r"\barquitectura\b"],
    "Excel VBA / Análisis de Datos": [r"\bvba\b", r"\bexcel\b", r"\.xlsm\b", r"\.xlsx\b", r"\buserform\b", r"\bestadística\b"],
    "Modelado 3D / CAD": [r"\bblender\b", r"\bcatia\b", r"\b3dexperience\b", r"\bcad\b"],
    "Git / Control de Versiones": [r"\bgithub\b", r"\bgitlab\b", r"\bgit\b"],
    "Producción Multimedia / Video": [r"\.mp4\b", r"\.webm\b", r"\.mov\b", r"\bvideo\b"]
}

def extraer_texto_de_archivo(nombre: str, contenido: bytes) -> str:
    ext = os.path.splitext(nombre)[1].lower()
    texto_extraido = f"Archivo: {nombre} ({ext}). "
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            lector = PdfReader(io.BytesIO(contenido))
            paginas_texto = []
            for page in lector.pages[:10]:
                paginas_texto.append(page.extract_text() or "")
            texto_extraido += " ".join(paginas_texto)
        except Exception:
            try:
                texto_crudo = contenido.decode("utf-8", errors="ignore")
                palabras = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñÑ0-9_\-\.]{4,}", texto_crudo)
                texto_extraido += " ".join(palabras[:1000])
            except Exception:
                pass
    elif ext == ".zip":
        try:
            with zipfile.ZipFile(io.BytesIO(contenido)) as z:
                lista_interna = z.namelist()
                texto_extraido += "Contiene archivos comprimidos: " + ", ".join(lista_interna[:50])
                for item in lista_interna[:8]:
                    if item.endswith((".py", ".kt", ".java", ".sql", ".html", ".js", ".md", ".txt", ".pl")):
                        muestra = z.read(item).decode("utf-8", errors="ignore")[:1000]
                        texto_extraido += f"\nCódigo en {item}: {muestra}"
        except Exception:
            pass
    elif ext in [".py", ".kt", ".java", ".sql", ".js", ".jsx", ".ts", ".html", ".css", ".pl", ".txt", ".md", ".json", ".csv"]:
        try:
            texto_extraido += contenido.decode("utf-8", errors="ignore")[:5000]
        except Exception:
            pass
    return texto_extraido

def analizar_evidencia_con_ia(titulo: str, descripcion: str, materia_nombre: str, textos_archivos: List[str], url_externa: str = "") -> dict:
    corpus_completo = f"Materia: {materia_nombre}. Título: {titulo}. Descripción: {descripcion}. URL: {url_externa}. " + "\n".join(textos_archivos)
    tecnologias_detectadas = []
    corpus_lower = corpus_completo.lower()
    for tech, patrones in DICCIONARIO_TECNOLOGIAS.items():
        for pat in patrones:
            if re.search(pat, corpus_lower, re.IGNORECASE):
                tecnologias_detectadas.append(tech)
                break
    if "base de datos" in materia_nombre.lower() or "sql" in materia_nombre.lower():
        if "SQL / Bases de Datos" not in tecnologias_detectadas: tecnologias_detectadas.append("SQL / Bases de Datos")
    elif "redes" in materia_nombre.lower() or "telecomunicaciones" in materia_nombre.lower() or "inalámbricas" in materia_nombre.lower():
        if "Redes y Telecomunicaciones" not in tecnologias_detectadas: tecnologias_detectadas.append("Redes y Telecomunicaciones")
    elif "móviles" in materia_nombre.lower():
        if "Kotlin / Android" not in tecnologias_detectadas: tecnologias_detectadas.append("Kotlin / Android")
    elif "web" in materia_nombre.lower():
        if "Desarrollo Web (HTML/CSS/JS)" not in tecnologias_detectadas: tecnologias_detectadas.append("Desarrollo Web (HTML/CSS/JS)")
    elif "conocimiento" in materia_nombre.lower():
        if "Ingeniería del Conocimiento / IA" not in tecnologias_detectadas: tecnologias_detectadas.append("Ingeniería del Conocimiento / IA")
    if not tecnologias_detectadas:
        tecnologias_detectadas.append(f"Competencia en {materia_nombre}")
    resumen_generado = f"Análisis IA de Evidencia: En la asignatura '{materia_nombre}', el estudiante desarrolló '{titulo}', demostrando dominio práctico en {', '.join(tecnologias_detectadas[:5])} mediante archivos verificados."
    return {"tecnologias": tecnologias_detectadas, "resumen_cv": resumen_generado}

def clasificar_extension(filename: str) -> TipoEvidencia:
    ext = os.path.splitext(filename)[1].lower()
    if ext in [".py", ".kt", ".java", ".sql", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".pl", ".cpp", ".c", ".json", ".xml", ".sh"]:
        return TipoEvidencia.CODIGO
    elif ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv"]:
        return TipoEvidencia.DOCUMENTO
    elif ext in [".zip", ".rar", ".7z", ".tar", ".gz", ".pkt"]:
        return TipoEvidencia.COMPRIMIDO
    elif ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"]:
        return TipoEvidencia.IMAGEN
    elif ext in [".mp4", ".webm", ".mov", ".avi", ".mkv"]:
        return TipoEvidencia.VIDEO
    return TipoEvidencia.OTRO

# --- ENDPOINTS DE AUTENTICACIÓN Y RECUPERACIÓN (FLUJO TIPO GOOGLE OTP) ---
@app.post("/api/auth/registro", status_code=201)
async def registrar_estudiante(
    nombre_completo: str = Form(...),
    matricula: str = Form(...),
    correo: str = Form(...),
    password: str = Form(...),
    es_itics: bool = Form(True),
    modo_semestre: str = Form("AUTOMATICO"),
    semestre_base: int = Form(1),
    fecha_inicio_semestre: Optional[str] = Form(None),
    fecha_fin_semestre: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    matricula_limpia = matricula.strip().upper()
    correo_limpio = correo.strip().lower()

    patron_correo = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(patron_correo, correo_limpio):
        raise HTTPException(status_code=400, detail="El formato del correo electrónico no es válido.")

    existente = db.query(Usuario).filter(
        (Usuario.matricula == matricula_limpia) | (Usuario.correo == correo_limpio)
    ).first()
    if existente:
        raise HTTPException(status_code=400, detail="Ese Número de Control o Correo ya está registrado.")

    foto_ruta = None
    if foto and foto.filename:
        carpeta_perfil = os.path.join(UPLOAD_DIR, "perfiles")
        os.makedirs(carpeta_perfil, exist_ok=True)
        nombre_foto = f"{matricula_limpia}_{uuid.uuid4().hex[:6]}_{foto.filename}"
        ruta_fisica = os.path.join(carpeta_perfil, nombre_foto)
        with open(ruta_fisica, "wb") as f:
            f.write(await foto.read())
        foto_ruta = f"/archivos/perfiles/{nombre_foto}"

    carrera = db.query(Carrera).filter_by(clave_oficial="ITIC-2010-225").first()
    nuevo = Usuario(
        nombre_completo=nombre_completo.strip(),
        matricula=matricula_limpia,
        correo=correo_limpio,
        password_hash=hashlib.sha256(password.encode()).hexdigest(),
        foto_url=foto_ruta,
        es_itics=es_itics,
        modo_semestre=modo_semestre,
        semestre_base=semestre_base,
        fecha_inicio_semestre=fecha_inicio_semestre if fecha_inicio_semestre else None,
        fecha_fin_semestre=fecha_fin_semestre if fecha_fin_semestre else None,
        carrera_id=carrera.id if carrera else None
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    info_sem = calcular_semestre_vigente(nuevo)
    return {
        "mensaje": "Cuenta creada exitosamente",
        "usuario": {
            "id": nuevo.id, "nombre": nuevo.nombre_completo, "matricula": nuevo.matricula,
            "correo": nuevo.correo, "foto_url": nuevo.foto_url, "es_itics": nuevo.es_itics,
            "semestre_actual": info_sem["semestre_calculado"], "detalle_semestre": info_sem["explicacion"]
        }
    }

@app.post("/api/auth/login")
def login_estudiante(
    identificador: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    ident = identificador.strip()
    usuario = db.query(Usuario).filter(
        (Usuario.matricula == ident.upper()) | (Usuario.correo == ident.lower())
    ).first()
    hash_ingresado = hashlib.sha256(password.encode()).hexdigest()

    if not usuario or usuario.password_hash != hash_ingresado:
        raise HTTPException(status_code=401, detail="Número de control/correo o contraseña incorrectos.")

    info_sem = calcular_semestre_vigente(usuario)
    return {
        "usuario": {
            "id": usuario.id, "nombre": usuario.nombre_completo, "matricula": usuario.matricula,
            "correo": usuario.correo, "foto_url": usuario.foto_url, "es_itics": usuario.es_itics,
            "semestre_actual": info_sem["semestre_calculado"], "detalle_semestre": info_sem["explicacion"]
        }
    }

@app.post("/api/auth/solicitar-codigo")
def solicitar_codigo_recuperacion(
    correo_o_matricula: str = Form(...),
    db: Session = Depends(get_db)
):
    ident = correo_o_matricula.strip()
    usuario = db.query(Usuario).filter(
        (Usuario.matricula == ident.upper()) | (Usuario.correo == ident.lower())
    ).first()
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en el sistema.")
        
    codigo = str(random.randint(100000, 999999))
    usuario.codigo_recuperacion = codigo
    usuario.expiracion_codigo = datetime.utcnow() + timedelta(minutes=15)
    db.commit()
    
    return {
        "mensaje": "Código generado exitosamente. (Para tu demo escolar, el código de verificación es: " + codigo + ")"
    }

@app.post("/api/auth/restablecer-password")
def restablecer_password(
    correo_o_matricula: str = Form(...),
    codigo: str = Form(...),
    nueva_password: str = Form(...),
    db: Session = Depends(get_db)
):
    ident = correo_o_matricula.strip()
    usuario = db.query(Usuario).filter(
        (Usuario.matricula == ident.upper()) | (Usuario.correo == ident.lower())
    ).first()
    
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        
    if not usuario.codigo_recuperacion or usuario.codigo_recuperacion != codigo.strip():
        raise HTTPException(status_code=401, detail="El código de verificación es incorrecto.")
        
    if not usuario.expiracion_codigo or datetime.utcnow() > usuario.expiracion_codigo:
        raise HTTPException(status_code=401, detail="El código de verificación ha expirado. Solicita uno nuevo.")
        
    usuario.password_hash = hashlib.sha256(nueva_password.encode()).hexdigest()
    usuario.codigo_recuperacion = None
    usuario.expiracion_codigo = None
    db.commit()
    
    return {"mensaje": "Contraseña actualizada exitosamente. Ya puedes iniciar sesión con tu nueva contraseña."}

# --- ENDPOINTS RETÍCULA, SUBIDA Y CV ---
@app.get("/api/reticula/materias")
def listar_materias(estudiante_id: Optional[int] = None, db: Session = Depends(get_db)):
    materias = db.query(Materia).order_by(Materia.semestre, Materia.id).all()
    conteo_evidencias = {}
    query_ev = db.query(Evidencia).filter(Evidencia.is_deleted == False)
    if estudiante_id:
        query_ev = query_ev.filter(Evidencia.estudiante_id == estudiante_id)
    for ev in query_ev.all():
        conteo_evidencias[ev.materia_id] = conteo_evidencias.get(ev.materia_id, 0) + 1

    return [{"id": m.id, "clave": m.clave, "nombre": m.nombre, "semestre": m.semestre, "satca": m.satca, "creditos": m.creditos, "tipo": m.tipo_asignatura, "total_evidencias": conteo_evidencias.get(m.id, 0)} for m in materias]

@app.post("/api/evidencias/subir", status_code=201)
async def subir_evidencia(
    estudiante_id: int = Form(...),
    titulo: str = Form(...),
    descripcion: str = Form(""),
    materia_id: int = Form(...),
    url_enlace_externo: Optional[str] = Form(None),
    archivos: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db)
):
    usuario = db.query(Usuario).filter(Usuario.id == estudiante_id).first()
    if not usuario: raise HTTPException(status_code=404, detail="Primero debes iniciar sesión.")

    materia = db.query(Materia).filter(Materia.id == materia_id).first()
    competencia = db.query(Competencia).filter(Competencia.materia_id == materia.id).first()
    archivos_validos = [a for a in archivos if a.filename]
    if not archivos_validos and not url_enlace_externo: raise HTTPException(status_code=400, detail="Adjunta al menos un archivo o enlace.")

    nueva_evidencia = Evidencia(
        titulo=titulo, descripcion=descripcion,
        tipo=TipoEvidencia.MULTIPLE if len(archivos_validos) > 1 else (clasificar_extension(archivos_validos[0].filename) if archivos_validos else TipoEvidencia.ENLACE),
        url_enlace_externo=url_enlace_externo, estudiante_id=usuario.id, materia_id=materia.id, competencia_id=competencia.id
    )
    db.add(nueva_evidencia)
    db.flush()

    carpeta_destino = os.path.join(UPLOAD_DIR, usuario.matricula, f"materia_{materia.id}", f"evidencia_{nueva_evidencia.id}")
    os.makedirs(carpeta_destino, exist_ok=True)
    textos_para_ia = []
    resumen_archivos_guardados = []

    for arch in archivos_validos:
        nombre_limpio = arch.filename
        tipo_arch = clasificar_extension(nombre_limpio)
        mime_detectado = arch.content_type or mimetypes.guess_type(nombre_limpio)[0] or "application/octet-stream"
        identificador_unico = f"{uuid.uuid4().hex[:8]}_{nombre_limpio}"
        ruta_fisica = os.path.join(carpeta_destino, identificador_unico)
        contenido = await arch.read()
        tamano = len(contenido)
        hash_sha256 = hashlib.sha256(contenido).hexdigest()
        with open(ruta_fisica, "wb") as f: f.write(contenido)
        texto_interno = extraer_texto_de_archivo(nombre_limpio, contenido)
        textos_para_ia.append(texto_interno)
        ruta_url = f"/archivos/{usuario.matricula}/materia_{materia.id}/evidencia_{nueva_evidencia.id}/{identificador_unico}"
        
        registro_archivo = ArchivoEvidencia(
            evidencia_id=nueva_evidencia.id, nombre_original=nombre_limpio, ruta_servidor=ruta_url,
            mime_type=mime_detectado, tipo_archivo=tipo_arch, tamano_bytes=tamano, sha256_hash=hash_sha256, resumen_extraido_ia=texto_interno[:300]
        )
        db.add(registro_archivo)
        resumen_archivos_guardados.append({"nombre": nombre_limpio, "url": ruta_url, "sha256": hash_sha256})

    resultado_ia = analizar_evidencia_con_ia(titulo, descripcion, materia.nombre, textos_para_ia, url_enlace_externo or "")
    nueva_evidencia.tags_ia_detectados = ", ".join(resultado_ia["tecnologias"])
    nueva_evidencia.analisis_ia = resultado_ia["resumen_cv"]
    db.commit()
    return {"mensaje": f"¡Guardado! La IA detectó: {', '.join(resultado_ia['tecnologias'])}", "analisis_ia": resultado_ia["resumen_cv"], "tecnologias_ia": resultado_ia["tecnologias"]}

@app.get("/api/archivos/leer-texto/{archivo_id}", response_class=PlainTextResponse)
def leer_archivo_texto(archivo_id: int, db: Session = Depends(get_db)):
    arch = db.query(ArchivoEvidencia).filter(ArchivoEvidencia.id == archivo_id).first()
    if not arch: raise HTTPException(status_code=404, detail="Archivo no encontrado")
    ruta_real = arch.ruta_servidor.replace("/archivos/", f"{UPLOAD_DIR}/")
    if not os.path.exists(ruta_real): raise HTTPException(status_code=404, detail="Archivo físico no encontrado")
    with open(ruta_real, "r", encoding="utf-8", errors="replace") as f: return f.read()

@app.get("/api/portafolio/{estudiante_id}")
def obtener_portafolio_curricular(estudiante_id: int, db: Session = Depends(get_db)):
    estudiante = db.query(Usuario).filter(Usuario.id == estudiante_id).first()
    if not estudiante: raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    info_sem = calcular_semestre_vigente(estudiante)
    evidencias = db.query(Evidencia).filter(Evidencia.estudiante_id == estudiante.id, Evidencia.is_deleted == False).order_by(Evidencia.fecha_creacion.desc()).all()

    mapa_materias = {}
    stack_ia_global = set()
    total_archivos_subidos = 0

    for ev in evidencias:
        mat = ev.materia
        if ev.tags_ia_detectados:
            for tag in ev.tags_ia_detectados.split(","):
                if tag.strip(): stack_ia_global.add(tag.strip())
        if mat.clave not in mapa_materias:
            mapa_materias[mat.clave] = {"materia_id": mat.id, "clave": mat.clave, "nombre_materia": mat.nombre, "semestre": mat.semestre, "creditos": mat.creditos, "satca": mat.satca, "evidencias": []}
        lista_archivos = []
        for a in ev.archivos:
            total_archivos_subidos += 1
            lista_archivos.append({"id": a.id, "nombre": a.nombre_original, "url": a.ruta_servidor, "tipo": a.tipo_archivo.value, "tamano_kb": round(a.tamano_bytes / 1024, 1), "sha256": a.sha256_hash})
        mapa_materias[mat.clave]["evidencias"].append({"id": ev.id, "titulo": ev.titulo, "descripcion": ev.descripcion, "analisis_ia": ev.analisis_ia, "url_enlace_externo": ev.url_enlace_externo, "tags_ia": [t.strip() for t in (ev.tags_ia_detectados or "").split(",") if t.strip()], "fecha": ev.fecha_creacion.strftime("%Y-%m-%d %H:%M"), "archivos": lista_archivos})

    materias_ordenadas = sorted(mapa_materias.values(), key=lambda x: x["semestre"])
    total_materias_db = db.query(Materia).count() or 54
    perfil_ia = f"Estudiante de {info_sem['semestre_calculado']}° semestre de Ingeniería en TICs en el Instituto Tecnológico de Puebla con {total_archivos_subidos} evidencias prácticas verificadas. " + (f"Dominio comprobado mediante análisis de código y documentos en: {', '.join(sorted(list(stack_ia_global)))}." if stack_ia_global else "Sube tu primer PDF, ZIP o código para que la IA construya tu perfil técnico.")

    return {
        "estudiante": {"id": estudiante.id, "nombre": estudiante.nombre_completo, "matricula": estudiante.matricula, "correo": estudiante.correo, "foto_url": estudiante.foto_url, "es_itics": estudiante.es_itics, "semestre_actual": info_sem["semestre_calculado"], "modo_semestre": info_sem["modo"], "explicacion_semestre": info_sem["explicacion"], "carrera": "Ingeniería en Tecnologías de la Información y Comunicaciones (ITIC-2010-225)", "especialidad": "Análisis de Datos (ITIE-ADD-2025-01)", "perfil_ia": perfil_ia},
        "metricas": {"total_evidencias": len(evidencias), "total_archivos": total_archivos_subidos, "materias_con_evidencia": len(materias_ordenadas), "total_materias_reticula": total_materias_db, "porcentaje_reticula": round((len(materias_ordenadas) / total_materias_db) * 100, 1), "stack_dominado": sorted(list(stack_ia_global))},
        "portafolio_por_materia": materias_ordenadas
    }