import os
import io
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import logging
import json
from typing import List, Optional

from research_models import init_db, get_research_db, ResearchProject, CorpusFile, TermCandidate, DefinitionExperiment
from dotenv import load_dotenv
load_dotenv()
from symbolic_parser import SymbolicDefinitionParser
import csv
import io
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize DB
init_db()

app = FastAPI(title="AI Assisted Terminography Research - Spring 2026")

# Set up paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Lazy import of main.py — deferred to startup so the port binds first
_main_module = None
llm_manager = None

def _get_main():
    """Lazy import of main module to avoid blocking port binding with heavy ML model loading."""
    global _main_module
    if _main_module is None:
        import main
        _main_module = main
    return _main_module

@app.on_event("startup")
async def startup_init_main():
    """Load main.py and its heavy dependencies AFTER uvicorn has bound the port."""
    global llm_manager
    logger.info("Port is bound — now loading main module and LLM manager...")
    main = _get_main()
    llm_manager = main.llm_manager

    # Inject API keys
    env_keys = {
        "gemini": os.getenv("GEMINI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
        "openai": os.getenv("OPENAI_API_KEY"),
        "openrouter": os.getenv("OPENROUTER_API_KEY"),
    }
    logger.info(f"Keys found in env: { {k: 'Present' if v else 'Missing' for k, v in env_keys.items()} }")

    for provider, key in env_keys.items():
        if key:
            llm_manager.system_api_keys[provider] = key

    logger.info(f"Final manager keys: { {k: 'Present' if v else 'Missing' for k, v in llm_manager.system_api_keys.items()} }")
    logger.info("Main module loaded successfully.")

@app.get("/api/ping")
async def ping():
    return {"status": "ok", "app": "research_app"}

@app.get("/api/llm-list")
async def list_models():
    """Returns available models from the main system with fallback"""
    try:
        models = llm_manager.get_available_models()
        # Ensure it's not empty, if so provide common ones
        if not models:
             models = {
                "gemini-1.5-pro": {"name": "Gemini 1.5 Pro", "available": True},
                "claude-3-5-sonnet-20241022": {"name": "Claude 3.5 Sonnet", "available": True}
             }
        logger.info(f"Returning {len(models)} models from llm-list.")
        return models
    except Exception as e:
        logger.error(f"Error in llm-list: {e}")
        return {
            "gemini-1.5-pro": {"name": "Gemini 1.5 Pro", "available": True},
            "claude-3-5-sonnet-20241022": {"name": "Claude 3.5 Sonnet", "available": True}
        }

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("research.html", {"request": request})

# PROJECT ENDPOINTS
@app.post("/api/projects")
async def create_project(name: str = Form(...), domain: str = Form(...), db: Session = Depends(get_research_db)):
    project = ResearchProject(name=name, domain=domain)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@app.get("/api/projects")
async def list_projects(db: Session = Depends(get_research_db)):
    return db.query(ResearchProject).all()

# CORPUS ENDPOINTS
@app.post("/api/projects/{project_id}/corpus")
async def upload_corpus(project_id: int, file: UploadFile = File(...), language: str = Form(...), db: Session = Depends(get_research_db)):
    content_bytes = await file.read()
    filename = file.filename.lower()
    text_content = ""

    # Reuse extractors from main.py if possible, otherwise use specialized tool logic
    try:
        if filename.endswith(".pdf"):
            # Using main's EletoDocumentScraper logic roughly
            scraper = _get_main().EletoDocumentScraper()
            text_content = scraper.extract_text_from_pdf(content_bytes)
        elif filename.endswith(".docx"):
            scraper = _get_main().EletoDocumentScraper()
            text_content = scraper.extract_text_from_docx(content_bytes)
        else:
            text_content = content_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Extraction failed for {filename}: {e}")
        raise HTTPException(status_code=400, detail="Could not extract text from file")
    
    if not text_content:
        raise HTTPException(status_code=400, detail="Extracted text is empty")

    # Basic cleaning
    cleaned_content = text_content.strip()
    
    corpus_file = CorpusFile(
        project_id=project_id,
        filename=file.filename,
        content=text_content,
        cleaned_content=cleaned_content,
        language=language,
        source_type="upload"
    )
    db.add(corpus_file)
    db.commit()
    db.refresh(corpus_file)
    return {"id": corpus_file.id, "filename": corpus_file.filename}

@app.get("/api/projects/{project_id}/corpus-list")
async def list_corpus_files(project_id: int, db: Session = Depends(get_research_db)):
    return db.query(CorpusFile).filter(CorpusFile.project_id == project_id).all()

# EXTRACTION ENDPOINTS (Phase 3)
@app.post("/api/projects/{project_id}/extract-terms")
async def trigger_term_extraction(project_id: int, model: str = Form("gemini-1.5-pro"), db: Session = Depends(get_research_db)):
    project = db.query(ResearchProject).filter(ResearchProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    corpus_files = db.query(CorpusFile).filter(CorpusFile.project_id == project_id).all()
    if not corpus_files:
        raise HTTPException(status_code=400, detail="No corpus files found for this project")

    # Load guidelines
    guidelines_path = os.path.join(os.path.dirname(__file__), "instructions", "term_extraction_guidelines.md")
    with open(guidelines_path, "r") as f:
        guidelines = f.read()

    extracted_terms_count = 0
    
    for file in corpus_files:
        # Process in chunks of ~2000 characters to keep context
        text_content = file.cleaned_content
        chunks = [text_content[i:i+4000] for i in range(0, len(text_content), 4000)]
        
        for chunk in chunks:
            prompt = f"""
            System: You are an expert terminologist following ISO standards.
            Instructions:
            {guidelines}
            
            Text to analyze ({file.language}):
            {chunk}
            
            Task: Extract domain-specific terms for '{project.domain}'. 
            Output format: A JSON array of strings only.
            """
            
            try:
                response_text = await _get_main().generate_with_timeout_multi(prompt, provider=model)
                # Cleanup potential markdown code blocks
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()
                
                terms = json.loads(response_text)
                
                for term_text in terms:
                    # Check if exists
                    existing = db.query(TermCandidate).filter(
                        TermCandidate.project_id == project_id,
                        TermCandidate.term == term_text,
                        TermCandidate.language == file.language
                    ).first()
                    
                    if existing:
                        existing.frequency += 1
                    else:
                        new_term = TermCandidate(
                            project_id=project_id,
                            term=term_text,
                            language=file.language,
                            model_used=model,
                            frequency=1
                        )
                        db.add(new_term)
                    extracted_terms_count += 1
                
                db.commit()
            except Exception as e:
                logger.error(f"Error extracting terms from chunk: {e}")
                continue

    return {"status": "completed", "extracted_count": extracted_terms_count}

@app.get("/api/projects/{project_id}/terms")
async def get_project_terms(project_id: int, db: Session = Depends(get_research_db)):
    return db.query(TermCandidate).filter(TermCandidate.project_id == project_id).all()

@app.post("/api/projects/{project_id}/extract-definitions")
async def extract_definitions(project_id: int, term_id: int = Form(...), model: str = Form("gemini-1.5-pro"), db: Session = Depends(get_research_db)):
    project = db.query(ResearchProject).filter(ResearchProject.id == project_id).first()
    term = db.query(TermCandidate).filter(TermCandidate.id == term_id).first()
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")

    # Load definition guidelines
    eval_guidelines_path = os.path.join(os.path.dirname(__file__), "instructions", "definition_evaluation_grid.md")
    with open(eval_guidelines_path, "r") as f:
        eval_guidelines = f.read()

    # Define 3 Prompt Strategies
    prompts = {
        "zero-shot": f"""
        Define the following term for the domain '{project.domain}': {term.term}.
        Follow these quality standards:
        {eval_guidelines}
        Output only the definition text.
        """,
        "few-shot": f"""
        Domain: Medicine (Celiac Disease)
        Term: Celiac Disease
        Definition: A chronic immune-mediated disorder triggered by gluten ingestion in genetically predisposed individuals, causing inflammation of the small intestine.
        
        Domain: {project.domain}
        Term: {term.term}
        Definition: 
        """,
        "cot-enhanced": f"""
        Step 1: Identify the superordinate concept (genus) for '{term.term}' in {project.domain}.
        Step 2: Identify the specific characteristics (differentia) that distinguish it.
        Step 3: Combine them into a single, concise ISO-compliant definition.
        
        Guidelines:
        {eval_guidelines}
        
        Final Definition for '{term.term}':
        """
    }

    results = []

    # Run the 3 prompt experiments
    for p_type, p_text in prompts.items():
        try:
            definition = await _get_main().generate_with_timeout_multi(p_text, provider=model)
            experiment = DefinitionExperiment(
                term_id=term.id,
                model_id=model,
                prompt_type=p_type,
                prompt_content=p_text,
                definition_text=definition.strip(),
                is_rag=False
            )
            db.add(experiment)
            results.append({"type": p_type, "text": definition.strip()})
        except Exception as e:
            logger.error(f"Experiment {p_type} failed: {e}")

    # Add RAG Strategy (reusing main.rag_system effectively)
    try:
        # Placeholder for RAG logic - ideally we'd use main.TerminologyRAGSystem
        # For the research protocol, we retrieve from the project's OWN corpus
        corpus_text = "\n".join([f.cleaned_content for f in project.corpus_files])
        # Simple "manual RAG" for this demo/request - find relevant context
        context = ""
        lines = corpus_text.split("\n")
        relevant_lines = [line for line in lines if term.term.lower() in line.lower()][:5]
        context = "\n".join(relevant_lines)

        rag_prompt = f"""
        Using the following context from our corpus:
        {context}
        
        Define the term '{term.term}' for the domain '{project.domain}'.
        {eval_guidelines}
        """
        
        definition_rag = await _get_main().generate_with_timeout_multi(rag_prompt, provider=model)
        experiment_rag = DefinitionExperiment(
            term_id=term.id,
            model_id=model,
            prompt_type="rag-enhanced",
            prompt_content=rag_prompt,
            definition_text=definition_rag.strip(),
            is_rag=True,
            rag_sources={"lines": relevant_lines}
        )
        db.add(experiment_rag)
        results.append({"type": "rag-enhanced", "text": definition_rag.strip()})
    except Exception as e:
        logger.error(f"RAG experiment failed: {e}")

    db.commit()
    return {"term": term.term, "results": results}

@app.post("/api/validate/auto")
async def auto_validate(experiment_id: int, db: Session = Depends(get_research_db)):
    exp = db.query(DefinitionExperiment).filter(DefinitionExperiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    term = db.query(TermCandidate).filter(TermCandidate.id == exp.term_id).first()
    parser = SymbolicDefinitionParser()
    
    result = parser.validate_structure(exp.definition_text, term.term, lang=term.language)
    
    exp.auto_valid = result["valid"]
    exp.auto_score = float(result["score"])
    exp.manual_comment = "; ".join(result["reasons"])
    
    db.commit()
    return result

@app.get("/api/projects/{project_id}/export")
async def export_results(project_id: int, db: Session = Depends(get_research_db)):
    terms = db.query(TermCandidate).filter(TermCandidate.project_id == project_id).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Term", "Language", "Model", "Strategy", "Definition", "Auto Valid", "Score", "Notes"])
    
    for t in terms:
        for d in t.definitions:
            writer.writerow([t.term, t.language, d.model_id, d.prompt_type, d.definition_text, d.auto_valid, d.auto_score, d.manual_comment])
            
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=research_results_{project_id}.csv"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
