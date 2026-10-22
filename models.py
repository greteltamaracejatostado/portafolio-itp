from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, DateTime, 
    Enum, JSON, Boolean, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

class RolUsuario(str, PyEnum):
    ESTUDIANTE = "ESTUDIANTE"
    ADMIN_DOCENTE = "ADMIN_DOCENTE"

class TipoEvidencia(str, PyEnum):
    CODIGO = "CODIGO"
    DOCUMENTO = "DOCUMENTO"
    COMPRIMIDO = "COMPRIMIDO"
    IMAGEN = "IMAGEN"
    VIDEO = "VIDEO"
    ENLACE = "ENLACE"
    MULTIPLE = "MULTIPLE"
    OTRO = "OTRO"

class EstadoEvidencia(str, PyEnum):
    PENDIENTE = "PENDIENTE"
    VALIDADO = "VALIDADO"
    RECHAZADO = "RECHAZADO"

class Carrera(Base):
    __tablename__ = "carreras"
    id = Column(Integer, primary_key=True, index=True)
    clave_oficial = Column(String(30), unique=True, nullable=False)
    nombre = Column(String(150), nullable=False)
    especialidad = Column(String(150), nullable=True)
    clave_especialidad = Column(String(30), nullable=True)
    creditos_totales = Column(Integer, default=260)

    materias = relationship("Materia", back_populates="carrera")
    estudiantes = relationship("Usuario", back_populates="carrera")

class Materia(Base):
    __tablename__ = "materias"
    id = Column(Integer, primary_key=True, index=True)
    clave = Column(String(20), unique=True, nullable=False, index=True)
    nombre = Column(String(150), nullable=False)
    semestre = Column(Integer, nullable=False, index=True)
    satca = Column(String(15), nullable=False)
    creditos = Column(Integer, nullable=False)
    tipo_asignatura = Column(String(30), default="GENÉRICA")

    carrera_id = Column(Integer, ForeignKey("carreras.id"), nullable=False)
    carrera = relationship("Carrera", back_populates="materias")
    competencias = relationship("Competencia", back_populates="materia", cascade="all, delete-orphan")
    evidencias = relationship("Evidencia", back_populates="materia")

class Competencia(Base):
    __tablename__ = "competencias"
    id = Column(Integer, primary_key=True, index=True)
    numero_unidad = Column(Integer, nullable=False, default=1)
    descripcion = Column(Text, nullable=False)
    criterio_desempeno = Column(Text, nullable=True)

    materia_id = Column(Integer, ForeignKey("materias.id"), nullable=False)
    materia = relationship("Materia", back_populates="competencias")
    evidencias = relationship("Evidencia", back_populates="competencia")

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre_completo = Column(String(150), nullable=False)
    matricula = Column(String(20), unique=True, nullable=False, index=True)
    correo = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # SISTEMA DE VERIFICACIÓN TIPO GOOGLE
    cuenta_verificada = Column(Boolean, default=False)
    codigo_recuperacion = Column(String(10), nullable=True)
    expiracion_codigo = Column(DateTime, nullable=True)
    
    foto_url = Column(String(500), nullable=True)
    es_itics = Column(Boolean, default=True)
    
    modo_semestre = Column(String(20), default="AUTOMATICO")
    semestre_base = Column(Integer, default=1)
    fecha_inicio_semestre = Column(String(20), nullable=True)
    fecha_fin_semestre = Column(String(20), nullable=True)
    
    resumen_ia_cv = Column(Text, nullable=True)
    rol = Column(Enum(RolUsuario), default=RolUsuario.ESTUDIANTE, nullable=False)
    fecha_registro = Column(DateTime, default=datetime.utcnow)

    carrera_id = Column(Integer, ForeignKey("carreras.id"), nullable=True)
    carrera = relationship("Carrera", back_populates="estudiantes")
    evidencias = relationship("Evidencia", back_populates="estudiante")

