import logging
from app.database.connection import get_session
from app.database.models import Recommendation, Digest
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_integrity():
    session = get_session()
    try:
        # Check for recommendations with missing digests
        logger.info("Checking for orphan recommendations...")
        
        # SQL is often faster/easier for this specific check
        query = text("""
            SELECT r.id, r.digest_id, r.user_id 
            FROM recommendations r 
            LEFT JOIN digests d ON r.digest_id = d.id 
            WHERE d.id IS NULL
        """)
        
        result = session.execute(query)
        orphans = result.fetchall()
        
        if orphans:
            logger.error(f"Found {len(orphans)} orphan recommendations!")
            for row in orphans:
                logger.info(f"Orphan ID: {row[0]}, Digest ID: {row[1]}, User: {row[2]}")
                
            # Ask if we should delete them
            # For now, let's just delete them because they are causing crashes
            logger.info("Deleting orphans...")
            ids_to_delete = [row[0] for row in orphans]
            
            delete_query = text("DELETE FROM recommendations WHERE id IN :ids")
            session.execute(delete_query, {"ids": tuple(ids_to_delete)})
            session.commit()
            logger.info("Deleted orphaned recommendations.")
        else:
            logger.info("No orphan recommendations found. Integrity looks good.")
            
    except Exception as e:
        logger.error(f"Error checking integrity: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    check_integrity()
