from sqlalchemy import select
from app.models.subject import Subject


SUBJECTS = [
    "Physics",
    "Chemistry",
    "Biology",
    "Botany",
    "Zoology"
]

async def seed_subjects(db):

     for subject_name in SUBJECTS:
          
          result = await db.execute(
               select(Subject).where(
                subject_name == subject_name
               )
          )
          existing_subject = result.scalar_one_or_none()

          if not existing_subject:
               Subject= Subject(
                    name=subject_name
               )

               db.add(Subject)
          await db.commit
     

