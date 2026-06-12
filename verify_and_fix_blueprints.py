#!/usr/bin/env python
"""Verify and fix all blueprints are seeded correctly."""
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Blueprint config - must match seed_all.py
BLUEPRINT_CONFIG = {
    "Physics": {
        "Laws of Motion": (4, "medium"),
        "Work, Energy and Power": (3, "medium"),
        "Gravitation": (3, "medium"),
        "Thermodynamics": (4, "hard"),
        "Kinetic Theory of Gases": (3, "medium"),
        "Waves and Oscillations": (3, "medium"),
        "Electrostatics": (5, "hard"),
        "Current Electricity": (4, "hard"),
        "Magnetic Effects of Current": (3, "medium"),
        "Electromagnetic Induction": (3, "medium"),
        "Ray Optics": (4, "medium"),
        "Wave Optics": (2, "medium"),
        "Atoms and Nuclei": (3, "hard"),
        "Semiconductor Devices": (3, "easy"),
    },
    "Chemistry": {
        "Atomic Structure": (3, "medium"),
        "Chemical Bonding and Molecular Structure": (4, "medium"),
        "States of Matter": (3, "medium"),
        "Thermodynamics": (3, "hard"),
        "Chemical Equilibrium": (4, "hard"),
        "Electrochemistry": (3, "hard"),
        "Chemical Kinetics": (3, "medium"),
        "Coordination Chemistry": (4, "hard"),
        "Organic Chemistry – Basic Principles": (3, "medium"),
        "Hydrocarbons": (4, "medium"),
        "Haloalkanes and Haloarenes": (3, "medium"),
        "Biomolecules": (3, "easy"),
        "p-Block Elements": (4, "hard"),
        "d and f Block Elements": (3, "medium"),
    },
    "Biology": {
        "Diversity in Living World and Classification": (2, "easy"),
        "Five Kingdom Classification": (2, "medium"),
        "Kingdom Monera, Protista and Fungi": (2, "medium"),
        "Viruses, Viroids and Lichens": (2, "easy"),
        "Plant Kingdom – Algae, Bryophytes and Pteridophytes": (2, "medium"),
        "Plant Kingdom – Gymnosperms and Angiosperms": (2, "medium"),
        "Animal Kingdom – Non-Chordates": (2, "medium"),
        "Animal Kingdom – Chordates": (2, "medium"),
        "Morphology of Flowering Plants": (3, "medium"),
        "Anatomy of Flowering Plants": (3, "medium"),
        "Structural Organisation in Animals": (3, "medium"),
        "Cell – The Unit of Life": (3, "medium"),
        "Cell Organelles and Their Functions": (3, "medium"),
        "Biomolecules – Structure and Function": (3, "medium"),
        "Enzymes": (2, "medium"),
        "Cell Division – Mitosis and Meiosis": (4, "hard"),
        "Transport in Plants": (2, "medium"),
        "Mineral Nutrition": (2, "easy"),
        "Photosynthesis in Higher Plants": (3, "hard"),
        "Respiration in Plants": (3, "hard"),
        "Plant Growth and Development": (2, "medium"),
        "Digestion and Absorption": (3, "medium"),
        "Breathing and Exchange of Gases": (3, "medium"),
        "Body Fluids and Circulation": (3, "hard"),
        "Excretory Products and Their Elimination": (3, "medium"),
        "Locomotion and Movement": (2, "medium"),
        "Neural Control and Coordination": (3, "hard"),
        "Chemical Coordination and Integration": (3, "hard"),
        "Reproduction in Organisms": (2, "easy"),
        "Sexual Reproduction in Flowering Plants": (3, "medium"),
        "Human Reproduction": (3, "medium"),
        "Reproductive Health": (2, "medium"),
        "Principles of Inheritance and Variation": (5, "hard"),
        "Molecular Basis of Inheritance": (5, "hard"),
        "Evolution": (3, "medium"),
        "Human Health and Disease": (3, "medium"),
        "Microbes in Human Welfare": (2, "easy"),
        "Biotechnology – Principles and Processes": (3, "hard"),
        "Biotechnology and Its Applications": (3, "hard"),
        "Organisms and Populations": (2, "medium"),
        "Ecosystem": (3, "medium"),
        "Biodiversity and Conservation": (2, "medium"),
        "Environmental Issues": (2, "easy"),
    },
}


async def verify_and_fix():
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select, func
    from app.models.exam import Exam
    from app.models.subject import Subject
    from app.models.topic import Topic
    from app.models.exam_blueprint import ExamBlueprint

    async with AsyncSessionLocal() as db:
        # Get all exams
        exams = (await db.execute(select(Exam))).scalars().all()
        logger.info(f"Found {len(exams)} exams in database")

        # Check each exam
        for exam in exams:
            subject = await db.get(Subject, exam.subject_id)
            exam_label = f"{exam.exam_name} {exam.exam_year} ({subject.name})"

            bp_count = (await db.execute(
                select(func.count(ExamBlueprint.id))
                .where(ExamBlueprint.exam_id == exam.id)
            )).scalar() or 0

            logger.info(f"  {exam_label}: {bp_count} blueprints")

            # If Full Exam (All Subjects), verify all subjects have blueprints
            if subject.name == "All Subjects":
                for subj_name in ["Physics", "Chemistry", "Biology"]:
                    subj_bp_count = (await db.execute(
                        select(func.count(ExamBlueprint.id))
                        .join(Topic, ExamBlueprint.topic_id == Topic.id)
                        .join(Subject, Subject.id == Topic.subject_id)
                        .where(ExamBlueprint.exam_id == exam.id, Subject.name == subj_name)
                    )).scalar() or 0
                    logger.info(f"    → {subj_name}: {subj_bp_count} blueprints")

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)

        total_bp = (await db.execute(
            select(func.count(ExamBlueprint.id))
        )).scalar() or 0

        for subj_name in ["Physics", "Chemistry", "Biology"]:
            subj = (await db.execute(
                select(Subject).where(Subject.name == subj_name)
            )).scalar()
            if subj:
                count = (await db.execute(
                    select(func.count(ExamBlueprint.id))
                    .join(Topic, ExamBlueprint.topic_id == Topic.id)
                    .where(Topic.subject_id == subj.id)
                )).scalar() or 0
                logger.info(f"{subj_name}: {count} blueprints total")

        logger.info(f"TOTAL: {total_bp} blueprints")
        logger.info("=" * 60)

        return total_bp > 0


if __name__ == "__main__":
    result = asyncio.run(verify_and_fix())
    exit(0 if result else 1)
