# Agentic Test System

AI agentic workflow for generating interview tests from a job description (JD) using FastAPI, LangGraph, and LangChain with Gemini 2.5 Flash.

## Project Structure

- app/main.py - FastAPI entrypoint
- app/api/routes.py - API routes
- app/core/config.py - environment config
- app/core/logging.py - logging setup
- app/schemas/request.py - request model
- app/schemas/response.py - response model
- app/agents/* - JD decomposition and test generation agents
- app/graph/workflow.py - LangGraph workflow
- app/services/orchestrator.py - workflow execution service
- app/utils/helpers.py - shared helpers

## Setup

1. Create and activate virtual environment.
2. Install dependencies:

   pip install -r requirements.txt

3. Add your API key in .env:

   GOOGLE_API_KEY=your_key_here

4. Run server:

   uvicorn app.main:app --reload

## API

- GET /api/v1/health
- POST /api/v1/generate-test

Example request body:

{
  "job_description": "We need a Python backend engineer with FastAPI and system design experience...",
  "role_title": "Backend Engineer",
  "question_count": 10,
  "difficulty": "medium"
}
