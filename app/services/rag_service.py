import io
from pypdf import PdfReader
from google import genai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.models.domain import DocumentChunk, ChatHistory

client = genai.Client(api_key=settings.GEMINI_API_KEY)

def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text)

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks

async def get_embedding(text: str) -> list[float]:
    response = await client.aio.models.embed_content(
        model="text-embedding-004",
        contents=text,
    )
    return response.embeddings[0].values

async def ingest_pdf(filename: str, file_bytes: bytes, db: AsyncSession) -> int:
    raw_text = extract_text_from_pdf(file_bytes)
    chunks = chunk_text(raw_text)
    
    for chunk in chunks:
        vector = await get_embedding(chunk)
        db.add(DocumentChunk(filename=filename, content=chunk, embedding=vector))
    
    await db.commit()
    return len(chunks)

async def generate_support_reply(user_id: int, question: str, db: AsyncSession) -> str:
    # 1. Async vector similarity search
    query_vector = await get_embedding(question)
    stmt = (
        select(DocumentChunk)
        .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
        .limit(4)
    )
    result = await db.execute(stmt)
    top_chunks = result.scalars().all()
    context_text = "\n---\n".join([f"[{c.filename}]: {c.content}" for c in top_chunks])

    # 2. Async chat history lookup
    history_stmt = (
        select(ChatHistory)
        .where(ChatHistory.user_id == user_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(6)
    )
    history_result = await db.execute(history_stmt)
    past_messages = history_result.scalars().all()
    history_text = "\n".join(
        [f"{m.role.capitalize()}: {m.message}" for m in reversed(past_messages)]
    )

    # 3. Async Gemini LLM call
    prompt = f"""You are a helpful customer support assistant.
Answer the customer's question using ONLY the Company Knowledge Base below.
If the answer is not in the knowledge base, politely say you don't have that information and offer to connect them with a human agent.

Company Knowledge Base:
{context_text if context_text else "No documents uploaded yet."}

Recent Conversation:
{history_text}

Customer Question: {question}
"""
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    reply = response.text

    # 4. Async save to database
    db.add(ChatHistory(user_id=user_id, role="user", message=question))
    db.add(ChatHistory(user_id=user_id, role="assistant", message=reply))
    await db.commit()

    return reply
