"""
VOID Builder Agent
==================

Autonomous project scaffolding agent. Generates architecture plans,
file structures, and code for websites, apps, and backends.

All file writes require explicit user approval (via fs_tools.ApprovalGate).

Usage:
    from server.backend.builder_agent import BuilderAgent, get_builder

    builder = get_builder()
    plan = builder.plan("Create a modern restaurant website")
    # Present plan to user → user approves
    result = await builder.execute_plan(plan, target_dir="./restaurant_site")
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("void.builder_agent")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class BuildFile:
    """A single file to be created as part of a build plan."""
    relative_path: str
    description: str
    content: str = ""          # Generated content (populated at execution time)
    is_binary: bool = False


@dataclass
class BuildPlan:
    """Complete plan for a new project."""
    id: str
    project_name: str
    project_type: str          # 'website' | 'backend' | 'app' | 'fullstack'
    description: str
    tech_stack: List[str]
    folder_structure: List[str]
    files: List[BuildFile]
    dev_command: str           # e.g. "npm run dev"
    install_command: str       # e.g. "npm install"
    estimated_time_min: int
    requirements: str          # Original user requirements
    approved: bool = False


@dataclass
class BuildResult:
    """Result after executing a build plan."""
    plan_id: str
    success: bool
    files_created: List[str]
    files_skipped: List[str]
    errors: List[str]
    target_dir: str
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Project type definitions
# ---------------------------------------------------------------------------
_PROJECT_TYPES = {
    "website": {
        "keywords": ["website", "landing page", "portfolio", "webpage", "restaurant", "blog"],
        "tech_stack": ["HTML5", "CSS3", "Vanilla JavaScript"],
        "dev_command": "",
        "install_command": "",
    },
    "backend": {
        "keywords": ["api", "backend", "rest api", "fastapi", "flask", "server", "endpoint"],
        "tech_stack": ["Python", "FastAPI", "Uvicorn", "SQLite"],
        "dev_command": "uvicorn main:app --reload",
        "install_command": "pip install fastapi uvicorn",
    },
    "app": {
        "keywords": ["app", "application", "electron", "desktop", "react", "vue", "frontend"],
        "tech_stack": ["React", "Vite", "Node.js"],
        "dev_command": "npm run dev",
        "install_command": "npm install",
    },
    "fullstack": {
        "keywords": ["fullstack", "full stack", "full-stack", "saas", "platform"],
        "tech_stack": ["React", "FastAPI", "SQLite", "Node.js"],
        "dev_command": "npm run dev",
        "install_command": "npm install && pip install -r requirements.txt",
    },
}


def _detect_project_type(requirements: str) -> str:
    req_lower = requirements.lower()
    for ptype, meta in _PROJECT_TYPES.items():
        if any(kw in req_lower for kw in meta["keywords"]):
            return ptype
    return "website"  # default


# ---------------------------------------------------------------------------
# Built-in website template (HTML + CSS + JS)
# ---------------------------------------------------------------------------
def _generate_website_template(project_name: str, description: str) -> List[BuildFile]:
    """Generate a complete responsive website scaffold."""
    safe_name = project_name.replace(" ", "_").lower()

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{description}">
    <title>{project_name}</title>
    <link rel="stylesheet" href="style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar" id="navbar">
        <div class="nav-container">
            <a href="#" class="nav-logo">{project_name}</a>
            <ul class="nav-links">
                <li><a href="#about">About</a></li>
                <li><a href="#services">Services</a></li>
                <li><a href="#contact">Contact</a></li>
            </ul>
            <button class="nav-cta" id="ctaBtn">Get Started</button>
        </div>
    </nav>

    <!-- Hero Section -->
    <section class="hero" id="hero">
        <div class="hero-content">
            <span class="hero-badge">✨ Welcome</span>
            <h1 class="hero-title">{project_name}</h1>
            <p class="hero-subtitle">{description}</p>
            <div class="hero-actions">
                <a href="#services" class="btn btn-primary">Explore</a>
                <a href="#contact" class="btn btn-outline">Contact Us</a>
            </div>
        </div>
        <div class="hero-visual">
            <div class="floating-card card-1">
                <span class="card-icon">🚀</span>
                <span>Fast &amp; Reliable</span>
            </div>
            <div class="floating-card card-2">
                <span class="card-icon">⭐</span>
                <span>5-Star Quality</span>
            </div>
        </div>
    </section>

    <!-- About -->
    <section class="section" id="about">
        <div class="container">
            <h2 class="section-title">About Us</h2>
            <p class="section-subtitle">We are dedicated to delivering the best experience possible.</p>
            <div class="grid-3">
                <div class="feature-card">
                    <span class="feature-icon">🎯</span>
                    <h3>Our Mission</h3>
                    <p>Delivering excellence in everything we do with passion and precision.</p>
                </div>
                <div class="feature-card">
                    <span class="feature-icon">👥</span>
                    <h3>Our Team</h3>
                    <p>A dedicated group of professionals committed to your success.</p>
                </div>
                <div class="feature-card">
                    <span class="feature-icon">💡</span>
                    <h3>Innovation</h3>
                    <p>Continuously evolving to bring you the latest and best solutions.</p>
                </div>
            </div>
        </div>
    </section>

    <!-- Services -->
    <section class="section section-dark" id="services">
        <div class="container">
            <h2 class="section-title">Services</h2>
            <p class="section-subtitle">Everything you need, all in one place.</p>
            <div class="grid-2">
                <div class="service-card" id="service1">
                    <div class="service-number">01</div>
                    <h3>Premium Quality</h3>
                    <p>The highest standards maintained across all our offerings.</p>
                </div>
                <div class="service-card" id="service2">
                    <div class="service-number">02</div>
                    <h3>24/7 Support</h3>
                    <p>Round-the-clock assistance whenever you need it most.</p>
                </div>
                <div class="service-card" id="service3">
                    <div class="service-number">03</div>
                    <h3>Custom Solutions</h3>
                    <p>Tailored specifically to your unique requirements and goals.</p>
                </div>
                <div class="service-card" id="service4">
                    <div class="service-number">04</div>
                    <h3>Fast Delivery</h3>
                    <p>Efficient processes ensuring timely and reliable results.</p>
                </div>
            </div>
        </div>
    </section>

    <!-- Contact -->
    <section class="section" id="contact">
        <div class="container">
            <h2 class="section-title">Get In Touch</h2>
            <p class="section-subtitle">We'd love to hear from you.</p>
            <form class="contact-form" id="contactForm">
                <div class="form-row">
                    <input type="text" id="nameInput" placeholder="Your Name" required>
                    <input type="email" id="emailInput" placeholder="Your Email" required>
                </div>
                <textarea id="messageInput" placeholder="Your Message" rows="5" required></textarea>
                <button type="submit" class="btn btn-primary" id="submitBtn">Send Message</button>
            </form>
        </div>
    </section>

    <!-- Footer -->
    <footer class="footer">
        <p>&copy; 2026 {project_name}. Built with ❤️ by VOID.</p>
    </footer>

    <script src="script.js"></script>
</body>
</html>"""

    style_css = """/* ================================================
   VOID Builder — Generated Website Styles
   ================================================ */

:root {
    --primary: #6366f1;
    --primary-dark: #4f46e5;
    --accent: #a78bfa;
    --bg: #0f0f1a;
    --bg-card: #1a1a2e;
    --bg-dark: #080812;
    --text: #e2e8f0;
    --text-muted: #94a3b8;
    --border: rgba(99, 102, 241, 0.2);
    --radius: 12px;
    --shadow: 0 4px 24px rgba(99, 102, 241, 0.15);
    --transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    --font: 'Inter', system-ui, sans-serif;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: var(--font);
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    overflow-x: hidden;
}

/* ---- NAVBAR ---- */
.navbar {
    position: fixed; top: 0; left: 0; right: 0; z-index: 100;
    padding: 1rem 2rem;
    background: rgba(15, 15, 26, 0.85);
    backdrop-filter: blur(16px);
    border-bottom: 1px solid var(--border);
    transition: var(--transition);
}
.nav-container { max-width: 1200px; margin: 0 auto; display: flex; align-items: center; gap: 2rem; }
.nav-logo { font-size: 1.4rem; font-weight: 700; color: var(--primary); text-decoration: none; }
.nav-links { list-style: none; display: flex; gap: 2rem; margin-left: auto; }
.nav-links a { color: var(--text-muted); text-decoration: none; transition: color var(--transition); }
.nav-links a:hover { color: var(--text); }
.nav-cta {
    padding: 0.5rem 1.5rem; border: none; border-radius: 50px;
    background: var(--primary); color: white; font-weight: 600;
    cursor: pointer; transition: var(--transition);
}
.nav-cta:hover { background: var(--primary-dark); transform: translateY(-1px); }

/* ---- HERO ---- */
.hero {
    min-height: 100vh; display: flex; align-items: center;
    padding: 8rem 2rem 4rem;
    background: radial-gradient(ellipse at 20% 50%, rgba(99,102,241,0.15) 0%, transparent 60%),
                radial-gradient(ellipse at 80% 20%, rgba(167,139,250,0.1) 0%, transparent 50%);
    position: relative; overflow: hidden;
}
.hero::before {
    content: ''; position: absolute; inset: 0;
    background: url("data:image/svg+xml,%3Csvg width='60' height='60' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 0h60v60H0z' fill='none'/%3E%3Ccircle cx='1' cy='1' r='1' fill='rgba(99,102,241,0.1)'/%3E%3C/svg%3E");
    opacity: 0.5; pointer-events: none;
}
.hero-content { max-width: 600px; z-index: 1; }
.hero-badge {
    display: inline-block; padding: 0.35rem 1rem; border-radius: 50px;
    background: rgba(99,102,241,0.15); border: 1px solid var(--border);
    font-size: 0.85rem; margin-bottom: 1.5rem; color: var(--accent);
}
.hero-title { font-size: clamp(2.5rem, 6vw, 5rem); font-weight: 700; line-height: 1.1; margin-bottom: 1.5rem; }
.hero-subtitle { font-size: 1.2rem; color: var(--text-muted); margin-bottom: 2.5rem; }
.hero-actions { display: flex; gap: 1rem; flex-wrap: wrap; }
.hero-visual { position: absolute; right: 8%; top: 50%; transform: translateY(-50%); }
.floating-card {
    position: absolute; background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 1rem 1.5rem;
    display: flex; align-items: center; gap: 0.75rem; font-weight: 600;
    box-shadow: var(--shadow); animation: float 4s ease-in-out infinite;
}
.floating-card .card-icon { font-size: 1.5rem; }
.card-1 { top: -60px; right: 0; animation-delay: 0s; }
.card-2 { bottom: -40px; right: 60px; animation-delay: -2s; }
@keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }

/* ---- BUTTONS ---- */
.btn {
    padding: 0.85rem 2rem; border-radius: 50px; font-weight: 600;
    text-decoration: none; transition: var(--transition); display: inline-block; cursor: pointer;
    border: none; font-family: var(--font); font-size: 1rem;
}
.btn-primary { background: var(--primary); color: white; }
.btn-primary:hover { background: var(--primary-dark); transform: translateY(-2px); box-shadow: 0 8px 25px rgba(99,102,241,0.4); }
.btn-outline { background: transparent; color: var(--text); border: 1px solid var(--border); }
.btn-outline:hover { border-color: var(--primary); color: var(--primary); }

/* ---- SECTIONS ---- */
.section { padding: 6rem 2rem; }
.section-dark { background: var(--bg-dark); }
.container { max-width: 1200px; margin: 0 auto; }
.section-title { font-size: clamp(2rem, 4vw, 3rem); font-weight: 700; text-align: center; margin-bottom: 1rem; }
.section-subtitle { color: var(--text-muted); text-align: center; margin-bottom: 4rem; font-size: 1.1rem; }

/* ---- GRIDS ---- */
.grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; }
.grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem; }

/* ---- CARDS ---- */
.feature-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 2rem; transition: var(--transition);
}
.feature-card:hover { border-color: var(--primary); transform: translateY(-4px); box-shadow: var(--shadow); }
.feature-icon { font-size: 2.5rem; display: block; margin-bottom: 1rem; }
.feature-card h3 { margin-bottom: 0.5rem; font-size: 1.2rem; }
.feature-card p { color: var(--text-muted); }

.service-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 2.5rem; transition: var(--transition);
}
.service-card:hover { border-color: var(--primary); box-shadow: var(--shadow); }
.service-number { font-size: 3rem; font-weight: 700; color: var(--primary); opacity: 0.3; margin-bottom: 0.5rem; }
.service-card h3 { margin-bottom: 0.75rem; font-size: 1.3rem; }
.service-card p { color: var(--text-muted); }

/* ---- CONTACT ---- */
.contact-form { max-width: 700px; margin: 0 auto; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem; }
.contact-form input, .contact-form textarea {
    width: 100%; padding: 1rem 1.25rem;
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius); color: var(--text); font-family: var(--font);
    font-size: 1rem; transition: var(--transition);
}
.contact-form input:focus, .contact-form textarea:focus {
    outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(99,102,241,0.15);
}
.contact-form textarea { resize: vertical; margin-bottom: 1.5rem; }
.contact-form .btn { width: 100%; justify-content: center; }

/* ---- FOOTER ---- */
.footer { padding: 2rem; text-align: center; border-top: 1px solid var(--border); color: var(--text-muted); }

/* ---- RESPONSIVE ---- */
@media (max-width: 768px) {
    .nav-links { display: none; }
    .hero { padding-top: 6rem; }
    .hero-visual { display: none; }
    .form-row { grid-template-columns: 1fr; }
}
"""

    script_js = f"""// ================================================
// VOID Builder — Generated Website Scripts
// ================================================

// Smooth scroll for nav links
document.querySelectorAll('a[href^="#"]').forEach(link => {{
    link.addEventListener('click', e => {{
        e.preventDefault();
        const target = document.querySelector(link.getAttribute('href'));
        if (target) {{
            target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
        }}
    }});
}});

// Navbar scroll effect
window.addEventListener('scroll', () => {{
    const navbar = document.getElementById('navbar');
    navbar.style.background = window.scrollY > 50
        ? 'rgba(15, 15, 26, 0.98)'
        : 'rgba(15, 15, 26, 0.85)';
}});

// Intersection Observer for entrance animations
const observer = new IntersectionObserver((entries) => {{
    entries.forEach(entry => {{
        if (entry.isIntersecting) {{
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }}
    }});
}}, {{ threshold: 0.1 }});

document.querySelectorAll('.feature-card, .service-card').forEach(el => {{
    el.style.opacity = '0';
    el.style.transform = 'translateY(24px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
}});

// Contact form handler
document.getElementById('contactForm')?.addEventListener('submit', e => {{
    e.preventDefault();
    const btn = document.getElementById('submitBtn');
    btn.textContent = '✓ Message Sent!';
    btn.style.background = '#10b981';
    setTimeout(() => {{
        btn.textContent = 'Send Message';
        btn.style.background = '';
        e.target.reset();
    }}, 3000);
}});

// CTA button
document.getElementById('ctaBtn')?.addEventListener('click', () => {{
    document.getElementById('contact').scrollIntoView({{ behavior: 'smooth' }});
}});

console.log('🚀 {project_name} — Built with VOID AI');
"""

    return [
        BuildFile(relative_path="index.html", description="Main HTML page", content=index_html),
        BuildFile(relative_path="style.css", description="Responsive dark-theme stylesheet", content=style_css),
        BuildFile(relative_path="script.js", description="Smooth interactions and animations", content=script_js),
    ]


