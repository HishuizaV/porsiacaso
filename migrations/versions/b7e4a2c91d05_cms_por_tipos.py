"""CMS por tipos: detalles por dominio, enlaces, instituciones, ajustes y bitácora

Migración ADITIVA: solo crea tablas y agrega columnas opcionales o con valor por
defecto. No borra ni modifica filas existentes (los artículos actuales quedan como
tipo «noticia» y conservan id, slug y URL).

Revision ID: b7e4a2c91d05
Revises: f176f384db00
Create Date: 2026-10-13 03:30:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'b7e4a2c91d05'
down_revision = 'f176f384db00'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'institucion',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=120), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('siglas', sa.String(length=40), nullable=True),
        sa.Column('sector', sa.String(length=20), nullable=True),
        sa.Column('web', sa.String(length=300), nullable=True),
        sa.Column('logo', sa.String(length=120), nullable=True),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('creado', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='uq_institucion_slug'),
    )
    op.create_table(
        'ajuste',
        sa.Column('clave', sa.String(length=60), nullable=False),
        sa.Column('valor', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('clave'),
    )
    op.create_table(
        'registro',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fecha', sa.DateTime(), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('accion', sa.String(length=40), nullable=False),
        sa.Column('detalle', sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], name='fk_registro_usuario'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_registro_fecha', 'registro', ['fecha'])

    with op.batch_alter_table('articulo', schema=None) as b:
        b.add_column(sa.Column('tipo', sa.String(length=20), nullable=False, server_default='noticia'))
        b.add_column(sa.Column('imagen_ancho', sa.Integer(), nullable=True))
        b.add_column(sa.Column('imagen_alto', sa.Integer(), nullable=True))
        b.add_column(sa.Column('fuente_nombre', sa.String(length=150), nullable=True))
        b.add_column(sa.Column('fecha_limite', sa.Date(), nullable=True))
        b.add_column(sa.Column('vigencia', sa.String(length=15), nullable=True))
        b.add_column(sa.Column('verificado_en', sa.Date(), nullable=True))
        b.add_column(sa.Column('aviso', sa.Text(), nullable=True))
        b.add_column(sa.Column('faq_json', sa.Text(), nullable=True))
        b.add_column(sa.Column('notas_internas', sa.Text(), nullable=True))
        b.add_column(sa.Column('busqueda', sa.Text(), nullable=True))
        b.add_column(sa.Column('busqueda_titulo', sa.String(length=300), nullable=True))
        b.add_column(sa.Column('institucion_id', sa.Integer(), nullable=True))
        b.create_foreign_key('fk_articulo_institucion', 'institucion', ['institucion_id'], ['id'])
        b.create_index('ix_articulo_tipo', ['tipo'])
        b.create_index('ix_articulo_fecha_limite', ['fecha_limite'])
        b.create_index('ix_articulo_institucion_id', ['institucion_id'])
        b.create_index('ix_articulo_estado_fecha', ['estado', 'fecha_publicacion'])

    with op.batch_alter_table('pagina', schema=None) as b:
        b.add_column(sa.Column('visible', sa.Boolean(), nullable=False, server_default=sa.true()))

    op.create_table(
        'detalle_empleo',
        sa.Column('articulo_id', sa.Integer(), nullable=False),
        sa.Column('cargo', sa.String(length=200)),
        sa.Column('codigo', sa.String(length=80)),
        sa.Column('tipo_convocatoria', sa.String(length=20)),
        sa.Column('sector', sa.String(length=20)),
        sa.Column('vacantes', sa.Integer()),
        sa.Column('modalidad', sa.String(length=15)),
        sa.Column('jornada', sa.String(length=15)),
        sa.Column('tipo_contrato', sa.String(length=20)),
        sa.Column('sueldo_min', sa.Numeric(10, 2)),
        sa.Column('sueldo_max', sa.Numeric(10, 2)),
        sa.Column('moneda', sa.String(length=3)),
        sa.Column('lugar', sa.String(length=200)),
        sa.Column('nivel_educativo', sa.String(length=20)),
        sa.Column('formacion', sa.Text()),
        sa.Column('experiencia', sa.Text()),
        sa.Column('competencias', sa.Text()),
        sa.Column('funciones', sa.Text()),
        sa.ForeignKeyConstraint(['articulo_id'], ['articulo.id'], name='fk_detalle_empleo_articulo'),
        sa.PrimaryKeyConstraint('articulo_id'),
    )
    op.create_index('ix_detalle_empleo_modalidad', 'detalle_empleo', ['modalidad'])
    op.create_index('ix_detalle_empleo_nivel_educativo', 'detalle_empleo', ['nivel_educativo'])
    op.create_table(
        'detalle_beca',
        sa.Column('articulo_id', sa.Integer(), nullable=False),
        sa.Column('publico', sa.String(length=300)),
        sa.Column('nivel', sa.String(length=120)),
        sa.Column('lugar_estudio', sa.String(length=200)),
        sa.Column('modalidad', sa.String(length=15)),
        sa.Column('vacantes', sa.Integer()),
        sa.Column('requisitos', sa.Text()),
        sa.Column('cobertura', sa.Text()),
        sa.Column('beneficios', sa.Text()),
        sa.Column('pasos', sa.Text()),
        sa.ForeignKeyConstraint(['articulo_id'], ['articulo.id'], name='fk_detalle_beca_articulo'),
        sa.PrimaryKeyConstraint('articulo_id'),
    )
    op.create_table(
        'detalle_curso',
        sa.Column('articulo_id', sa.Integer(), nullable=False),
        sa.Column('nivel', sa.String(length=80)),
        sa.Column('modalidad', sa.String(length=15)),
        sa.Column('costo', sa.String(length=15)),
        sa.Column('costo_detalle', sa.String(length=200)),
        sa.Column('duracion', sa.String(length=120)),
        sa.Column('fecha_inicio', sa.Date()),
        sa.Column('horario', sa.String(length=200)),
        sa.Column('certificado', sa.String(length=15)),
        sa.Column('requisitos', sa.Text()),
        sa.Column('temario', sa.Text()),
        sa.ForeignKeyConstraint(['articulo_id'], ['articulo.id'], name='fk_detalle_curso_articulo'),
        sa.PrimaryKeyConstraint('articulo_id'),
    )
    op.create_index('ix_detalle_curso_costo', 'detalle_curso', ['costo'])
    op.create_table(
        'detalle_beneficio',
        sa.Column('articulo_id', sa.Integer(), nullable=False),
        sa.Column('poblacion', sa.String(length=300)),
        sa.Column('monto', sa.String(length=120)),
        sa.Column('cronograma', sa.Text()),
        sa.Column('requisitos', sa.Text()),
        sa.Column('pasos', sa.Text()),
        sa.ForeignKeyConstraint(['articulo_id'], ['articulo.id'], name='fk_detalle_beneficio_articulo'),
        sa.PrimaryKeyConstraint('articulo_id'),
    )
    op.create_table(
        'detalle_tramite',
        sa.Column('articulo_id', sa.Integer(), nullable=False),
        sa.Column('finalidad', sa.String(length=300)),
        sa.Column('costo', sa.String(length=150)),
        sa.Column('plazo', sa.String(length=150)),
        sa.Column('canal', sa.String(length=15)),
        sa.Column('lugar_atencion', sa.String(length=250)),
        sa.Column('documentos', sa.Text()),
        sa.Column('requisitos', sa.Text()),
        sa.Column('pasos', sa.Text()),
        sa.ForeignKeyConstraint(['articulo_id'], ['articulo.id'], name='fk_detalle_tramite_articulo'),
        sa.PrimaryKeyConstraint('articulo_id'),
    )
    op.create_table(
        'enlace',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('articulo_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('etiqueta', sa.String(length=80)),
        sa.Column('url', sa.String(length=500)),
        sa.Column('archivo', sa.String(length=120)),
        sa.Column('orden', sa.Integer()),
        sa.ForeignKeyConstraint(['articulo_id'], ['articulo.id'], name='fk_enlace_articulo'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_enlace_articulo_id', 'enlace', ['articulo_id'])


def downgrade():
    op.drop_index('ix_enlace_articulo_id', table_name='enlace')
    op.drop_table('enlace')
    op.drop_table('detalle_tramite')
    op.drop_table('detalle_beneficio')
    op.drop_index('ix_detalle_curso_costo', table_name='detalle_curso')
    op.drop_table('detalle_curso')
    op.drop_table('detalle_beca')
    op.drop_index('ix_detalle_empleo_nivel_educativo', table_name='detalle_empleo')
    op.drop_index('ix_detalle_empleo_modalidad', table_name='detalle_empleo')
    op.drop_table('detalle_empleo')
    with op.batch_alter_table('pagina', schema=None) as b:
        b.drop_column('visible')
    with op.batch_alter_table('articulo', schema=None) as b:
        b.drop_index('ix_articulo_estado_fecha')
        b.drop_index('ix_articulo_institucion_id')
        b.drop_index('ix_articulo_fecha_limite')
        b.drop_index('ix_articulo_tipo')
        b.drop_constraint('fk_articulo_institucion', type_='foreignkey')
        for col in ('institucion_id', 'busqueda_titulo', 'busqueda', 'notas_internas', 'faq_json',
                    'aviso', 'verificado_en', 'vigencia', 'fecha_limite', 'fuente_nombre',
                    'imagen_alto', 'imagen_ancho', 'tipo'):
            b.drop_column(col)
    op.drop_index('ix_registro_fecha', table_name='registro')
    op.drop_table('registro')
    op.drop_table('ajuste')
    op.drop_table('institucion')
