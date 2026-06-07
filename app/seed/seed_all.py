"""
Master seed runner. Runs once on startup in dependency order:
  Subjects → Topics → Exams → Blueprints

All operations are idempotent — safe to run repeatedly.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subject import Subject
from app.models.topic import Topic
from app.models.exam import Exam
from app.models.exam_blueprint import ExamBlueprint
from app.seed.location_seed import seed_locations


# ── Subjects ──────────────────────────────────────────────────────────────────

# Core subjects (have their own topics)
SUBJECTS = ["Physics", "Chemistry", "Biology"]

# Sentinel subject used only as FK for the combined full-NEET exam rows.
# No topics are seeded under this subject directly.
FULL_EXAM_SUBJECT = "All Subjects"


# ── Topics per subject ────────────────────────────────────────────────────────

TOPICS: dict[str, list[str]] = {
    "Physics": [
        "Laws of Motion",
        "Work, Energy and Power",
        "Gravitation",
        "Thermodynamics",
        "Kinetic Theory of Gases",
        "Waves and Oscillations",
        "Electrostatics",
        "Current Electricity",
        "Magnetic Effects of Current",
        "Electromagnetic Induction",
        "Ray Optics",
        "Wave Optics",
        "Atoms and Nuclei",
        "Semiconductor Devices",
    ],
    "Chemistry": [
        "Atomic Structure",
        "Chemical Bonding and Molecular Structure",
        "States of Matter",
        "Thermodynamics",
        "Chemical Equilibrium",
        "Electrochemistry",
        "Chemical Kinetics",
        "Coordination Chemistry",
        "Organic Chemistry – Basic Principles",
        "Hydrocarbons",
        "Haloalkanes and Haloarenes",
        "Biomolecules",
        "p-Block Elements",
        "d and f Block Elements",
    ],
    "Biology": [
        # Unit 1 – Diversity in Living World
        "Diversity in Living World and Classification",
        "Five Kingdom Classification",
        "Kingdom Monera, Protista and Fungi",
        "Viruses, Viroids and Lichens",
        "Plant Kingdom – Algae, Bryophytes and Pteridophytes",
        "Plant Kingdom – Gymnosperms and Angiosperms",
        "Animal Kingdom – Non-Chordates",
        "Animal Kingdom – Chordates",
        # Unit 2 – Structural Organisation in Animals and Plants
        "Morphology of Flowering Plants",
        "Anatomy of Flowering Plants",
        "Structural Organisation in Animals",
        # Unit 3 – Cell Structure and Function
        "Cell – The Unit of Life",
        "Cell Organelles and Their Functions",
        "Biomolecules – Structure and Function",
        "Enzymes",
        "Cell Division – Mitosis and Meiosis",
        # Unit 4 – Plant Physiology
        "Transport in Plants",
        "Mineral Nutrition",
        "Photosynthesis in Higher Plants",
        "Respiration in Plants",
        "Plant Growth and Development",
        # Unit 5 – Human Physiology
        "Digestion and Absorption",
        "Breathing and Exchange of Gases",
        "Body Fluids and Circulation",
        "Excretory Products and Their Elimination",
        "Locomotion and Movement",
        "Neural Control and Coordination",
        "Chemical Coordination and Integration",
        # Unit 6 – Reproduction
        "Reproduction in Organisms",
        "Sexual Reproduction in Flowering Plants",
        "Human Reproduction",
        "Reproductive Health",
        # Unit 7 – Genetics and Evolution
        "Principles of Inheritance and Variation",
        "Molecular Basis of Inheritance",
        "Evolution",
        # Unit 8 – Biology and Human Welfare
        "Human Health and Disease",
        "Microbes in Human Welfare",
        # Unit 9 – Biotechnology
        "Biotechnology – Principles and Processes",
        "Biotechnology and Its Applications",
        # Unit 10 – Ecology and Environment
        "Organisms and Populations",
        "Ecosystem",
        "Biodiversity and Conservation",
        "Environmental Issues",
    ],
}


# ── Exams (name, year) ────────────────────────────────────────────────────────

EXAM_YEARS = [2023, 2024, 2025, 2026]
EXAM_NAME = "NEET"


# ── Blueprint config per subject: (expected_questions, difficulty) ───────────

BLUEPRINT_CONFIG: dict[str, dict[str, tuple[int, str]]] = {
    "Physics": {
        "Laws of Motion":               (4, "medium"),
        "Work, Energy and Power":       (3, "medium"),
        "Gravitation":                  (3, "medium"),
        "Thermodynamics":               (4, "hard"),
        "Kinetic Theory of Gases":      (3, "medium"),
        "Waves and Oscillations":       (3, "medium"),
        "Electrostatics":               (5, "hard"),
        "Current Electricity":          (4, "hard"),
        "Magnetic Effects of Current":  (3, "medium"),
        "Electromagnetic Induction":    (3, "medium"),
        "Ray Optics":                   (4, "medium"),
        "Wave Optics":                  (2, "medium"),
        "Atoms and Nuclei":             (3, "hard"),
        "Semiconductor Devices":        (3, "easy"),
    },
    "Chemistry": {
        "Atomic Structure":                          (3, "medium"),
        "Chemical Bonding and Molecular Structure":  (4, "medium"),
        "States of Matter":                          (3, "medium"),
        "Thermodynamics":                            (3, "hard"),
        "Chemical Equilibrium":                      (4, "hard"),
        "Electrochemistry":                          (3, "hard"),
        "Chemical Kinetics":                         (3, "medium"),
        "Coordination Chemistry":                    (4, "hard"),
        "Organic Chemistry – Basic Principles":      (3, "medium"),
        "Hydrocarbons":                              (4, "medium"),
        "Haloalkanes and Haloarenes":                (3, "medium"),
        "Biomolecules":                              (3, "easy"),
        "p-Block Elements":                          (4, "hard"),
        "d and f Block Elements":                    (3, "medium"),
    },
    "Biology": {
        # Unit 1 – Diversity in Living World
        "Diversity in Living World and Classification":       (2, "easy"),
        "Five Kingdom Classification":                        (2, "medium"),
        "Kingdom Monera, Protista and Fungi":                 (2, "medium"),
        "Viruses, Viroids and Lichens":                       (2, "easy"),
        "Plant Kingdom – Algae, Bryophytes and Pteridophytes":(2, "medium"),
        "Plant Kingdom – Gymnosperms and Angiosperms":        (2, "medium"),
        "Animal Kingdom – Non-Chordates":                     (2, "medium"),
        "Animal Kingdom – Chordates":                         (2, "medium"),
        # Unit 2 – Structural Organisation in Animals and Plants
        "Morphology of Flowering Plants":                     (3, "medium"),
        "Anatomy of Flowering Plants":                        (3, "medium"),
        "Structural Organisation in Animals":                 (3, "medium"),
        # Unit 3 – Cell Structure and Function
        "Cell – The Unit of Life":                            (3, "medium"),
        "Cell Organelles and Their Functions":                (3, "medium"),
        "Biomolecules – Structure and Function":              (3, "medium"),
        "Enzymes":                                            (2, "medium"),
        "Cell Division – Mitosis and Meiosis":                (4, "hard"),
        # Unit 4 – Plant Physiology
        "Transport in Plants":                                (2, "medium"),
        "Mineral Nutrition":                                  (2, "easy"),
        "Photosynthesis in Higher Plants":                    (3, "hard"),
        "Respiration in Plants":                              (3, "hard"),
        "Plant Growth and Development":                       (2, "medium"),
        # Unit 5 – Human Physiology
        "Digestion and Absorption":                           (3, "medium"),
        "Breathing and Exchange of Gases":                    (3, "medium"),
        "Body Fluids and Circulation":                        (3, "hard"),
        "Excretory Products and Their Elimination":           (3, "medium"),
        "Locomotion and Movement":                            (2, "medium"),
        "Neural Control and Coordination":                    (3, "hard"),
        "Chemical Coordination and Integration":              (3, "hard"),
        # Unit 6 – Reproduction
        "Reproduction in Organisms":                          (2, "easy"),
        "Sexual Reproduction in Flowering Plants":            (3, "medium"),
        "Human Reproduction":                                 (3, "medium"),
        "Reproductive Health":                                (2, "medium"),
        # Unit 7 – Genetics and Evolution
        "Principles of Inheritance and Variation":            (5, "hard"),
        "Molecular Basis of Inheritance":                     (5, "hard"),
        "Evolution":                                          (3, "medium"),
        # Unit 8 – Biology and Human Welfare
        "Human Health and Disease":                           (3, "medium"),
        "Microbes in Human Welfare":                          (2, "easy"),
        # Unit 9 – Biotechnology
        "Biotechnology – Principles and Processes":           (3, "hard"),
        "Biotechnology and Its Applications":                 (3, "hard"),
        # Unit 10 – Ecology and Environment
        "Organisms and Populations":                          (2, "medium"),
        "Ecosystem":                                          (3, "medium"),
        "Biodiversity and Conservation":                      (2, "medium"),
        "Environmental Issues":                               (2, "easy"),
    },
}


# ── Runner ────────────────────────────────────────────────────────────────────

async def seed_all(db: AsyncSession) -> None:
    await seed_locations(db)
    subject_map = await _seed_subjects(db)
    topic_map = await _seed_topics(db, subject_map)
    exam_map = await _seed_exams(db, subject_map)
    await _seed_blueprints(db, subject_map, topic_map, exam_map)


async def _seed_subjects(db: AsyncSession) -> dict[str, int]:
    """Returns {subject_name: subject_id} for core subjects + the full-exam sentinel."""
    subject_map: dict[str, int] = {}

    for name in [*SUBJECTS, FULL_EXAM_SUBJECT]:
        result = await db.execute(select(Subject).where(Subject.name == name))
        existing = result.scalar_one_or_none()

        if not existing:
            subject = Subject(name=name)
            db.add(subject)
            await db.flush()
            subject_map[name] = subject.id
        else:
            subject_map[name] = existing.id

    await db.commit()
    return subject_map


async def _seed_topics(db: AsyncSession, subject_map: dict[str, int]) -> dict[tuple[str, str], int]:
    """Returns {(subject_name, topic_name): topic_id}"""
    topic_map: dict[tuple[str, str], int] = {}

    for subject_name, topic_names in TOPICS.items():
        subject_id = subject_map[subject_name]

        for topic_name in topic_names:
            result = await db.execute(
                select(Topic).where(
                    Topic.subject_id == subject_id,
                    Topic.topic_name == topic_name,
                )
            )
            existing = result.scalar_one_or_none()

            if not existing:
                topic = Topic(topic_name=topic_name, subject_id=subject_id)
                db.add(topic)
                await db.flush()
                topic_map[(subject_name, topic_name)] = topic.id
            else:
                topic_map[(subject_name, topic_name)] = existing.id

    await db.commit()
    return topic_map


async def _seed_exams(db: AsyncSession, subject_map: dict[str, int]) -> dict[tuple[str, int], int]:
    """
    Creates exam rows:
      - One per (core subject, year)  e.g. NEET 2026 – Physics
      - One per year under FULL_EXAM_SUBJECT  e.g. NEET 2026 – Full Exam
    Returns {(subject_name, year): exam_id}
    """
    exam_map: dict[tuple[str, int], int] = {}

    for year in EXAM_YEARS:
        # Per-subject exams
        for subject_name in SUBJECTS:
            subject_id = subject_map[subject_name]
            result = await db.execute(
                select(Exam).where(
                    Exam.exam_name == EXAM_NAME,
                    Exam.exam_year == year,
                    Exam.subject_id == subject_id,
                )
            )
            existing = result.scalar_one_or_none()
            if not existing:
                exam = Exam(
                    exam_name=EXAM_NAME,
                    exam_year=year,
                    subject_id=subject_id,
                    description=f"{EXAM_NAME} {year} — {subject_name}",
                )
                db.add(exam)
                await db.flush()
                exam_map[(subject_name, year)] = exam.id
            else:
                exam_map[(subject_name, year)] = existing.id

        # Combined full-NEET exam for this year
        full_subject_id = subject_map[FULL_EXAM_SUBJECT]
        result = await db.execute(
            select(Exam).where(
                Exam.exam_name == EXAM_NAME,
                Exam.exam_year == year,
                Exam.subject_id == full_subject_id,
            )
        )
        existing = result.scalar_one_or_none()
        if not existing:
            exam = Exam(
                exam_name=EXAM_NAME,
                exam_year=year,
                subject_id=full_subject_id,
                description=f"{EXAM_NAME} {year} — Full Exam (Physics + Chemistry + Biology)",
            )
            db.add(exam)
            await db.flush()
            exam_map[(FULL_EXAM_SUBJECT, year)] = exam.id
        else:
            exam_map[(FULL_EXAM_SUBJECT, year)] = existing.id

    await db.commit()
    return exam_map


async def _seed_blueprints(
    db: AsyncSession,
    subject_map: dict[str, int],
    topic_map: dict[tuple[str, str], int],
    exam_map: dict[tuple[str, int], int],
) -> None:
    """
    Blueprint entries for:
      - Per-subject exams: topics belonging to that subject only
      - Full exam: every topic from every subject (all 44 topics)
    """

    async def _add_blueprint(exam_id: int, topic_id: int, expected_q: int, difficulty: str) -> None:
        result = await db.execute(
            select(ExamBlueprint).where(
                ExamBlueprint.exam_id == exam_id,
                ExamBlueprint.topic_id == topic_id,
            )
        )
        if result.scalar_one_or_none():
            return
        db.add(ExamBlueprint(
            exam_id=exam_id,
            topic_id=topic_id,
            expected_questions=expected_q,
            difficulty_level=difficulty,
        ))

    for year in EXAM_YEARS:
        full_exam_id = exam_map.get((FULL_EXAM_SUBJECT, year))

        for subject_name in SUBJECTS:
            config = BLUEPRINT_CONFIG.get(subject_name, {})
            per_subject_exam_id = exam_map.get((subject_name, year))

            for topic_name, (expected_q, difficulty) in config.items():
                topic_id = topic_map.get((subject_name, topic_name))
                if not topic_id:
                    continue

                # Per-subject exam blueprint
                if per_subject_exam_id:
                    await _add_blueprint(per_subject_exam_id, topic_id, expected_q, difficulty)

                # Full exam blueprint — same topic, same config
                if full_exam_id:
                    await _add_blueprint(full_exam_id, topic_id, expected_q, difficulty)

    await db.commit()