def _generate_fastapi_template(project_name: str, description: str) -> List[BuildFile]:
    """Generate a FastAPI backend scaffold."""
    safe_name = project_name.lower().replace(" ", "_")
    main_py = f"""from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

app = FastAPI(title="{project_name}", description="{description}", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Models ----
class Item(BaseModel):
    id: Optional[int] = None
    name: str
    description: str = ""

# ---- In-memory store (replace with DB) ----
_items: List[Item] = []
_next_id = 1

# ---- Routes ----
@app.get("/")
async def root():
    return {{"message": "Welcome to {project_name}", "status": "ok"}}

@app.get("/items", response_model=List[Item])
async def list_items():
    return _items

@app.post("/items", response_model=Item, status_code=201)
async def create_item(item: Item):
    global _next_id
    item.id = _next_id
    _next_id += 1
    _items.append(item)
    return item

@app.get("/items/{{item_id}}", response_model=Item)
async def get_item(item_id: int):
    for item in _items:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")

@app.delete("/items/{{item_id}}")
async def delete_item(item_id: int):
    global _items
    _items = [i for i in _items if i.id != item_id]
    return {{"status": "deleted"}}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
"""
    requirements = "fastapi\nuvicorn[standard]\npydantic\n"
    readme = f"""# {project_name}

{description}

## Setup
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://localhost:8000/docs for the interactive API documentation.

Built with VOID AI.
"""
    return [
        BuildFile(relative_path="main.py", description="FastAPI application entry point", content=main_py),
        BuildFile(relative_path="requirements.txt", description="Python dependencies", content=requirements),
        BuildFile(relative_path="README.md", description="Project documentation", content=readme),
    ]


