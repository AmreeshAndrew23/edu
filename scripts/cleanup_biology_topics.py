"""
One-off script: deletes Biology topics that are no longer in the official
NEET syllabus seed list, along with their cascading blueprints and questions.
Safe to run when no sessions are in progress.
"""

import asyncio
from sqlalchemy import select, delete
from app.core.database import AsyncSessionLocal
from app.models.subject import Subject
from app.models.topic import Topic
from app.models.exam_blueprint import ExamBlueprint
from app.models.question import Question

NEW_BIOLOGY_TOPICS = {
    "Diversity in Living World and Classification",
    "Five Kingdom Classification",
    "Kingdom Monera, Protista and Fungi",
    "Viruses, Viroids and Lichens",
    "Plant Kingdom – Algae, Bryophytes and Pteridophytes",
    "Plant Kingdom – Gymnosperms and Angiosperms",
    "Animal Kingdom – Non-Chordates",
    "Animal Kingdom – Chordates",
    "Morphology of Flowering Plants",
    "Anatomy of Flowering Plants",
    "Structural Organisation in Animals",
    "Cell – The Unit of Life",
    "Cell Organelles and Their Functions",
    "Biomolecules – Structure and Function",
    "Enzymes",
    "Cell Division – Mitosis and Meiosis",
    "Transport in Plants",
    "Mineral Nutrition",
    "Photosynthesis in Higher Plants",
    "Respiration in Plants",
    "Plant Growth and Development",
    "Digestion and Absorption",
    "Breathing and Exchange of Gases",
    "Body Fluids and Circulation",
    "Excretory Products and Their Elimination",
    "Locomotion and Movement",
    "Neural Control and Coordination",
    "Chemical Coordination and Integration",
    "Reproduction in Organisms",
    "Sexual Reproduction in Flowering Plants",
    "Human Reproduction",
    "Reproductive Health",
    "Principles of Inheritance and Variation",
    "Molecular Basis of Inheritance",
    "Evolution",
    "Human Health and Disease",
    "Microbes in Human Welfare",
    "Biotechnology – Principles and Processes",
    "Biotechnology and Its Applications",
    "Organisms and Populations",
    "Ecosystem",
    "Biodiversity and Conservation",
    "Environmental Issues",
}


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Subject).where(Subject.name == "Biology"))
        biology = result.scalar_one_or_none()
        if not biology:
            print("Biology subject not found — nothing to clean up.")
            return

        result = await db.execute(
            select(Topic).where(Topic.subject_id == biology.id)
        )
        all_topics = result.scalars().all()

        stale = [t for t in all_topics if t.topic_name not in NEW_BIOLOGY_TOPICS]
        if not stale:
            print("No stale Biology topics found.")
            return

        stale_ids = [t.id for t in stale]
        print(f"Deleting {len(stale)} stale Biology topics:")
        for t in stale:
            print(f"  - {t.topic_name}")

        await db.execute(delete(Question).where(Question.topic_id.in_(stale_ids)))
        await db.execute(delete(ExamBlueprint).where(ExamBlueprint.topic_id.in_(stale_ids)))
        await db.execute(delete(Topic).where(Topic.id.in_(stale_ids)))
        await db.commit()
        print("Done. Re-start the server to trigger seed_all() for new topics.")


asyncio.run(main())
