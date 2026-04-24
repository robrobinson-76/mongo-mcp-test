from bank_ods.db.client import get_db
from bank_ods.models.registry import ENTITIES

_indexes_created = False


async def ensure_indexes() -> None:
    global _indexes_created
    if _indexes_created:
        return
    db = get_db()
    for entity in ENTITIES:
        col = db[entity.COLLECTION]
        for keys, options in entity.INDEXES:
            await col.create_index(keys, **options)
    _indexes_created = True
