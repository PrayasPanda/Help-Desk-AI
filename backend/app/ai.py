"""LLM classification + RAG draft replies.

Two separate concerns, two separate calls:
- classify():    small prompt -> {category, priority, confidence}
- draft_reply(): retrieval over kb/*.md -> grounded reply + citations

If GROQ_API_KEY is unset, both fall back to a deterministic keyword mock so
every code path stays testable without a key (allowed by the brief, documented
in the README).
"""
import json
import logging
import re

from .config import settings
from .models import Category, Priority

log = logging.getLogger("quickdesk.ai")

# similarity threshold: below this the KB is considered irrelevant and the
# draft says so instead of letting the LLM freelance
MIN_SIMILARITY = 0.55
TOP_K = 3

NO_KB_MESSAGE = (
    "I couldn't find a relevant knowledge base article for this ticket, "
    "so I don't have enough verified information to draft a grounded reply. "
    "Please answer from your own knowledge of our internal processes."
)

_vector_store = None
_llm = None


def _get_llm():
    global _llm
    if _llm is None and settings.groq_api_key:
        from langchain_groq import ChatGroq

        _llm = ChatGroq(model=settings.groq_model, api_key=settings.groq_api_key, temperature=0)
    return _llm


def build_vector_store():
    """Load kb/*.md, chunk, embed, index. Rebuilt on every boot (KB is tiny)."""
    global _vector_store
    from langchain_community.embeddings import FastEmbedEmbeddings
    from langchain_core.documents import Document
    from langchain_core.vectorstores import InMemoryVectorStore
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    docs = []
    for path in sorted(settings.kb_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip() if text else path.stem
        docs.append(Document(page_content=text, metadata={"article": title, "file": path.name}))

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(docs)

    embeddings = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    _vector_store = InMemoryVectorStore(embeddings)
    _vector_store.add_documents(chunks)
    log.info("KB indexed: %d articles, %d chunks", len(docs), len(chunks))
    return _vector_store


def _extract_json(text: str) -> dict:
    """LLMs love wrapping JSON in prose/code fences; dig it out."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object in LLM output: {text[:200]}")
    return json.loads(match.group())


# ---------------- classification ----------------

CLASSIFY_PROMPT = """You are a helpdesk ticket classifier for an internal company tool.
Classify the ticket below.

Ticket title: {title}
Ticket description: {description}

Respond with ONLY a JSON object, no other text:
{{"category": "<IT|HR|Finance|Admin|Other>", "priority": "<Low|Medium|High>", "confidence": <0.0-1.0>}}"""

_MOCK_CATEGORY_KEYWORDS = {
    Category.IT: ["vpn", "password", "laptop", "wifi", "network", "software", "email", "login", "computer"],
    Category.HR: ["leave", "vacation", "holiday", "payroll", "salary", "onboarding", "resignation"],
    Category.Finance: ["expense", "reimburs", "invoice", "budget", "payment"],
    Category.Admin: ["desk", "office", "building", "parking", "id card", "stationery", "access card"],
}


def _mock_classify(title: str, description: str) -> dict:
    text = f"{title} {description}".lower()
    category = Category.Other
    for cat, words in _MOCK_CATEGORY_KEYWORDS.items():
        if any(w in text for w in words):
            category = cat
            break
    priority = Priority.High if any(w in text for w in ["urgent", "asap", "blocked", "cannot work", "down"]) else Priority.Medium
    return {"category": category, "priority": priority, "confidence": 0.5}


def classify(title: str, description: str) -> dict:
    """Returns {category: Category, priority: Priority, confidence: float}.

    Invalid/unexpected LLM output falls back to Other/Medium and is logged —
    the enum is enforced here, never trusted from the model.
    """
    llm = _get_llm()
    if llm is None:
        return _mock_classify(title, description)
    try:
        raw = llm.invoke(CLASSIFY_PROMPT.format(title=title, description=description)).content
        data = _extract_json(raw)
        try:
            category = Category(data.get("category"))
        except ValueError:
            log.warning("LLM returned invalid category %r, falling back to Other", data.get("category"))
            category = Category.Other
        try:
            priority = Priority(data.get("priority"))
        except ValueError:
            log.warning("LLM returned invalid priority %r, falling back to Medium", data.get("priority"))
            priority = Priority.Medium
        confidence = data.get("confidence")
        confidence = float(confidence) if isinstance(confidence, (int, float)) else None
        return {"category": category, "priority": priority, "confidence": confidence}
    except Exception:
        log.exception("classification failed, using mock fallback")
        return _mock_classify(title, description)


# ---------------- RAG draft reply ----------------

RAG_PROMPT = """You are drafting a helpdesk reply for a support agent to review.
Answer ONLY using the knowledge base context below. Do not invent policies,
URLs, or steps that are not in the context. If the context does not cover the
question, say you don't have enough information.

Knowledge base context:
{context}

Ticket title: {title}
Ticket description: {description}

Write a short, friendly, actionable reply (plain text, no markdown headers).
Respond with ONLY a JSON object, no other text:
{{"reply": "<the reply text>", "citations": [<titles of the articles you actually used>]}}"""


def draft_reply(title: str, description: str) -> dict:
    """Returns {draft: str, citations: list[str]}."""
    if _vector_store is None:
        raise RuntimeError("vector store not built — call build_vector_store() at startup")

    results = _vector_store.similarity_search_with_score(f"{title}\n{description}", k=TOP_K)
    relevant = [(doc, score) for doc, score in results if score >= MIN_SIMILARITY]
    if not relevant:
        return {"draft": NO_KB_MESSAGE, "citations": []}

    context = "\n\n---\n\n".join(
        f"[{doc.metadata['article']}]\n{doc.page_content}" for doc, _ in relevant
    )
    allowed_titles = {doc.metadata["article"] for doc, _ in relevant}

    llm = _get_llm()
    if llm is None:
        # mock: quote the single best-matching article
        best = relevant[0][0]
        return {
            "draft": f"Based on our internal documentation ({best.metadata['article']}):\n\n"
            f"{best.page_content.split(chr(10), 1)[-1].strip()[:600]}",
            "citations": [best.metadata["article"]],
        }
    try:
        raw = llm.invoke(RAG_PROMPT.format(context=context, title=title, description=description)).content
        data = _extract_json(raw)
        draft = str(data.get("reply", "")).strip() or NO_KB_MESSAGE
        # only accept citations that were actually in the retrieved context
        citations = [c for c in data.get("citations", []) if c in allowed_titles]
        return {"draft": draft, "citations": citations}
    except Exception:
        log.exception("draft generation failed, returning top chunk verbatim")
        best = relevant[0][0]
        return {
            "draft": f"(AI draft unavailable — closest KB article shown)\n\n{best.page_content[:600]}",
            "citations": [best.metadata["article"]],
        }