class Evidencia(Base):
    __tablename__ = "evidencias"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=False)
    analisis_ia = Column(Text, nullable=True)
    tipo = Column(Enum(TipoEvidencia), default=TipoEvidencia.MULTIPLE, nullable=False)
    url_enlace_externo = Column(String(500), nullable=True)
    tags_ia_detectados = Column(String(400), nullable=True)

    estado = Column(Enum(EstadoEvidencia), default=EstadoEvidencia.VALIDADO, nullable=False)
    is_deleted = Column(Boolean, default=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    estudiante_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    materia_id = Column(Integer, ForeignKey("materias.id"), nullable=False)
    competencia_id = Column(Integer, ForeignKey("competencias.id"), nullable=False)

    estudiante = relationship("Usuario", back_populates="evidencias")
    materia = relationship("Materia", back_populates="evidencias")
    competencia = relationship("Competencia", back_populates="evidencias")
    archivos = relationship("ArchivoEvidencia", back_populates="evidencia", cascade="all, delete-orphan")
    historial_auditoria = relationship("AuditoriaEvidencia", back_populates="evidencia", cascade="all, delete-orphan")

class ArchivoEvidencia(Base):
    __tablename__ = "archivos_evidencia"
    id = Column(Integer, primary_key=True, index=True)
    evidencia_id = Column(Integer, ForeignKey("evidencias.id"), nullable=False)
    nombre_original = Column(String(255), nullable=False)
    ruta_servidor = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=False)
    tipo_archivo = Column(Enum(TipoEvidencia), nullable=False)
    tamano_bytes = Column(Integer, nullable=False)
    sha256_hash = Column(String(64), nullable=False)
    resumen_extraido_ia = Column(Text, nullable=True)
    fecha_subida = Column(DateTime, default=datetime.utcnow)

    evidencia = relationship("Evidencia", back_populates="archivos")

