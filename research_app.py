import os
import io
import asyncio
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import logging
import json
from typing import List, Optional

from research_models import init_db, get_research_db, ResearchProject, CorpusFile, TermCandidate, DefinitionExperiment, ConceptRelation
from dotenv import load_dotenv
load_dotenv()
from symbolic_parser import SymbolicDefinitionParser
import project_rag
import csv
import io
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

# ── LLM utilities — lightweight, no main.py import ──
from llm_utils import llm_manager, generate_with_timeout_multi, extract_text_from_pdf, extract_text_from_docx

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

# Inject API keys from environment into the manager
_env_keys = {
    "gemini": os.getenv("GEMINI_API_KEY"),
    "anthropic": os.getenv("ANTHROPIC_API_KEY"),
    "openai": os.getenv("OPENAI_API_KEY"),
    "openrouter": os.getenv("OPENROUTER_API_KEY"),
}
for _provider, _key in _env_keys.items():
    if _key:
        llm_manager.system_api_keys[_provider] = _key
logger.info(f"LLM keys: { {k: 'Present' if v else 'Missing' for k, v in llm_manager.system_api_keys.items()} }")


@app.get("/api/ping")
async def ping():
    return {"status": "ok", "app": "research_app", "ready": True}

@app.get("/api/llm-list")
async def list_models():
    """Returns available models."""
    try:
        models = llm_manager.get_available_models()
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
    return templates.TemplateResponse(request=request, name="research.html")

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

    try:
        if filename.endswith(".pdf"):
            text_content = extract_text_from_pdf(content_bytes)
        elif filename.endswith(".docx"):
            text_content = extract_text_from_docx(content_bytes)
        else:
            text_content = content_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"Extraction failed for {filename}: {e}")
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    if not text_content:
        raise HTTPException(status_code=400, detail="Extracted text is empty")

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

    guidelines_path = os.path.join(os.path.dirname(__file__), "instructions", "term_extraction_guidelines.md")
    with open(guidelines_path, "r") as f:
        guidelines = f.read()

    extracted_terms_count = 0

    for file in corpus_files:
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
                response_text = await generate_with_timeout_multi(prompt, provider=model)
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()

                terms = json.loads(response_text)

                for term_text in terms:
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

    eval_guidelines_path = os.path.join(os.path.dirname(__file__), "instructions", "definition_evaluation_grid.md")
    with open(eval_guidelines_path, "r") as f:
        eval_guidelines = f.read()

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

    for p_type, p_text in prompts.items():
        try:
            definition = await generate_with_timeout_multi(p_text, provider=model)
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

    # Gather corpus texts for RAG
    corpus_texts = [f.cleaned_content for f in project.corpus_files if f.cleaned_content]

    # ── Keyword RAG Strategy ──
    try:
        keyword_results = project_rag.keyword_retrieve(term.term, corpus_texts, top_k=5)
        keyword_context = "\n".join([r["text"] for r in keyword_results])

        keyword_rag_prompt = f"""Using the following context retrieved from our corpus via keyword matching:
{keyword_context}

Define the term '{term.term}' for the domain '{project.domain}'.
{eval_guidelines}
Output ONLY the definition text."""

        definition_krag = await generate_with_timeout_multi(keyword_rag_prompt, provider=model)
        experiment_krag = DefinitionExperiment(
            term_id=term.id,
            model_id=model,
            prompt_type="keyword-rag",
            prompt_content=keyword_rag_prompt,
            definition_text=definition_krag.strip(),
            is_rag=True,
            rag_sources={"method": "keyword", "passages": [r["text"] for r in keyword_results]}
        )
        db.add(experiment_krag)
        results.append({"type": "keyword-rag", "text": definition_krag.strip()})
    except Exception as e:
        logger.error(f"Keyword-RAG experiment failed: {e}")

    # ── Vector RAG Strategy ──
    try:
        faiss_index, chunks = project_rag.build_project_index(corpus_texts)
        vector_results = project_rag.retrieve(term.term, faiss_index, chunks, top_k=5)
        vector_context = "\n".join([r["text"] for r in vector_results])

        vector_rag_prompt = f"""Using the following context retrieved from our corpus via semantic vector search:
{vector_context}

Define the term '{term.term}' for the domain '{project.domain}'.
{eval_guidelines}
Output ONLY the definition text."""

        definition_vrag = await generate_with_timeout_multi(vector_rag_prompt, provider=model)
        experiment_vrag = DefinitionExperiment(
            term_id=term.id,
            model_id=model,
            prompt_type="vector-rag",
            prompt_content=vector_rag_prompt,
            definition_text=definition_vrag.strip(),
            is_rag=True,
            rag_sources={"method": "vector", "passages": [{"text": r["text"], "score": r["score"]} for r in vector_results]}
        )
        db.add(experiment_vrag)
        results.append({"type": "vector-rag", "text": definition_vrag.strip()})
    except Exception as e:
        logger.error(f"Vector-RAG experiment failed: {e}")

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

