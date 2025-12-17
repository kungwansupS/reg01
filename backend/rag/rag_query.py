from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

from config import RAGConfig
from core_components import RAGCore


def ask(query: str):
    retriever = RAGCore.get_retriever()

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=RAGConfig.GOOGLE_API_KEY,
        temperature=RAGConfig.LLM_TEMPERATURE,
    )

    system_prompt = (
        "ตอบคำถามโดยอ้างอิงจาก context เท่านั้น "
        "ถ้าไม่พบข้อมูลให้ตอบว่าไม่ทราบ\n\n"
        "{context}"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    qa_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, qa_chain)

    result = rag_chain.invoke({"input": query})

    return {
        "answer": result["answer"],
        "sources": [
            doc.metadata.get("original_filename", "unknown")
            for doc in result["context"]
        ],
    }