class AuditoriaEvidencia(Base):
    __tablename__ = "auditoria_evidencias"
    id = Column(Integer, primary_key=True, index=True)
    evidencia_id = Column(Integer, ForeignKey("evidencias.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    accion = Column(String(50), nullable=False)
    detalle_cambios = Column(JSON, nullable=False)
    fecha_evento = Column(DateTime, default=datetime.utcnow, nullable=False)

    evidencia = relationship("Evidencia", back_populates="historial_auditoria")

def inicializar_reticula_itp(db_session):
    if db_session.query(Carrera).filter_by(clave_oficial="ITIC-2010-225").first():
        return

    itics = Carrera(
        clave_oficial="ITIC-2010-225",
        nombre="Ingeniería en Tecnologías de la Información y Comunicaciones",
        especialidad="Análisis de Datos",
        clave_especialidad="ITIE-ADD-2025-01",
        creditos_totales=260
    )
    db_session.add(itics)
    db_session.flush()

    catalogo_materias = [
        (1, "ACF-2301", "Cálculo Diferencial", "3-2-5", 5, "GENÉRICA"),
        (1, "AEF-1032", "Fundamentos de Programación", "3-2-5", 5, "GENÉRICA"),
        (1, "TIF-1019", "Matemáticas Discretas I", "3-2-5", 5, "GENÉRICA"),
        (1, "TIP-1017", "Introducción a las TIC's", "3-0-3", 3, "GENÉRICA"),
        (1, "ACH-2307", "Taller de Ética", "0-4-4", 4, "GENÉRICA"),
        (1, "ACC-0906", "Fundamentos de Investigación", "2-2-4", 4, "GENÉRICA"),
        (2, "ACF-0902", "Cálculo Integral", "3-2-5", 5, "GENÉRICA"),
        (2, "AEB-1054", "Programación Orientada a Objetos", "1-4-5", 5, "GENÉRICA"),
        (2, "TIF-1020", "Matemáticas Discretas II", "3-2-5", 5, "GENÉRICA"),
        (2, "ACF-0903", "Álgebra Lineal", "3-2-5", 5, "GENÉRICA"),
        (2, "TIF-1009", "Contabilidad y Costos", "3-2-5", 5, "GENÉRICA"),
        (2, "AEF-1052", "Probabilidad y Estadística", "3-2-5", 5, "GENÉRICA"),
        (3, "TIE-1018", "Matemáticas Aplicadas a Comunicaciones", "3-1-4", 4, "GENÉRICA"),
        (3, "TID-1012", "Estructuras y Organización de Datos", "2-3-5", 5, "GENÉRICA"),
        (3, "TIF-1021", "Matemáticas para la Toma de Decisiones", "3-2-5", 5, "GENÉRICA"),
        (3, "ACD-0908", "Desarrollo Sustentable", "2-3-5", 5, "GENÉRICA"),
        (3, "TIC-1011", "Electricidad y Magnetismo", "2-2-4", 4, "GENÉRICA"),
        (3, "TIF-1013", "Fundamentos de Redes", "3-2-5", 5, "GENÉRICA"),
        (4, "TID-1004", "Análisis de Señales y Sistemas de Comunicación", "2-3-5", 5, "GENÉRICA"),
        (4, "AEF-1031", "Fundamentos de Base de Datos", "3-2-5", 5, "GENÉRICA"),
        (4, "AEC-1061", "Sistemas Operativos I", "2-2-4", 4, "GENÉRICA"),
        (4, "TID-1010", "Desarrollo de Emprendedores", "2-3-5", 5, "GENÉRICA"),
        (4, "TID-1008", "Circuitos Eléctricos y Electrónicos", "2-3-5", 5, "GENÉRICA"),
        (4, "TIF-1025", "Redes de Computadoras", "3-2-5", 5, "GENÉRICA"),
        (5, "TIF-1029", "Telecomunicaciones", "3-2-5", 5, "GENÉRICA"),
        (5, "AEH-1063", "Taller de Base de Datos", "1-3-4", 4, "GENÉRICA"),
        (5, "TIB-1024", "Programación II", "1-4-5", 5, "GENÉRICA"),
        (5, "AED-1062", "Sistemas Operativos II", "2-3-5", 5, "GENÉRICA"),
        (5, "TIC-1005", "Arquitectura de Computadoras", "2-2-4", 4, "GENÉRICA"),
        (5, "TIF-1026", "Redes Emergentes", "3-2-5", 5, "GENÉRICA"),
        (6, "TIC-1028", "Tecnologías Inalámbricas", "2-2-4", 4, "GENÉRICA"),
        (6, "TIF-1007", "Base de Datos Distribuidas", "3-2-5", 5, "GENÉRICA"),
        (6, "AEB-1055", "Programación Web", "1-4-5", 5, "GENÉRICA"),
        (6, "TIC-1014", "Ingeniería de Software", "2-2-4", 4, "GENÉRICA"),
        (6, "TIH-1016", "Interacción Humano Computadora", "1-3-4", 4, "GENÉRICA"),
        (6, "TIF-1003", "Administración y Seguridad de Redes", "3-2-5", 5, "GENÉRICA"),
        (7, "ACA-0909", "Taller de Investigación I", "0-4-4", 4, "GENÉRICA"),
        (7, "TIC-1022", "Negocios Electrónicos I", "2-2-4", 4, "GENÉRICA"),
        (7, "AEB-1011", "Desarrollo de Aplicaciones para Dispositivos Móviles", "1-4-5", 5, "GENÉRICA"),
        (7, "TIC-1027", "Taller de Ingeniería de Software", "2-2-4", 4, "GENÉRICA"),
        (7, "TIC-1002", "Administración Gerencial", "2-2-4", 4, "GENÉRICA"),
        (7, "ADD-2505", "SQL para exploración de datos", "2-3-5", 5, "ESPECIALIDAD_OPTATIVA"),
        (8, "ACA-0910", "Taller de Investigación II", "0-4-4", 4, "GENÉRICA"),
        (8, "TIC-1023", "Negocios Electrónicos II", "2-2-4", 4, "GENÉRICA"),
        (8, "TIC-1006", "Auditoría en Tecnologías de la Información", "2-2-4", 4, "GENÉRICA"),
        (8, "TIC-1015", "Ingeniería del Conocimiento", "2-2-4", 4, "GENÉRICA"),
        (8, "TIF-1001", "Administración de Proyectos", "3-2-5", 5, "GENÉRICA"),
        (8, "ADD-2507", "Introducción al aprendizaje automático", "2-3-5", 5, "ESPECIALIDAD_OPTATIVA"),
        (9, "ADD-2501", "Estadística para análisis de datos", "2-3-5", 5, "ESPECIALIDAD_OBLIGATORIA"),
        (9, "ADV-2502", "Herramientas avanzadas para el análisis de datos", "0-5-5", 5, "ESPECIALIDAD_OBLIGATORIA"),
        (9, "ADV-2503", "Programación para análisis de datos", "0-5-5", 5, "ESPECIALIDAD_OBLIGATORIA"),
        (9, "ADB-2504", "Ciberseguridad", "1-4-5", 5, "ESPECIALIDAD_OBLIGATORIA"),
        (9, "ADD-2506", "Exploración de bases de datos no relacionales", "2-3-5", 5, "ESPECIALIDAD_OPTATIVA"),
        (9, "RES-0001", "Residencia Profesional", "0-0-10", 10, "RESIDENCIA")
    ]

    for sem, clave, nombre, satca, cred, tipo in catalogo_materias:
        mat = Materia(clave=clave, nombre=nombre, semestre=sem, satca=satca, creditos=cred, tipo_asignatura=tipo, carrera_id=itics.id)
        db_session.add(mat)
        db_session.flush()
        db_session.add(Competencia(numero_unidad=1, descripcion=f"Competencia acreditada en {nombre}.", criterio_desempeno="Evidencia analizada y verificada.", materia_id=mat.id))
    db_session.commit()