# ---------------------------------------------------------------------------
# Builder Agent
# ---------------------------------------------------------------------------
class BuilderAgent:
    """
    Generates, plans, and executes project scaffolding.
    All file writes are gated through fs_tools.ApprovalGate.
    """

    def __init__(self):
        self._last_plan: Optional[BuildPlan] = None

    # ------------------------------------------------------------------
    # Planning (no file writes — safe to call without approval)
    # ------------------------------------------------------------------
    def plan(self, requirements: str) -> BuildPlan:
        """
        Analyse requirements and generate a BuildPlan.
        This does NOT write any files — just produces the plan.

        Args:
            requirements: Natural language description of the project.

        Returns:
            BuildPlan ready for user review and approval.
        """
        import uuid
        logger.info(f"[BUILDER] Planning: '{requirements[:80]}'")

        project_type = _detect_project_type(requirements)
        type_meta = _PROJECT_TYPES[project_type]

        # Extract project name from requirements
        project_name = self._extract_project_name(requirements)

        # Generate files based on project type
        if project_type == "backend":
            files = _generate_fastapi_template(project_name, requirements)
        else:
            files = _generate_website_template(project_name, requirements)

        folder_structure = list({
            str(Path(f.relative_path).parent)
            for f in files
            if str(Path(f.relative_path).parent) != "."
        }) or ["."]

        plan = BuildPlan(
            id=str(uuid.uuid4())[:8],
            project_name=project_name,
            project_type=project_type,
            description=requirements,
            tech_stack=type_meta["tech_stack"],
            folder_structure=folder_structure,
            files=files,
            dev_command=type_meta["dev_command"],
            install_command=type_meta["install_command"],
            estimated_time_min=1 if len(files) <= 5 else 3,
            requirements=requirements,
        )

        self._last_plan = plan
        logger.info(
            f"[BUILDER] Plan '{plan.id}': {len(files)} files, "
            f"type={project_type}, stack={type_meta['tech_stack']}"
        )
        return plan

    # ------------------------------------------------------------------
    # Execution (requires user approval per file or batch)
    # ------------------------------------------------------------------
    async def execute_plan(
        self,
        plan: BuildPlan,
        target_dir: str = ".",
        batch_approve: bool = False,
    ) -> BuildResult:
        """
        Execute a BuildPlan by writing all files to target_dir.

        Args:
            plan:          The BuildPlan to execute.
            target_dir:    Root directory for the project.
            batch_approve: If True, a single approval covers all files.
                           If False, each file needs individual approval.

        Returns:
            BuildResult with success status and created file paths.
        """
        from server.backend.fs_tools import get_fs_tools
        fs = get_fs_tools()

        t0 = time.time()
        root = Path(target_dir) / plan.project_name.replace(" ", "_").lower()
        created: List[str] = []
        skipped: List[str] = []
        errors: List[str] = []

        logger.info(f"[BUILDER] Executing plan '{plan.id}' → {root}")

        # Batch approval gate
        if batch_approve:
            from server.backend.fs_tools import request_approval
            file_list = "\n".join(f"  • {f.relative_path}" for f in plan.files)
            approved = await request_approval(
                operation=f"Create project '{plan.project_name}'",
                path=str(root),
                details=f"Will create {len(plan.files)} files:\n{file_list}",
                timeout=60.0,
            )
            if not approved:
                return BuildResult(
                    plan_id=plan.id, success=False,
                    files_created=[], files_skipped=[],
                    errors=["User denied project creation."],
                    target_dir=str(root), elapsed_seconds=time.time() - t0,
                )

        # Create each file
        for build_file in plan.files:
            full_path = root / build_file.relative_path
            result = await fs.write_file(
                str(full_path),
                build_file.content,
                require_approval=not batch_approve,
            )
            if result["status"] == "ok":
                created.append(str(full_path))
            elif result["status"] == "denied":
                skipped.append(str(full_path))
                logger.info(f"[BUILDER] Skipped (denied): {full_path}")
            else:
                errors.append(f"{full_path}: {result.get('message','unknown error')}")
                logger.error(f"[BUILDER] Error creating {full_path}: {result.get('message')}")

        elapsed = time.time() - t0
        success = len(errors) == 0 and len(created) > 0
        logger.info(
            f"[BUILDER] Plan '{plan.id}' done in {elapsed:.1f}s — "
            f"created={len(created)}, skipped={len(skipped)}, errors={len(errors)}"
        )
        return BuildResult(
            plan_id=plan.id,
            success=success,
            files_created=created,
            files_skipped=skipped,
            errors=errors,
            target_dir=str(root),
            elapsed_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_project_name(requirements: str) -> str:
        """Attempt to extract a project name from natural language requirements."""
        import re
        # Match patterns like "Create a X website/app/backend"
        for pattern in (
            r"create (?:a |an )?(.+?) (?:website|app|backend|application|api|platform)",
            r"build (?:a |an )?(.+?) (?:website|app|backend|application|api|platform)",
            r"generate (?:a |an )?(.+?) (?:website|app|backend|application|api|platform)",
            r"make (?:a |an )?(.+?) (?:website|app|backend|application|api|platform)",
        ):
            m = re.search(pattern, requirements.lower())
            if m:
                name = m.group(1).strip().title()
                if 2 <= len(name) <= 30:
                    return name
        # Fallback: first 3 words
        words = requirements.strip().split()[:3]
        return " ".join(words).title()

    def plan_to_dict(self, plan: BuildPlan) -> Dict[str, Any]:
        """Convert a BuildPlan to a JSON-serialisable dict for the frontend."""
        return {
            "id": plan.id,
            "project_name": plan.project_name,
            "project_type": plan.project_type,
            "description": plan.description,
            "tech_stack": plan.tech_stack,
            "folder_structure": plan.folder_structure,
            "files": [
                {"path": f.relative_path, "description": f.description}
                for f in plan.files
            ],
            "dev_command": plan.dev_command,
            "install_command": plan.install_command,
            "estimated_time_min": plan.estimated_time_min,
            "file_count": len(plan.files),
        }

    def status(self) -> Dict[str, Any]:
        """Return builder status for monitoring dashboard."""
        return {
            "last_plan_id": self._last_plan.id if self._last_plan else None,
            "last_plan_name": self._last_plan.project_name if self._last_plan else None,
            "last_plan_type": self._last_plan.project_type if self._last_plan else None,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_builder: Optional[BuilderAgent] = None

def get_builder() -> BuilderAgent:
    """Return (or create) the BuilderAgent singleton."""
    global _builder
    if _builder is None:
        _builder = BuilderAgent()
    return _builder
