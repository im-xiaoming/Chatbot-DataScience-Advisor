from qdrant_client import models


_PAYLOAD = [
    ('doc_id', models.PayloadSchemaType.KEYWORD),
    ('chunk_id', models.PayloadSchemaType.KEYWORD),
    ('title', models.PayloadSchemaType.KEYWORD),
    ('page_content', models.PayloadSchemaType.KEYWORD),
    ('url', models.PayloadSchemaType.KEYWORD),
    ('category', models.PayloadSchemaType.KEYWORD),
    ('section_path', models.PayloadSchemaType.KEYWORD),
    ('publisher',  models.PayloadSchemaType.KEYWORD),
    ('authority',  models.PayloadSchemaType.KEYWORD),
    ('language',  models.PayloadSchemaType.KEYWORD),
    ('region',  models.PayloadSchemaType.KEYWORD),
    ('published_date',  models.PayloadSchemaType.DATETIME),
    ('valid_until',  models.PayloadSchemaType.DATETIME),
    ('license',  models.PayloadSchemaType.KEYWORD),
    ('fetched_at',  models.PayloadSchemaType.DATETIME),
    ('normalized_at',  models.PayloadSchemaType.DATETIME),
    ('pipeline_version',  models.PayloadSchemaType.KEYWORD),
]
   