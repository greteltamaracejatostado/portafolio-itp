import os
import io
import re
import json
import uuid
import zipfile
import hashlib
import secrets
import mimetypes
import smtplib
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./portafolio_seguro_itp.db")
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

app = FastAPI(title="Portafolio Académico ITP - Plataforma Oficial", version="9.0.0")

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
    return {"mensaje": "Servidor activo"}

# --- SEGURIDAD CRIPTOGRÁFICA ---
def hashear_secreto(texto: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", texto.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return f"{salt}${key}"

def verificar_secreto(texto_plano: str, hash_guardado: str) -> bool:
    if not hash_guardado or "$" not in hash_guardado:
        return hashlib.sha256(texto_plano.encode("utf-8")).hexdigest() == hash_guardado
    salt, key = hash_guardado.split("$", 1)
    nuevo_key = hashlib.pbkdf2_hmac("sha256", texto_plano.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return secrets.compare_digest(key, nuevo_key)

def generar_otp_6_digitos() -> str:
    return f"{secrets.randbelow(900000) + 100000}"

# --- VALIDACIÓN DE CORREO REAL CONTRA GOOGLE PUBLIC DNS (dns.google) ---
DOMINIOS_BLOQUEADOS = {
    "tail.com", "test.com", "example.com", "mailinator.com", "tempmail.com",
    "10minutemail.com", "guerrillamail.com", "yopmail.com", "fake.com", "correo.com"
}

TYPOS_DOMINIO = {
    "gmal.com": "gmail.com", "gamil.com": "gmail.com", "gmial.com": "gmail.com",
    "hotmal.com": "hotmail.com", "outlok.com": "outlook.com"
}

def verificar_correo_con_google_dns(correo: str) -> dict:
    correo = correo.strip().lower()
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_.+-]{1,62}@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$", correo):
        return {"valido": False, "motivo": "El formato del correo electrónico no es válido."}

    usuario_parte, dominio = correo.split("@", 1)
    if dominio in TYPOS_DOMINIO:
        return {"valido": False, "motivo": f"¿Quisiste decir {usuario_parte}@{TYPOS_DOMINIO[dominio]}?"}
    if dominio in DOMINIOS_BLOQUEADOS:
        return {"valido": False, "motivo": f"El dominio @{dominio} no es un proveedor de correo válido."}

    try:
        url_google_dns = f"https://dns.google/resolve?name={dominio}&type=MX"
        req = urllib.request.Request(url_google_dns, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("Status") == 0 and data.get("Answer"):
                return {"valido": True, "mensaje": f"Correo válido verificado ({dominio})."}
            return {"valido": False, "motivo": f"El dominio @{dominio} no existe o no puede recibir correos."}
    except Exception:
        return {"valido": True, "mensaje": "Formato de correo válido."}

# --- ENVÍO DE CORREO DE VERIFICACIÓN ---
def enviar_correo_verificacion(destinatario: str, nombre: str, codigo_otp: str, proposito: str) -> bool:
    # --- RESPALDO ACTIVO: Valores hardcodeados si Render falla ---
    remitente = os.getenv("SMTP_EMAIL", "reticulasproyectos@gmail.com")
    
    # ATENCIÓN: REEMPLAZA ESTO CON TUS 16 LETRAS DE GOOGLE
    password = os.getenv("SMTP_PASSWORD", "AQUI_PON_TUS_16_LETRAS") 

    accion = "verificar tu correo electrónico y activar tu cuenta" if proposito == "VERIFICAR_CORREO" else "restablecer tu contraseña"
    html_body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 32px; background: #ffffff; color: #0f172a; border-radius: 12px; border: 1px solid #e2e8f0;">
        <div style="margin-bottom: 20px;">
            <span style="background: #2563eb; color: #ffffff; font-weight: bold; padding: 6px 12px; border-radius: 6px; font-size: 14px;">ITP</span>
            <span style="font-weight: bold; font-size: 16px; margin-left: 8px; color: #0f172a;">Portafolio Académico ITP</span>
        </div>
        <h2 style="color: #0f172a; margin-top: 0; font-size: 20px;">Verificación de correo electrónico</h2>
        <p style="color: #334155; font-size: 14px; line-height: 1.5;">Hola <strong>{nombre}</strong>,</p>
        <p style="color: #334155; font-size: 14px; line-height: 1.5;">Hemos recibido una solicitud para {accion}. Ingresa el siguiente código de verificación de 6 dígitos:</p>
        <div style="background: #f8fafc; border: 2px solid #2563eb; border-radius: 10px; padding: 20px; text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #1e40af; font-family: monospace;">{codigo_otp}</span>
        </div>
        <p style="color: #64748b; font-size: 12px;">Este código es válido por 15 minutos. Si no realizaste esta solicitud, puedes ignorar este correo de forma segura.</p>
    </div>
    """

    if password == "AQUI_PON_TUS_16_LETRAS" or not password:
        print(f"[SMTP NO CONFIGURADO] Pon tu contraseña de aplicación en la línea 106. Código generado: {codigo_otp}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"Portafolio Académico ITP <{remitente}>"
        msg["To"] = destinatario
        msg["Subject"] = f"{codigo_otp} es tu código de verificación - Portafolio ITP"
        msg.attach(MIMEText(html_body, "html"))

        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
        server.starttls()
        server.login(remitente, password)
        server.send_message(msg)
        server.quit()
        print(f"Correo enviado exitosamente a {destinatario}")
        return True
    except Exception as e:
        print("Error enviando SMTP:", e)
        return False

def calcular_semestre_vigente(usuario: Usuario) -> dict:
    sem_base = usuario.semestre_base or 1
    if usuario.modo_semestre == "MANUAL" or not usuario.fecha_fin_semestre:
        return {"semestre_calculado": sem_base, "modo": "Manual", "explicacion": f"Semestre {sem_base}° en curso."}
    try:
        hoy = date.today()
        fin_sem = datetime.strptime(usuario.fecha_fin_semestre, "%Y-%m-%d").date()
        inicio_sem = datetime.strptime(usuario.fecha_inicio_semestre, "%Y-%m-%d").date() if usuario.fecha_inicio_semestre else fin_sem
        if hoy <= fin_sem:
            return {"semestre_calculado": sem_base, "modo": "Automático", "explicacion": f"Cursando {sem_base}° semestre ({inicio_sem} a {fin_sem})."}
        dias_extra = (hoy - fin_sem).days
        semestres_adicionales = (dias_extra // 180) + 1
        nuevo_semestre = min(9, sem_base + semestres_adicionales)
        return {"semestre_calculado": nuevo_semestre, "modo": "Automático", "explicacion": f"Actualizado automáticamente a {nuevo_semestre}° semestre."}
    except Exception:
        return {"semestre_calculado": sem_base, "modo": "Manual", "explicacion": f"Semestre {sem_base}° activo."}

# --- ENDPOINTS DE VALIDACIÓN, REGISTRO, VERIFICACIÓN Y RECUPERACIÓN ---

@app.post("/api/auth/validar-correo")
def endpoint_validar_correo(correo: str = Form(...), db: Session = Depends(get_db)):
    correo_limpio = correo.strip().lower()
    validacion = verificar_correo_con_google_dns(correo_limpio)
    if not validacion["valido"]:
        raise HTTPException(status_code=400, detail=validacion["motivo"])

    ya_existe = db.query(Usuario).filter(Usuario.correo == correo_limpio, Usuario.cuenta_verificada == True).first()
    if ya_existe:
        raise HTTPException(status_code=400, detail="Este correo electrónico ya está registrado. Inicia sesión.")
    return validacion

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

    if len(password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres.")

    validacion_correo = verificar_correo_con_google_dns(correo_limpio)
    if not validacion_correo["valido"]:
        raise HTTPException(status_code=400, detail=validacion_correo["motivo"])

    existente = db.query(Usuario).filter(
        (Usuario.matricula == matricula_limpia) | (Usuario.correo == correo_limpio)
    ).first()

    if existente and existente.cuenta_verificada:
        raise HTTPException(status_code=400, detail="Ese Número de Control o Correo Personal ya está registrado. Inicia sesión.")

    foto_ruta = existente.foto_url if existente else None
    if foto and foto.filename:
        carpeta_perfil = os.path.join(UPLOAD_DIR, "perfiles")
        os.makedirs(carpeta_perfil, exist_ok=True)
        nombre_foto = f"{matricula_limpia}_{uuid.uuid4().hex[:6]}_{foto.filename}"
        ruta_fisica = os.path.join(carpeta_perfil, nombre_foto)
        with open(ruta_fisica, "wb") as f:
            f.write(await foto.read())
        foto_ruta = f"/archivos/perfiles/{nombre_foto}"

    codigo_otp = generar_otp_6_digitos()
    carrera = db.query(Carrera).filter_by(clave_oficial="ITIC-2010-225").first()

    if existente and not existente.cuenta_verificada:
        existente.nombre_completo = nombre_completo.strip()
        existente.matricula = matricula_limpia
        existente.correo = correo_limpio
        existente.password_hash = hashear_secreto(password)
        existente.foto_url = foto_ruta
        existente.modo_semestre = modo_semestre
        existente.semestre_base = semestre_base
        existente.fecha_inicio_semestre = fecha_inicio_semestre or None
        existente.fecha_fin_semestre = fecha_fin_semestre or None
        existente.otp_hash = hashear_secreto(codigo_otp)
        existente.otp_expiracion = datetime.utcnow() + timedelta(minutes=15)
        existente.otp_proposito = "VERIFICAR_CORREO"
        existente.otp_intentos = 0
        usuario_obj = existente
    else:
        usuario_obj = Usuario(
            nombre_completo=nombre_completo.strip(),
            matricula=matricula_limpia,
            correo=correo_limpio,
            password_hash=hashear_secreto(password),
            foto_url=foto_ruta,
            es_itics=es_itics,
            modo_semestre=modo_semestre,
            semestre_base=semestre_base,
            fecha_inicio_semestre=fecha_inicio_semestre or None,
            fecha_fin_semestre=fecha_fin_semestre or None,
            carrera_id=carrera.id if carrera else None,
            cuenta_verificada=False,
            otp_hash=hashear_secreto(codigo_otp),
            otp_expiracion=datetime.utcnow() + timedelta(minutes=15),
            otp_proposito="VERIFICAR_CORREO",
            otp_intentos=0
        )
        db.add(usuario_obj)

    db.commit()
    db.refresh(usuario_obj)

    enviado_real = enviar_correo_verificacion(usuario_obj.correo, usuario_obj.nombre_completo, codigo_otp, "VERIFICAR_CORREO")

    if not enviado_real:
        raise HTTPException(status_code=500, detail="Error en el servidor de correo. Verifica que la contraseña de 16 letras esté correctamente pegada en main.py.")

    return {
        "requiere_verificacion": True,
        "correo": usuario_obj.correo,
        "smtp_activo": enviado_real,
        "mensaje": f"Te hemos enviado un correo electrónico de verificación con un código de 6 dígitos a {usuario_obj.correo}."
    }

@app.post("/api/auth/verificar-correo")
def verificar_codigo_correo(correo: str = Form(...), codigo: str = Form(...), db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.correo == correo.strip().lower()).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="No se encontró la cuenta asociada a este correo.")

    if usuario.otp_intentos >= 5:
        raise HTTPException(status_code=429, detail="Se agotaron los intentos permitidos. Haz clic en Reenviar código.")

    if not usuario.otp_expiracion or datetime.utcnow() > usuario.otp_expiracion:
        raise HTTPException(status_code=400, detail="El código de verificación ha expirado. Solicita uno nuevo.")

    if not usuario.otp_hash or not verificar_secreto(codigo.strip(), usuario.otp_hash):
        usuario.otp_intentos += 1
        db.commit()
        restantes = max(0, 5 - usuario.otp_intentos)
        raise HTTPException(status_code=400, detail=f"El código ingresado es incorrecto. Te quedan {restantes} intentos.")

    usuario.cuenta_verificada = True
    usuario.otp_hash = None
    usuario.otp_expiracion = None
    usuario.otp_proposito = None
    usuario.otp_intentos = 0
    db.commit()

    info_sem = calcular_semestre_vigente(usuario)
    return {
        "mensaje": "Correo verificado correctamente. Bienvenido(a) a tu Portafolio Académico.",
        "usuario": {
            "id": usuario.id, "nombre": usuario.nombre_completo, "matricula": usuario.matricula,
            "correo": usuario.correo, "foto_url": usuario.foto_url, "es_itics": usuario.es_itics,
            "cuenta_verificada": True,
            "semestre_actual": info_sem["semestre_calculado"], "detalle_semestre": info_sem["explicacion"]
        }
    }

@app.post("/api/auth/reenviar-codigo")
def reenviar_codigo_verificacion(correo: str = Form(...), proposito: str = Form("VERIFICAR_CORREO"), db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.correo == correo.strip().lower()).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="El correo electrónico no está registrado.")

    nuevo_otp = generar_otp_6_digitos()
    usuario.otp_hash = hashear_secreto(nuevo_otp)
    usuario.otp_expiracion = datetime.utcnow() + timedelta(minutes=15)
    usuario.otp_proposito = proposito
    usuario.otp_intentos = 0
    db.commit()

    enviado = enviar_correo_verificacion(usuario.correo, usuario.nombre_completo, nuevo_otp, proposito)
    if not enviado:
        raise HTTPException(status_code=500, detail="No se pudo conectar con Gmail. Revisa la contraseña de aplicación en el código.")
        
    return {"mensaje": f"Se ha enviado un nuevo correo con tu código de verificación a {usuario.correo}."}

@app.post("/api/auth/login")
def login_estudiante(identificador: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    ident = identificador.strip()
    usuario = db.query(Usuario).filter(
        (Usuario.matricula == ident.upper()) | (Usuario.correo == ident.lower())
    ).first()

    if not usuario or not verificar_secreto(password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Correo/Número de control o contraseña incorrectos.")

    if not usuario.cuenta_verificada:
        nuevo_otp = generar_otp_6_digitos()
        usuario.otp_hash = hashear_secreto(nuevo_otp)
        usuario.otp_expiracion = datetime.utcnow() + timedelta(minutes=15)
        usuario.otp_proposito = "VERIFICAR_CORREO"
        usuario.otp_intentos = 0
        db.commit()
        enviar_correo_verificacion(usuario.correo, usuario.nombre_completo, nuevo_otp, "VERIFICAR_CORREO")
        return {
            "requiere_verificacion": True,
            "correo": usuario.correo,
            "mensaje": f"Se envió un correo de verificación a {usuario.correo}. Ingresa el código para activar tu cuenta."
        }

    info_sem = calcular_semestre_vigente(usuario)
    return {
        "usuario": {
            "id": usuario.id, "nombre": usuario.nombre_completo, "matricula": usuario.matricula,
            "correo": usuario.correo, "foto_url": usuario.foto_url, "es_itics": usuario.es_itics,
            "cuenta_verificada": True,
            "semestre_actual": info_sem["semestre_calculado"], "detalle_semestre": info_sem["explicacion"]
        }
    }

@app.post("/api/auth/recuperar-solicitar")
def solicitar_recuperacion_por_correo(correo: str = Form(...), db: Session = Depends(get_db)):
    correo_limpio = correo.strip().lower()
    usuario = db.query(Usuario).filter(Usuario.correo == correo_limpio).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="No encontramos ninguna cuenta registrada con ese correo electrónico.")

    codigo_otp = generar_otp_6_digitos()
    usuario.otp_hash = hashear_secreto(codigo_otp)
    usuario.otp_expiracion = datetime.utcnow() + timedelta(minutes=15)
    usuario.otp_proposito = "RECUPERAR_PASSWORD"
    usuario.otp_intentos = 0
    db.commit()

    enviado = enviar_correo_verificacion(usuario.correo, usuario.nombre_completo, codigo_otp, "RECUPERAR_PASSWORD")
    if not enviado:
        raise HTTPException(status_code=500, detail="Error enviando el correo de recuperación.")
        
    return {
        "correo": usuario.correo,
        "mensaje": f"Se ha enviado un correo de recuperación con un código de 6 dígitos a {usuario.correo}."
    }

@app.post("/api/auth/recuperar-confirmar")
def confirmar_nueva_password(
    correo: str = Form(...),
    codigo: str = Form(...),
    nueva_password: str = Form(...),
    confirmar_password: str = Form(...),
    db: Session = Depends(get_db)
):
    if nueva_password != confirmar_password:
        raise HTTPException(status_code=400, detail="Las contraseñas no coinciden.")
    if len(nueva_password) < 6:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener mínimo 6 caracteres.")

    usuario = db.query(Usuario).filter(Usuario.correo == correo.strip().lower()).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")

    if usuario.otp_intentos >= 5:
        raise HTTPException(status_code=429, detail="Demasiados intentos fallidos. Solicita un nuevo código.")

    if not usuario.otp_expiracion or datetime.utcnow() > usuario.otp_expiracion:
        raise HTTPException(status_code=400, detail="El código de verificación ha expirado.")

    if not usuario.otp_hash or not verificar_secreto(codigo.strip(), usuario.otp_hash):
        usuario.otp_intentos += 1
        db.commit()
        restantes = max(0, 5 - usuario.otp_intentos)
        raise HTTPException(status_code=400, detail=f"Código incorrecto. Intentos restantes: {restantes}.")

    usuario.password_hash = hashear_secreto(nueva_password)
    usuario.cuenta_verificada = True
    usuario.otp_hash = None
    usuario.otp_expiracion = None
    usuario.otp_proposito = None
    usuario.otp_intentos = 0
    db.commit()

    return {"mensaje": "Tu contraseña se actualizó correctamente. Ya puedes iniciar sesión."}

# --- MOTOR DE ANÁLISIS IA DE EVIDENCIAS Y PORTAFOLIO ---
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
            paginas_texto = [page.extract_text() or "" for page in lector.pages[:10]]
            texto_extraido += " ".join(paginas_texto)
        except Exception:
            pass
    elif ext == ".zip":
        try:
            with zipfile.ZipFile(io.BytesIO(contenido)) as z:
                lista_interna = z.namelist()
                texto_extraido += "Contiene: " + ", ".join(lista_interna[:50])
                for item in lista_interna[:8]:
                    if item.endswith((".py", ".kt", ".java", ".sql", ".html", ".js", ".md", ".txt", ".pl")):
                        muestra = z.read(item).decode("utf-8", errors="ignore")[:1000]
                        texto_extraido += f"\nCódigo en {item}: {muestra}"
        except Exception:
            pass
    elif ext in [".py", ".kt", ".java", ".sql", ".js", ".jsx", ".ts", ".html", ".css", ".pl", ".txt", ".md", ".json", ".csv"]:
        texto_extraido += contenido.decode("utf-8", errors="ignore")[:5000]
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

@app.get("/api/reticula/materias")
def listar_materias(estudiante_id: Optional[int] = None, db: Session = Depends(get_db)):
    materias = db.query(Materia).order_by(Materia.semestre, Materia.id).all()
    conteo_evidencias = {}
    query_ev = db.query(Evidencia).filter(Evidencia.is_deleted == False)
    if estudiante_id: query_ev = query_ev.filter(Evidencia.estudiante_id == estudiante_id)
    for ev in query_ev.all(): conteo_evidencias[ev.materia_id] = conteo_evidencias.get(ev.materia_id, 0) + 1
    return [{"id": m.id, "clave": m.clave, "nombre": m.nombre, "semestre": m.semestre, "satca": m.satca, "creditos": m.creditos, "tipo": m.tipo_asignatura, "total_evidencias": conteo_evidencias.get(m.id, 0)} for m in materias]

@app.post("/api/evidencias/subir", status_code=201)
async def subir_evidencia(estudiante_id: int = Form(...), titulo: str = Form(...), descripcion: str = Form(""), materia_id: int = Form(...), url_enlace_externo: Optional[str] = Form(None), archivos: List[UploadFile] = File(default=[]), db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == estudiante_id, Usuario.cuenta_verificada == True).first()
    if not usuario: raise HTTPException(status_code=403, detail="Tu cuenta debe estar verificada para subir archivos.")
    materia = db.query(Materia).filter(Materia.id == materia_id).first()
    competencia = db.query(Competencia).filter(Competencia.materia_id == materia.id).first()
    archivos_validos = [a for a in archivos if a.filename]
    if not archivos_validos and not url_enlace_externo: raise HTTPException(status_code=400, detail="Adjunta al menos un archivo o enlace.")

    nueva_evidencia = Evidencia(titulo=titulo, descripcion=descripcion, tipo=TipoEvidencia.MULTIPLE if len(archivos_validos) > 1 else (clasificar_extension(archivos_validos[0].filename) if archivos_validos else TipoEvidencia.ENLACE), url_enlace_externo=url_enlace_externo, estudiante_id=usuario.id, materia_id=materia.id, competencia_id=competencia.id)
    db.add(nueva_evidencia)
    db.flush()

    carpeta_destino = os.path.join(UPLOAD_DIR, usuario.matricula, f"materia_{materia.id}", f"evidencia_{nueva_evidencia.id}")
    os.makedirs(carpeta_destino, exist_ok=True)
    textos_para_ia = []

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
        registro_archivo = ArchivoEvidencia(evidencia_id=nueva_evidencia.id, nombre_original=nombre_limpio, ruta_servidor=ruta_url, mime_type=mime_detectado, tipo_archivo=tipo_arch, tamano_bytes=tamano, sha256_hash=hash_sha256, resumen_extraido_ia=texto_interno[:300])
        db.add(registro_archivo)

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
        "estudiante": {"id": estudiante.id, "nombre": estudiante.nombre_completo, "matricula": estudiante.matricula, "correo": estudiante.correo, "foto_url": estudiante.foto_url, "es_itics": estudiante.es_itics, "cuenta_verificada": estudiante.cuenta_verificada, "semestre_actual": info_sem["semestre_calculado"], "modo_semestre": info_sem["modo"], "explicacion_semestre": info_sem["explicacion"], "carrera": "Ingeniería en Tecnologías de la Información y Comunicaciones (ITIC-2010-225)", "especialidad": "Análisis de Datos (ITIE-ADD-2025-01)", "perfil_ia": perfil_ia},
        "metricas": {"total_evidencias": len(evidencias), "total_archivos": total_archivos_subidos, "materias_con_evidencia": len(materias_ordenadas), "total_materias_reticula": total_materias_db, "porcentaje_reticula": round((len(materias_ordenadas) / total_materias_db) * 100, 1), "stack_dominado": sorted(list(stack_ia_global))},
        "portafolio_por_materia": materias_ordenadas
    }