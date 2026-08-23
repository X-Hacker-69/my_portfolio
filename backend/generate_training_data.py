#!/usr/bin/env python3
"""
generate_training_data.py
──────────────────────────
Reads portfolio.json → generates:
  1. training_data.jsonl  — Q&A pairs for fine-tuning
  2. rag_chunks.json      — text chunks for RAG embedding

Run:
  python generate_training_data.py
"""

import json, os, random, sys

print("🔄 Generating training data...", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
#  PATHS
# ══════════════════════════════════════════════════════════════════════════════
BASE_DIR       = r"D:\portfolio\portfolio_Main\backend"
PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio.json")
TRAINING_FILE  = os.path.join(BASE_DIR, "training_data.jsonl")
RAG_FILE       = os.path.join(BASE_DIR, "rag_chunks.json")

if not os.path.exists(PORTFOLIO_FILE):
    print(f"❌  portfolio.json not found at: {PORTFOLIO_FILE}", flush=True)
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
#  LOAD PORTFOLIO
# ══════════════════════════════════════════════════════════════════════════════
with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
    p = json.load(f)

name       = p["personal_info"]["name"]
first_name = name.split()[0]
print(f"   Portfolio owner : {name}", flush=True)

# ── Safe getters — never crash on missing keys ────────────────────────────────
info        = p.get("personal_info", {})
skills      = p.get("skills", {})
projects    = p.get("projects", [])
education   = p.get("education", [])
experience  = p.get("experience", [])
achievements= p.get("achievements", [])
hackathons  = p.get("hackathons", [])
contact     = p.get("contact", {})

qa_pairs  = []
rag_chunks= []

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def add(questions: list, answer: str):
    """Add multiple question variants for the same answer."""
    for q in questions:
        if q and answer:
            qa_pairs.append({"instruction": q.strip(), "response": answer.strip()})

def chunk(text: str, source: str):
    """Add a RAG text chunk."""
    if text and text.strip():
        rag_chunks.append({"text": text.strip(), "source": source})

def join(lst, sep=", "):
    """Safely join a list — returns empty string if not a list."""
    if isinstance(lst, list):
        return sep.join(str(i) for i in lst if i)
    return str(lst) if lst else ""

# ══════════════════════════════════════════════════════════════════════════════
#  PERSONAL / INTRO
# ══════════════════════════════════════════════════════════════════════════════
about = p.get("about_me", "")

add(
    [
        f"Who is {name}?",
        f"Tell me about {name}.",
        "Introduce yourself.",
        "Who are you?",
        f"What does {first_name} do?",
    ],
    f"{name} is a {info.get('title','')} based in {info.get('location','')}. {about}"
)

add(
    [f"Where is {first_name} located?", f"Where does {first_name} live?"],
    f"{first_name} is based in {info.get('location','N/A')}."
)

currently_learning = skills.get("currently_learning", [])
if currently_learning:
    add(
        [f"What are {first_name}'s goals?", f"What is {first_name} passionate about?"],
        f"{first_name} is passionate about building AI-powered products and scalable systems. "
        f"He is currently focusing on {join(currently_learning)} "
        f"and aims to contribute to cutting-edge AI research and open-source projects."
    )

# RAG chunk
chunk(f"{name} — {info.get('title','')}\n{about}", "about")

# ══════════════════════════════════════════════════════════════════════════════
#  SKILLS
# ══════════════════════════════════════════════════════════════════════════════
skill_lines = []
skill_chunk_parts = []
for key, label in [
    ("languages",         "Languages"),
    ("frontend",          "Frontend"),
    ("backend",           "Backend"),
    ("ai_ml",             "AI/ML"),
    ("databases",         "Databases"),
    ("devops",            "DevOps"),
    ("currently_learning","Currently learning"),
]:
    vals = skills.get(key, [])
    if vals:
        skill_lines.append(f"• {label}: {join(vals)}")
        skill_chunk_parts.append(f"{label}: {join(vals)}")

if skill_lines:
    add(
        [
            f"What are {first_name}'s skills?",
            f"What technologies does {first_name} know?",
            f"What is {first_name}'s tech stack?",
            "What programming languages does he know?",
            "What frameworks does he use?",
        ],
        f"{first_name}'s skill set includes:\n" + "\n".join(skill_lines)
    )
    chunk("Skills: " + ". ".join(skill_chunk_parts) + ".", "skills")

ai_ml = skills.get("ai_ml", [])
if ai_ml:
    add(
        [f"What AI/ML skills does {first_name} have?", "What ML frameworks does he know?"],
        f"{first_name} has strong AI/ML expertise: {join(ai_ml)}."
    )

if currently_learning:
    add(
        [f"What is {first_name} currently learning?", "What new technologies is he exploring?"],
        f"{first_name} is currently learning {join(currently_learning)}."
    )

# ══════════════════════════════════════════════════════════════════════════════
#  PROJECTS
# ══════════════════════════════════════════════════════════════════════════════
if projects:
    add(
        [
            f"What projects has {first_name} built?",
            f"Tell me about {first_name}'s projects.",
            "Show me his portfolio projects.",
            f"What has {first_name} worked on?",
        ],
        f"{first_name} has built {len(projects)} notable projects:\n" +
        "\n".join(f"• {pr['name']} — {pr.get('description','')[:80]}..." for pr in projects)
    )

    for pr in projects:
        tech_str       = join(pr.get("tech", []))
        highlights     = pr.get("highlights", [])
        highlights_str = "\n".join(f"  • {h}" for h in highlights)
        github_line    = f"\nGitHub: {pr['github']}" if pr.get("github") else ""
        category       = pr.get("category", "")

        add(
            [
                f"Tell me about the {pr['name']} project.",
                f"Explain the {pr['name']}.",
                f"What is {pr['name']}?",
                f"How does {pr['name']} work?",
            ],
            f"{pr['name']}\n\n{pr.get('description','')}\n\nTech stack: {tech_str}"
            + (f"\n\nKey highlights:\n{highlights_str}" if highlights_str else "")
            + github_line
        )

        add(
            [
                f"What technologies were used in {pr['name']}?",
                f"What tech stack does {pr['name']} use?",
            ],
            f"The {pr['name']} project was built with: {tech_str}."
        )

        # RAG chunk per project
        chunk(
            f"Project: {pr['name']} ({category})\n"
            f"{pr.get('description','')}\n"
            f"Tech: {tech_str}\n"
            f"Highlights: {join(highlights, '; ')}",
            f"project:{pr['name']}"
        )

    ai_projects = [pr for pr in projects if "AI" in pr.get("category", "")]
    if ai_projects:
        add(
            [f"What AI projects has {first_name} built?", "Show me his AI work."],
            f"{first_name}'s AI projects:\n" +
            "\n".join(f"• {pr['name']}: {pr.get('description','')[:100]}..." for pr in ai_projects)
        )

    add(
        [f"Which is {first_name}'s most impressive project?", "What is his best project?"],
        f"The most advanced project is **{projects[0]['name']}** — {projects[0].get('description','')} "
        + (f"Key highlights: {join(projects[0].get('highlights',[]), '; ')}." if projects[0].get('highlights') else "")
    )

    add(
        ["What are his strongest projects?", "Highlight his best work."],
        "Top highlights from " + first_name + "'s portfolio:\n\n" +
        "\n".join(
            f"• {pr['name']} ({pr.get('category','')}): "
            f"{join(pr.get('highlights', [pr.get('description','')[:80]]), '; ')}"
            for pr in projects[:3]
        )
    )

# ══════════════════════════════════════════════════════════════════════════════
#  EDUCATION
# ══════════════════════════════════════════════════════════════════════════════
for edu in education:
    courses = join(edu.get("relevant_courses", []))
    answer  = (
        f"{first_name} is pursuing a {edu.get('degree','')} "
        f"from {edu.get('institution','')} ({edu.get('year','')}) "
        f"with a GPA of {edu.get('gpa','')}."
        + (f" Relevant coursework: {courses}." if courses else "")
    )
    add(
        [
            f"What is {first_name}'s educational background?",
            f"Where did {first_name} study?",
            "What is his degree?",
            "Tell me about his education.",
            f"Where does {first_name} go to college?",
        ],
        answer
    )
    chunk(
        f"Education: {edu.get('degree','')} from {edu.get('institution','')} "
        f"({edu.get('year','')}), GPA {edu.get('gpa','')}."
        + (f" Courses: {courses}." if courses else ""),
        "education"
    )

# ══════════════════════════════════════════════════════════════════════════════
#  EXPERIENCE
# ══════════════════════════════════════════════════════════════════════════════
if experience:
    add(
        [
            f"What work experience does {first_name} have?",
            f"Where has {first_name} worked?",
            "Tell me about his internships.",
            "What companies has he worked at?",
        ],
        f"{first_name}'s work experience:\n" +
        "\n".join(
            f"• {e.get('role','')} at {e.get('company','')} ({e.get('period','')}): {e.get('description','')}"
            for e in experience
        )
    )
    for exp in experience:
        add(
            [
                f"Tell me about his role at {exp.get('company','')}.",
                f"What did he do at {exp.get('company','')}?",
            ],
            f"{first_name} worked as {exp.get('role','')} at {exp.get('company','')} "
            f"({exp.get('period','')}). {exp.get('description','')}"
        )
        chunk(
            f"Experience: {exp.get('role','')} at {exp.get('company','')} "
            f"({exp.get('period','')}). {exp.get('description','')}",
            f"experience:{exp.get('company','')}"
        )

# ══════════════════════════════════════════════════════════════════════════════
#  ACHIEVEMENTS
# ══════════════════════════════════════════════════════════════════════════════
if achievements:
    add(
        [
            f"What are {first_name}'s achievements?",
            f"What awards has {first_name} won?",
            "Tell me about his accomplishments.",
            "What certifications does he have?",
            f"What has {first_name} achieved?",
        ],
        f"{first_name}'s key achievements:\n" + "\n".join(f"• {a}" for a in achievements)
    )
    chunk("Achievements:\n" + "\n".join(f"- {a}" for a in achievements), "achievements")

    # Recruiter summary uses first achievement
    add(
        [
            f"Why should I hire {first_name}?",
            f"Give me a recruiter summary of {first_name}.",
            "Summarize his profile for a recruiter.",
            "What makes him a strong candidate?",
            "Is he a good hire?",
        ],
        f"{name} is a standout {info.get('title','')} with deep AI/ML expertise "
        f"and full-stack engineering skills.\n\n"
        + (f"🎓 Education: {education[0].get('degree','')} from {education[0].get('institution','')} "
           f"(GPA {education[0].get('gpa','')})\n\n" if education else "")
        + f"🏆 Recognition: {achievements[0]}\n\n"
        f"🚀 Impact: His projects serve real users with measurable results.\n\n"
        f"💻 Stack: Full-stack across Python, JavaScript/TypeScript, React, FastAPI "
        f"and the modern AI/ML ecosystem."
    )
else:
    # Recruiter summary without achievements
    add(
        [
            f"Why should I hire {first_name}?",
            f"Give me a recruiter summary of {first_name}.",
            "Summarize his profile for a recruiter.",
        ],
        f"{name} is a {info.get('title','')} with strong technical skills "
        f"and hands-on project experience."
        + (f" He studied {education[0].get('degree','')} at {education[0].get('institution','')}." if education else "")
    )

# ══════════════════════════════════════════════════════════════════════════════
#  HACKATHONS
# ══════════════════════════════════════════════════════════════════════════════
if hackathons:
    add(
        [
            f"What hackathons has {first_name} participated in?",
            "Tell me about his hackathon results.",
            f"Has {first_name} won any hackathons?",
        ],
        f"{first_name}'s hackathon record:\n" +
        "\n".join(f"• {h.get('name','')}: {h.get('result','')} — {h.get('project','')}" for h in hackathons)
    )
    for h in hackathons:
        chunk(
            f"Hackathon: {h.get('name','')} — {h.get('result','')}. Project: {h.get('project','')}",
            f"hackathon:{h.get('name','')}"
        )

# ══════════════════════════════════════════════════════════════════════════════
#  CONTACT
# ══════════════════════════════════════════════════════════════════════════════
contact_lines = []
for key, label in [("email","Email"),("github","GitHub"),("linkedin","LinkedIn"),
                   ("calendly","Schedule a call"),("resume","Resume")]:
    if contact.get(key):
        contact_lines.append(f"• {label}: {contact[key]}")

if contact_lines:
    add(
        [
            f"How can I contact {first_name}?",
            f"What is {first_name}'s email?",
            "How do I reach him?",
            "Show me his contact information.",
            "Where can I find him online?",
        ],
        f"You can reach {first_name} at:\n" + "\n".join(contact_lines)
    )
    chunk(
        f"Contact {name}: " + ", ".join(
            f"{k} {contact[k]}" for k in ["email","github","linkedin","resume"] if contact.get(k)
        ),
        "contact"
    )

if contact.get("github"):
    add(["Show me his GitHub.", f"What is {first_name}'s GitHub?"],
        f"{first_name}'s GitHub: {contact['github']}")
if contact.get("linkedin"):
    add(["Show me his LinkedIn.", f"What is {first_name}'s LinkedIn?"],
        f"{first_name}'s LinkedIn: {contact['linkedin']}")
if contact.get("resume"):
    add(["Where is his resume?", "Show me his CV."],
        f"{first_name}'s resume: {contact['resume']}")

# ══════════════════════════════════════════════════════════════════════════════
#  WRITE OUTPUTS
# ══════════════════════════════════════════════════════════════════════════════
random.shuffle(qa_pairs)

with open(TRAINING_FILE, "w", encoding="utf-8") as f:
    for pair in qa_pairs:
        f.write(json.dumps({
            "instruction": pair["instruction"],
            "input":       "",
            "output":      pair["response"],
        }) + "\n")

with open(RAG_FILE, "w", encoding="utf-8") as f:
    json.dump(rag_chunks, f, indent=2, ensure_ascii=False)

print(f"✅ Training data : {len(qa_pairs)} Q&A pairs  →  {TRAINING_FILE}", flush=True)
print(f"✅ RAG chunks    : {len(rag_chunks)} chunks       →  {RAG_FILE}", flush=True)
print(f"\n📌 Next steps:", flush=True)
print(f"   1. python build_rag_index.py", flush=True)
print(f"   2. python inference_server.py\n", flush=True)