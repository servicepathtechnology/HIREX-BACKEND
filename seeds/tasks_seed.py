"""Seed 10 sample tasks across all domains and difficulty levels.

Run: python -m seeds.tasks_seed
(from hirex_backend/ directory with DB running)
"""

import asyncio
import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.models.user import User
from app.models.task import Task

SEED_TASKS = [
    {
        "title": "Build a REST API for a Task Management App",
        "slug": "build-rest-api-task-management",
        "description": "Design and implement a fully functional REST API for a task management application. The API should support CRUD operations for tasks, user authentication, and task assignment.",
        "problem_statement": "Build a production-ready REST API using FastAPI or Node.js/Express that supports: user registration and JWT auth, task CRUD with status tracking, task assignment to users, and pagination on list endpoints.",
        "evaluation_criteria": [
            {"criterion": "Accuracy", "weight": 40, "description": "Does the API correctly implement all required endpoints?"},
            {"criterion": "Approach & Thinking", "weight": 30, "description": "Is the code well-structured and follows REST conventions?"},
            {"criterion": "Completeness", "weight": 20, "description": "Are all requirements covered including auth and pagination?"},
            {"criterion": "Efficiency", "weight": 10, "description": "Is the code clean and optimally written?"},
        ],
        "domain": "engineering",
        "difficulty": "intermediate",
        "task_type": "code",
        "submission_types": ["code", "link"],
        "skills_tested": ["python", "rest api", "fastapi", "postgresql"],
        "estimated_hours": 4.0,
        "company_visible": True,
        "company_name": "TechCorp",
        "prize_or_opportunity": "Top 3 candidates get fast-tracked interviews",
        "deadline_days": 7,
    },
    {
        "title": "Fix 3 Bugs in This Flutter Widget",
        "slug": "fix-3-bugs-flutter-widget",
        "description": "You are given a Flutter widget with 3 intentional bugs. Your task is to identify and fix all three bugs, and explain what each bug was.",
        "problem_statement": "The provided Flutter widget has 3 bugs: one causes a null pointer exception, one causes incorrect state management, and one causes a layout overflow. Find and fix all three.",
        "evaluation_criteria": [
            {"criterion": "Accuracy", "weight": 40, "description": "Are all 3 bugs correctly identified and fixed?"},
            {"criterion": "Approach & Thinking", "weight": 30, "description": "Is the explanation of each bug clear and correct?"},
            {"criterion": "Completeness", "weight": 20, "description": "Are all 3 bugs addressed?"},
            {"criterion": "Efficiency", "weight": 10, "description": "Is the fix minimal and clean?"},
        ],
        "domain": "engineering",
        "difficulty": "beginner",
        "task_type": "code",
        "submission_types": ["code"],
        "skills_tested": ["flutter", "dart"],
        "estimated_hours": 1.5,
        "company_visible": False,
        "deadline_days": 5,
    },
    {
        "title": "Optimize This SQL Query for 10x Performance",
        "slug": "optimize-sql-query-10x-performance",
        "description": "You are given a slow SQL query that runs on a 10M row table. Your task is to optimize it to run at least 10x faster using indexes, query restructuring, or other techniques.",
        "problem_statement": "The given query does a full table scan on a 10M row orders table. Optimize it using appropriate indexes, query rewriting, and explain your approach with EXPLAIN ANALYZE output.",
        "evaluation_criteria": [
            {"criterion": "Accuracy", "weight": 40, "description": "Does the optimized query return correct results?"},
            {"criterion": "Approach & Thinking", "weight": 30, "description": "Is the optimization strategy well-reasoned?"},
            {"criterion": "Completeness", "weight": 20, "description": "Are all optimization opportunities addressed?"},
            {"criterion": "Efficiency", "weight": 10, "description": "Is the solution clean and well-documented?"},
        ],
        "domain": "engineering",
        "difficulty": "advanced",
        "task_type": "code",
        "submission_types": ["code", "text"],
        "skills_tested": ["sql", "postgresql"],
        "estimated_hours": 3.0,
        "company_visible": True,
        "company_name": "DataScale Inc",
        "deadline_days": 10,
    },
    {
        "title": "Redesign the Login Screen of a Fintech App",
        "slug": "redesign-login-screen-fintech",
        "description": "Redesign the login screen for a fintech mobile app. The current design is outdated and has poor UX. Create a modern, trustworthy, and accessible design.",
        "problem_statement": "The current login screen has poor contrast, confusing form layout, and no visual hierarchy. Redesign it in Figma with improved UX, accessibility, and brand alignment for a fintech product.",
        "evaluation_criteria": [
            {"criterion": "Accuracy", "weight": 40, "description": "Does the design solve the stated UX problems?"},
            {"criterion": "Approach & Thinking", "weight": 30, "description": "Is the design rationale well-explained?"},
            {"criterion": "Completeness", "weight": 20, "description": "Are all screen states covered (error, loading, success)?"},
            {"criterion": "Efficiency", "weight": 10, "description": "Is the design system consistent?"},
        ],
        "domain": "design",
        "difficulty": "intermediate",
        "task_type": "design",
        "submission_types": ["file", "link"],
        "allowed_file_types": ["pdf", "png", "jpg"],
        "skills_tested": ["figma", "ui design", "ux design"],
        "estimated_hours": 3.0,
        "company_visible": True,
        "company_name": "FinFlow",
        "prize_or_opportunity": "Winner gets a design internship offer",
        "deadline_days": 6,
    },
    {
        "title": "Create a Logo for a Food Delivery Startup",
        "slug": "create-logo-food-delivery-startup",
        "description": "Design a logo for 'QuickBite', a new food delivery startup targeting urban millennials. The brand should feel fast, fresh, and friendly.",
        "problem_statement": "QuickBite needs a logo that works across app icons, delivery bags, and social media. Design a primary logo, icon variant, and provide the logo in light and dark versions.",
        "evaluation_criteria": [
            {"criterion": "Accuracy", "weight": 40, "description": "Does the logo match the brand brief?"},
            {"criterion": "Approach & Thinking", "weight": 30, "description": "Is the design concept well-explained?"},
            {"criterion": "Completeness", "weight": 20, "description": "Are all required variants delivered?"},
            {"criterion": "Efficiency", "weight": 10, "description": "Is the file well-organized?"},
        ],
        "domain": "design",
        "difficulty": "beginner",
        "task_type": "design",
        "submission_types": ["file"],
        "allowed_file_types": ["pdf", "png", "zip"],
        "skills_tested": ["graphic design", "branding"],
        "estimated_hours": 2.0,
        "company_visible": False,
        "deadline_days": 5,
    },
    {
        "title": "Write a PRD for a Habit Tracking Feature",
        "slug": "write-prd-habit-tracking-feature",
        "description": "Write a complete Product Requirements Document for a habit tracking feature to be added to an existing wellness app with 500K MAU.",
        "problem_statement": "The wellness app wants to add habit tracking. Write a PRD covering: problem statement, user personas, success metrics, feature requirements, edge cases, and a phased rollout plan.",
        "evaluation_criteria": [
            {"criterion": "Accuracy", "weight": 40, "description": "Does the PRD correctly define the problem and solution?"},
            {"criterion": "Approach & Thinking", "weight": 30, "description": "Is the product thinking structured and insightful?"},
            {"criterion": "Completeness", "weight": 20, "description": "Are all PRD sections complete?"},
            {"criterion": "Efficiency", "weight": 10, "description": "Is the document concise and well-structured?"},
        ],
        "domain": "product",
        "difficulty": "intermediate",
        "task_type": "product",
        "submission_types": ["text", "file"],
        "allowed_file_types": ["pdf", "docx"],
        "skills_tested": ["product management", "user stories"],
        "estimated_hours": 4.0,
        "company_visible": True,
        "company_name": "WellnessOS",
        "deadline_days": 8,
    },
    {
        "title": "Define the Go-to-Market Strategy for HireX Launch",
        "slug": "gtm-strategy-hirex-launch",
        "description": "HireX is launching in 3 months. Define a complete go-to-market strategy targeting both candidates and recruiters in the Indian tech market.",
        "problem_statement": "HireX needs a GTM strategy covering: target segments, positioning, acquisition channels, pricing strategy, launch timeline, and success KPIs. Provide a 90-day launch plan.",
        "evaluation_criteria": [
            {"criterion": "Accuracy", "weight": 40, "description": "Is the strategy grounded in market reality?"},
            {"criterion": "Approach & Thinking", "weight": 30, "description": "Is the strategic thinking sharp and differentiated?"},
            {"criterion": "Completeness", "weight": 20, "description": "Are all GTM components addressed?"},
            {"criterion": "Efficiency", "weight": 10, "description": "Is the plan actionable and prioritized?"},
        ],
        "domain": "product",
        "difficulty": "advanced",
        "task_type": "product",
        "submission_types": ["text", "file"],
        "allowed_file_types": ["pdf", "docx"],
        "skills_tested": ["product strategy", "roadmapping"],
        "estimated_hours": 5.0,
        "company_visible": True,
        "company_name": "HireX",
        "prize_or_opportunity": "Top submission gets a PM role offer",
        "deadline_days": 12,
    },
    {
        "title": "Analyze 3 Competitors of Swiggy and Suggest Improvements",
        "slug": "analyze-swiggy-competitors",
        "description": "Conduct a competitive analysis of Swiggy's top 3 competitors (Zomato, Dunzo, Blinkit) and suggest 3 strategic improvements Swiggy should make.",
        "problem_statement": "Analyze Zomato, Dunzo, and Blinkit across: product features, pricing, UX, and market positioning. Then suggest 3 specific, actionable improvements for Swiggy with supporting rationale.",
        "evaluation_criteria": [
            {"criterion": "Accuracy", "weight": 40, "description": "Is the competitive analysis factually accurate?"},
            {"criterion": "Approach & Thinking", "weight": 30, "description": "Are the insights sharp and non-obvious?"},
            {"criterion": "Completeness", "weight": 20, "description": "Are all 3 competitors analyzed and 3 improvements suggested?"},
            {"criterion": "Efficiency", "weight": 10, "description": "Is the analysis concise and well-structured?"},
        ],
        "domain": "business",
        "difficulty": "beginner",
        "task_type": "business",
        "submission_types": ["text"],
        "skills_tested": ["business analysis", "market research"],
        "estimated_hours": 2.5,
        "company_visible": False,
        "deadline_days": 5,
    },
    {
        "title": "Write a LinkedIn Post Campaign for a SaaS Launch",
        "slug": "linkedin-campaign-saas-launch",
        "description": "Create a 5-post LinkedIn campaign for the launch of a B2B SaaS product that helps remote teams manage async communication.",
        "problem_statement": "Write 5 LinkedIn posts for a 2-week launch campaign. Each post should have a different angle (problem, solution, social proof, feature spotlight, CTA). Include hooks, body copy, and hashtags.",
        "evaluation_criteria": [
            {"criterion": "Accuracy", "weight": 40, "description": "Do the posts effectively communicate the product value?"},
            {"criterion": "Approach & Thinking", "weight": 30, "description": "Is the campaign strategy coherent and well-sequenced?"},
            {"criterion": "Completeness", "weight": 20, "description": "Are all 5 posts complete with hooks, body, and hashtags?"},
            {"criterion": "Efficiency", "weight": 10, "description": "Is the writing tight and engaging?"},
        ],
        "domain": "marketing",
        "difficulty": "intermediate",
        "task_type": "writing",
        "submission_types": ["text"],
        "skills_tested": ["content marketing", "copywriting", "social media"],
        "estimated_hours": 2.0,
        "company_visible": True,
        "company_name": "AsyncHQ",
        "deadline_days": 4,
    },
    {
        "title": "Write a Technical Blog Post on Flutter State Management",
        "slug": "technical-blog-flutter-state-management",
        "description": "Write a comprehensive technical blog post comparing the top 3 Flutter state management solutions: Riverpod, Bloc, and Provider.",
        "problem_statement": "Write a 1500-2000 word technical blog post that: explains the problem state management solves, compares Riverpod, Bloc, and Provider with code examples, and gives a recommendation for different use cases.",
        "evaluation_criteria": [
            {"criterion": "Accuracy", "weight": 40, "description": "Is the technical content accurate and up-to-date?"},
            {"criterion": "Approach & Thinking", "weight": 30, "description": "Is the comparison balanced and insightful?"},
            {"criterion": "Completeness", "weight": 20, "description": "Are all 3 solutions covered with code examples?"},
            {"criterion": "Efficiency", "weight": 10, "description": "Is the writing clear and well-structured?"},
        ],
        "domain": "writing",
        "difficulty": "beginner",
        "task_type": "writing",
        "submission_types": ["text"],
        "skills_tested": ["technical writing", "flutter", "dart"],
        "estimated_hours": 3.0,
        "company_visible": False,
        "deadline_days": 6,
    },
]


