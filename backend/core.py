from langchain import hub
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore

INDEX_NAME="medium-blogs-embedding-index"


def run_llm(query:str):
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    docsearch = PineconeVectorStore(index_name=INDEX_NAME,embedding=embeddings)

    chat = ChatOpenAI(verbose=True,temperature=0)

    retrieval_qa_chat_prompt = hub.pull("langchain-ai/retrieval-qa-chat")

    stuff_documents_chain = create_stuff_documents_chain(chat,retrieval_qa_chat_prompt)

    qa = create_retrieval_chain(retriever=docsearch.as_retriever(),
                                combine_docs_chain=stuff_documents_chain)

    result = qa.invoke(input={"input":query})
    return result



if __name__ == "__main__":
    print(run_llm("who wrote the article , slashing build times at slice"))