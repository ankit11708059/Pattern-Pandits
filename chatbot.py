from typing import Set

import streamlit as st
from backend.core import run_llm

st.header("🤖 CHATBOT")

prompt = st.text_input("Prompt", placeholder="Enter your prompt here")

# Initialize session state variables with consistent naming
if "user_prompt_history" not in st.session_state:
    st.session_state["user_prompt_history"] = []

if "chat_answers_history" not in st.session_state:
    st.session_state["chat_answers_history"] = []

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

def create_sources_string(source_urls: Set[str]) -> str:
    if not source_urls:
        return ""
    sources_list = list(source_urls)
    sources_list.sort()
    sources_string = "sources:\n"
    for i, source in enumerate(sources_list):
        sources_string += f"{i+1}. {source}\n"
    return sources_string

if prompt:
    with st.spinner("Generating Response"):
        try:
            generated_response = run_llm(prompt, chat_history=st.session_state["chat_history"])
            
            # Handle different response formats
            if isinstance(generated_response, dict):
                # Check for source_documents key
                if "source_documents" in generated_response:
                    sources = set([doc.metadata.get("source", "Unknown") for doc in generated_response["source_documents"]])
                    sources_string = create_sources_string(sources)
                else:
                    sources_string = ""
                
                # Get the result
                result = generated_response.get("result", generated_response.get("answer", str(generated_response)))
            else:
                # If response is just a string
                result = str(generated_response)
                sources_string = ""
            
            # Format the final response
            if sources_string:
                formatted_response = f"{result}\n\n{sources_string}"
            else:
                formatted_response = result

            # Update session state with consistent variable names
            st.session_state["user_prompt_history"].append(prompt)
            st.session_state["chat_answers_history"].append(formatted_response)
            st.session_state["chat_history"].append(("human", prompt))
            st.session_state["chat_history"].append(("ai", result))
            
        except Exception as e:
            st.error(f"Error generating response: {e}")
            formatted_response = "Sorry, I encountered an error while generating a response. Please try again."
            
            # Still update session state for error case
            st.session_state["user_prompt_history"].append(prompt)
            st.session_state["chat_answers_history"].append(formatted_response)

# Display chat history with consistent variable names
if st.session_state["chat_answers_history"]:
    for generated_response, user_query in zip(st.session_state["chat_answers_history"], st.session_state["user_prompt_history"]):
        st.chat_message("user").write(user_query)
        st.chat_message("assistant").write(generated_response)