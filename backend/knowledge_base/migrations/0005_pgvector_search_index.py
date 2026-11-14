from django.db import migrations


def enable_pgvector(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('CREATE EXTENSION IF NOT EXISTS vector')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS knowledge_base_chunk_embedding_hnsw '
            'ON knowledge_base_documentchunk USING hnsw '
            '(embedding vector_cosine_ops)'
        )


def disable_pgvector(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'DROP INDEX IF EXISTS knowledge_base_chunk_embedding_hnsw'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_base', '0004_documentchunk_embedding_dimension'),
    ]

    operations = [
        migrations.RunPython(enable_pgvector, disable_pgvector),
    ]