# ══════════════════════════════════════════════════════════════
# DELETE PROJECT
# ══════════════════════════════════════════════════════════════

@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: int, db: Session = Depends(get_research_db)):
    project = db.query(ResearchProject).filter(ResearchProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.query(ConceptRelation).filter(ConceptRelation.project_id == project_id).delete()
    for term in db.query(TermCandidate).filter(TermCandidate.project_id == project_id).all():
        db.query(DefinitionExperiment).filter(DefinitionExperiment.term_id == term.id).delete()
    db.query(TermCandidate).filter(TermCandidate.project_id == project_id).delete()
    db.query(CorpusFile).filter(CorpusFile.project_id == project_id).delete()
    db.delete(project)
    db.commit()
    return {"status": "deleted", "project_id": project_id}


# ══════════════════════════════════════════════════════════════
# NEURO-SYMBOLIC FEEDBACK LOOP
# ══════════════════════════════════════════════════════════════

@app.post("/api/projects/{project_id}/neurosymbolic-define")
async def neurosymbolic_define(
    project_id: int,
    term_id: int = Form(...),
    model: str = Form("gemini-1.5-pro"),
    max_iterations: int = Form(3),
    rag_mode: str = Form("none"),
    db: Session = Depends(get_research_db)
):
    """
    Neuro-symbolic definition generation with feedback loop.
    1. (Optional) Retrieve context from corpus via keyword or vector RAG
    2. LLM generates an initial definition
    3. Symbolic parser validates it
    4. If validation fails, parser generates targeted feedback
    5. LLM rewrites the definition using the feedback
    6. Repeat until valid or max_iterations reached
    Each iteration is saved as a separate DefinitionExperiment.

    rag_mode: "none" | "keyword" | "vector"
    """
    project = db.query(ResearchProject).filter(ResearchProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    term = db.query(TermCandidate).filter(TermCandidate.id == term_id).first()
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")

    eval_guidelines_path = os.path.join(os.path.dirname(__file__), "instructions", "definition_evaluation_grid.md")
    with open(eval_guidelines_path, "r") as f:
        eval_guidelines = f.read()

    all_terms = db.query(TermCandidate).filter(TermCandidate.project_id == project_id).all()
    known_term_strings = [t.term for t in all_terms]
    parser = SymbolicDefinitionParser(known_terms=known_term_strings)

    # Build RAG context if requested
    rag_context = ""
    rag_sources_data = None
    if rag_mode in ("keyword", "vector"):
        corpus_texts = [f.cleaned_content for f in project.corpus_files if f.cleaned_content]
        if corpus_texts:
            if rag_mode == "keyword":
                rag_results = project_rag.keyword_retrieve(term.term, corpus_texts, top_k=5)
                rag_context = "\n".join([r["text"] for r in rag_results])
                rag_sources_data = {"method": "keyword", "passages": [r["text"] for r in rag_results]}
            elif rag_mode == "vector":
                faiss_index, chunks = project_rag.build_project_index(corpus_texts)
                rag_results = project_rag.retrieve(term.term, faiss_index, chunks, top_k=5)
                rag_context = "\n".join([r["text"] for r in rag_results])
                rag_sources_data = {"method": "vector", "passages": [{"text": r["text"], "score": r["score"]} for r in rag_results]}

    rag_preamble = ""
    if rag_context:
        rag_preamble = f"""Using the following context retrieved from our corpus ({rag_mode} retrieval):
{rag_context}

"""

    iterations = []
    current_definition = None
    prompt_type_prefix = f"neurosymbolic-{rag_mode}" if rag_mode != "none" else "neurosymbolic"
    current_prompt = f"""{rag_preamble}Define the following term for the domain '{project.domain}': {term.term}.
Follow these quality standards:
{eval_guidelines}
Output ONLY the definition text, nothing else."""

    for i in range(max_iterations):
        try:
            definition = await generate_with_timeout_multi(current_prompt, provider=model)
            definition = definition.strip()
            current_definition = definition

            validation = parser.validate_structure(definition, term.term, lang=term.language)

            experiment = DefinitionExperiment(
                term_id=term.id,
                model_id=model,
                prompt_type=f"{prompt_type_prefix}-iter-{i+1}",
                prompt_content=current_prompt,
                definition_text=definition,
                is_rag=(rag_mode != "none"),
                rag_sources=rag_sources_data if (i == 0 and rag_mode != "none") else None,
                auto_valid=validation["valid"],
                auto_score=float(validation["score"]),
                manual_comment="; ".join(validation["reasons"]) if validation["reasons"] else "All checks passed",
            )
            db.add(experiment)

            iteration_result = {
                "iteration": i + 1,
                "definition": definition,
                "score": validation["score"],
                "max_score": validation["max_score"],
                "valid": validation["valid"],
                "checks": validation["checks"],
            }
            iterations.append(iteration_result)

            if validation["valid"]:
                break

            feedback = parser.get_feedback_prompt(definition, term.term, validation, lang=term.language)
            current_prompt = feedback

        except Exception as e:
            logger.error(f"Neurosymbolic iteration {i+1} failed: {e}")
            iterations.append({
                "iteration": i + 1,
                "error": str(e),
            })
            break

    db.commit()

    return {
        "term": term.term,
        "model": model,
        "rag_mode": rag_mode,
        "total_iterations": len(iterations),
        "final_valid": iterations[-1].get("valid", False) if iterations else False,
        "final_definition": current_definition,
        "iterations": iterations,
    }


# ══════════════════════════════════════════════════════════════
# CONCEPT RELATION EXTRACTION + GRAPH VALIDATION
# ══════════════════════════════════════════════════════════════

@app.post("/api/projects/{project_id}/extract-relations")
async def extract_concept_relations(
    project_id: int,
    model: str = Form("gemini-1.5-pro"),
    db: Session = Depends(get_research_db)
):
    """
    Extract concept relations between terms using LLM, then validate
    the resulting graph symbolically (cycle detection, consistency).
    """
    project = db.query(ResearchProject).filter(ResearchProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    terms = db.query(TermCandidate).filter(TermCandidate.project_id == project_id).all()
    if len(terms) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 terms to extract relations")

    term_names = [t.term for t in terms]
    term_map = {t.term.lower(): t for t in terms}

    prompt = f"""You are an expert terminologist analyzing the domain '{project.domain}'.

Given these domain-specific terms:
{json.dumps(term_names, ensure_ascii=False)}

For each meaningful relationship between terms, output a JSON array of objects with:
- "source": the source term (exact match from list above)
- "target": the target term (exact match from list above)
- "relation": one of "IS-A" (hypernymy), "PART-OF" (meronymy), "CAUSES" (causation), "RELATED-TO" (association)

Rules:
- IS-A means source is a specific type of target (e.g. "celiac disease" IS-A "autoimmune disorder")
- PART-OF means source is a component of target (e.g. "villi" PART-OF "small intestine")
- CAUSES means source leads to or triggers target (e.g. "gluten ingestion" CAUSES "immune response")
- RELATED-TO for other meaningful domain associations
- Only include relationships you are confident about
- Output ONLY a valid JSON array, nothing else

JSON array:"""

    try:
        response_text = await generate_with_timeout_multi(prompt, provider=model)

        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        relations_raw = json.loads(response_text)
    except Exception as e:
        logger.error(f"Relation extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM extraction failed: {str(e)}")

    saved_relations = []
    for rel in relations_raw:
        source_label = rel.get("source", "")
        target_label = rel.get("target", "")
        relation_type = rel.get("relation", "RELATED-TO")

        if relation_type not in ("IS-A", "PART-OF", "CAUSES", "RELATED-TO"):
            relation_type = "RELATED-TO"

        source_term = term_map.get(source_label.lower())
        target_term = term_map.get(target_label.lower())

        cr = ConceptRelation(
            project_id=project_id,
            source_term_id=source_term.id if source_term else None,
            target_term_id=target_term.id if target_term else None,
            source_label=source_label,
            target_label=target_label,
            relation_type=relation_type,
            model_used=model,
        )
        db.add(cr)
        saved_relations.append({
            "source": source_label,
            "target": target_label,
            "relation": relation_type,
        })

    db.commit()

    # ── Symbolic graph validation ──
    graph_issues = _validate_concept_graph(saved_relations)

    if graph_issues:
        relations_in_db = db.query(ConceptRelation).filter(
            ConceptRelation.project_id == project_id,
            ConceptRelation.model_used == model
        ).order_by(ConceptRelation.id.desc()).limit(len(saved_relations)).all()

        issue_lookup = {}
        for issue in graph_issues:
            for rel_key in issue.get("involved_relations", []):
                issue_lookup.setdefault(rel_key, []).append(issue["issue"])

        for cr_db in relations_in_db:
            key = f"{cr_db.source_label}|{cr_db.relation_type}|{cr_db.target_label}"
            if key in issue_lookup:
                cr_db.is_valid = False
                cr_db.validation_note = "; ".join(issue_lookup[key])
            else:
                cr_db.is_valid = True
        db.commit()

    return {
        "relations_count": len(saved_relations),
        "relations": saved_relations,
        "graph_validation": {
            "issues_found": len(graph_issues),
            "issues": graph_issues,
        }
    }


@app.get("/api/projects/{project_id}/relations")
async def get_concept_relations(project_id: int, db: Session = Depends(get_research_db)):
    relations = db.query(ConceptRelation).filter(ConceptRelation.project_id == project_id).all()
    return [{
        "id": r.id,
        "source": r.source_label,
        "target": r.target_label,
        "relation": r.relation_type,
        "is_valid": r.is_valid,
        "validation_note": r.validation_note,
    } for r in relations]


def _validate_concept_graph(relations: list) -> list:
    """
    Symbolic validation of the concept relation graph.
    Checks for: cycles in IS-A hierarchy, self-references, contradictions.
    """
    issues = []

    isa_graph = {}
    all_edges = set()

    for rel in relations:
        src = rel["source"].lower()
        tgt = rel["target"].lower()
        rtype = rel["relation"]

        if src == tgt:
            issues.append({
                "type": "self_reference",
                "issue": f"Self-reference: '{rel['source']}' {rtype} '{rel['target']}'",
                "involved_relations": [f"{rel['source']}|{rtype}|{rel['target']}"],
            })
            continue

        edge_key = (src, rtype, tgt)
        if edge_key in all_edges:
            issues.append({
                "type": "duplicate",
                "issue": f"Duplicate relation: '{rel['source']}' {rtype} '{rel['target']}'",
                "involved_relations": [f"{rel['source']}|{rtype}|{rel['target']}"],
            })
        all_edges.add(edge_key)

        if rtype == "IS-A":
            isa_graph.setdefault(src, []).append(tgt)

    visited = set()
    rec_stack = set()

    def _find_cycle(node, path):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in isa_graph.get(node, []):
            if neighbor not in visited:
                cycle = _find_cycle(neighbor, path + [neighbor])
                if cycle:
                    return cycle
            elif neighbor in rec_stack:
                cycle_path = path[path.index(neighbor):] + [neighbor]
                return cycle_path
        rec_stack.discard(node)
        return None

    for node in isa_graph:
        if node not in visited:
            cycle = _find_cycle(node, [node])
            if cycle:
                cycle_display = " → ".join(cycle)
                issues.append({
                    "type": "cycle",
                    "issue": f"Cycle in IS-A hierarchy: {cycle_display}",
                    "involved_relations": [
                        f"{cycle[i]}|IS-A|{cycle[i+1]}" for i in range(len(cycle)-1)
                    ],
                })

    for src, targets in isa_graph.items():
        for tgt in targets:
            if tgt in isa_graph and src in isa_graph[tgt]:
                issues.append({
                    "type": "contradiction",
                    "issue": f"Contradictory IS-A: '{src}' IS-A '{tgt}' AND '{tgt}' IS-A '{src}'",
                    "involved_relations": [f"{src}|IS-A|{tgt}", f"{tgt}|IS-A|{src}"],
                })

    return issues


# ══════════════════════════════════════════════════════════════
# ENHANCED AUTO-VALIDATE (updated to use new parser)
# ══════════════════════════════════════════════════════════════

@app.post("/api/validate/auto-enhanced")
async def auto_validate_enhanced(experiment_id: int, db: Session = Depends(get_research_db)):
    """Enhanced validation using the full symbolic parser with all checks."""
    exp = db.query(DefinitionExperiment).filter(DefinitionExperiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    term = db.query(TermCandidate).filter(TermCandidate.id == exp.term_id).first()

    all_terms = db.query(TermCandidate).filter(TermCandidate.project_id == term.project_id).all()
    known_term_strings = [t.term for t in all_terms]
    parser = SymbolicDefinitionParser(known_terms=known_term_strings)

    result = parser.validate_structure(exp.definition_text, term.term, lang=term.language)

    exp.auto_valid = result["valid"]
    exp.auto_score = float(result["score"])
    exp.manual_comment = "; ".join(result["reasons"]) if result["reasons"] else "All checks passed"

    db.commit()
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
