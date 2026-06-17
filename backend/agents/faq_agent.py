"""
agents/faq_agent.py
====================
Answers general banking/loan questions using RAG (FAISS vector store).
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from openai import AzureOpenAI
from rag import retrieve
from prompts.faq_prompt import BANKING_SYSTEM_PROMPT
from utils.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    CHAT_DEPLOYMENT,
)

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION,
)


def faq_agent(user_message: str, chat_history: list) -> tuple:
    """
    Args:
        user_message  : latest user input
        chat_history  : list of {role, content} dicts

    Returns:
        answer        : assistant reply string
        scored_docs   : list of retrieved chunk dicts (for sidebar)
    """
    try:
        context, scored_docs = retrieve(query=user_message, chat_history=chat_history)
    except Exception:
        context = ""
        scored_docs = []

    api_messages = [
        {
            "role": "system",
            "content": f"""{BANKING_SYSTEM_PROMPT}

---
RELEVANT KNOWLEDGE BASE CONTEXT:
{context if context else "No specific context retrieved."}
---
""",
        }
    ]
    api_messages.extend(chat_history)
    api_messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=api_messages,
            temperature=0.3,
        )
        answer = response.choices[0].message.content
    except Exception as e:
        answer = f"Sorry, I encountered an error: {e}"

    return answer, scored_docs
