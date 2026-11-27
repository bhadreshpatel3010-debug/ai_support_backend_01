from collections.abc import AsyncGenerator
from app.core.redis_client import get_cached_history, append_cached_history

async def stream_support_reply(
    user_id: int, question: str, db: AsyncSession
) -> AsyncGenerator[str, None]:
    # 1. Vector similarity search in PostgreSQL (pgvector)
    query_vector = await get_embedding(question)
    stmt = (
        select(DocumentChunk)
        .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
        .limit(4)
    )
    result = await db.execute(stmt)
    top_chunks = result.scalars().all()
    context_text = "\n---\n".join([f"[{c.filename}]: {c.content}" for c in top_chunks])

    # 2. Fetch recent chat history from Redis (fast in-memory cache)
    past_messages = await get_cached_history(user_id)
    history_text = "\n".join(
        [f"{m['role'].capitalize()}: {m['message']}" for m in past_messages]
    )

    prompt = f"""You are a helpful customer support assistant.
Answer the customer's question using ONLY the Company Knowledge Base below.
If the answer is not in the knowledge base, politely say you don't have that information and offer to connect them with a human agent.

Company Knowledge Base:
{context_text if context_text else "No documents uploaded yet."}

Recent Conversation:
{history_text}

Customer Question: {question}
"""

    # 3. Stream tokens from Gemini LLM in real time
    full_reply = []
    response_stream = await client.aio.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    async for chunk in response_stream:
        if chunk.text:
            full_reply.append(chunk.text)
            yield chunk.text

    complete_text = "".join(full_reply)

    # 4. Persist to both Redis (hot cache) and PostgreSQL (permanent storage)
    await append_cached_history(user_id, "user", question)
    await append_cached_history(user_id, "assistant", complete_text)

    db.add(ChatHistory(user_id=user_id, role="user", message=question))
    db.add(ChatHistory(user_id=user_id, role="assistant", message=complete_text))
    await db.commit()
