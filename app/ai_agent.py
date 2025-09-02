
import streamlit as st
from smol.agent import Agent
from smol.language_model import LanguageModel

def main():
    st.header("🤖 AI Agent")

    # Get the user's prompt
    prompt = st.text_area("Enter your prompt for the AI agent:")

    if st.button("Run Agent"):
        if prompt:
            # Create a language model
            model = LanguageModel(provider="huggingface", model="gpt2")

            # Create an agent
            agent = Agent(model=model)

            # Run the agent
            with st.spinner("Running the AI agent..."):
                output = agent.run(prompt)

            # Display the output
            st.subheader("Agent Output")
            st.write(output)
        else:
            st.warning("Please enter a prompt for the AI agent.")