async def seed(db: AsyncSession) -> None:
    # Get or create a system recruiter user
    result = await db.execute(select(User).where(User.email == "system@hirex.io"))
    recruiter = result.scalar_one_or_none()

    if not recruiter:
        recruiter = User(
            firebase_uid="system-recruiter-uid",
            email="system@hirex.io",
            full_name="HireX System",
            role="recruiter",
            onboarding_complete=True,
        )
        db.add(recruiter)
        await db.flush()
        await db.refresh(recruiter)

    now = datetime.utcnow()
    created = 0

    for task_data in SEED_TASKS:
        # Check if already exists
        existing = await db.execute(select(Task).where(Task.slug == task_data["slug"]))
        if existing.scalar_one_or_none():
            print(f"  Skipping (exists): {task_data['title']}")
            continue

        deadline_days = task_data["deadline_days"]
        task_fields = {k: v for k, v in task_data.items() if k != "deadline_days"}
        task = Task(
            recruiter_id=recruiter.id,
            deadline=now + timedelta(days=deadline_days),
            is_published=True,
            is_active=True,
            max_file_size_mb=10,
            **task_fields,
        )
        db.add(task)
        created += 1
        print(f"  Created: {task_data['title']}")

    await db.commit()
    print(f"\nSeeded {created} tasks successfully.")


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as db:
        await seed(db)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
