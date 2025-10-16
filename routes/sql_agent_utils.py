import os
import re
import pandas as pd
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI
from langchain.agents.agent_types import AgentType

def decode_raw_df(raw_df: pd.DataFrame, key_df: pd.DataFrame) -> pd.DataFrame:
    """
    Replace coded values in raw_df using mappings from key_df
    Returns a decoded version of the DataFrame
    """
    decoded_df = raw_df.copy()

    # Step 1: Build mapping dictionary {Qx: {code: label}}
    code_map = {}
    current_qid = None

    for _, row in key_df.iterrows():
        qid = str(row[0]).strip() if pd.notna(row[0]) else ""
        label = str(row[1]).strip() if pd.notna(row[1]) else ""

        if re.match(r"^Q\d+$", qid):
            current_qid = qid
            code_map[current_qid] = {}
        elif current_qid and qid and label:
            code_map[current_qid][str(qid)] = label

    # Step 2: Replace in raw_df
    for qid, mapping in code_map.items():
        if qid in decoded_df.columns:
            decoded_df[qid] = decoded_df[qid].astype(str).map(mapping).fillna(decoded_df[qid])

    return decoded_df


def run_sql_agent(user_query: str, raw_df: pd.DataFrame, key_df: pd.DataFrame):

    # ✅ Decode values using Answer Key
    decoded_df = decode_raw_df(raw_df, key_df)

    # ✅ Build Q-code → question label mapping
    question_map = {}
    current_qid = None
    for _, row in key_df.iterrows():
        qid = str(row[0]).strip() if pd.notna(row[0]) else ""
        label = str(row[1]).strip() if pd.notna(row[1]) else ""
        if re.match(r"^Q\d+$", qid):
            current_qid = qid
            question_map[current_qid] = label

    # ✅ Build reference table for agent
    question_reference = "\n".join([f"- {qid}: {label}" for qid, label in question_map.items()])

    # ✅ Construct a context-injected user prompt
    prompt = f"""
        You are analyzing a survey dataset where questions are named like Q1, Q2, etc.

        Here is what each question means:
        {question_reference}

        The responses in the table are decoded (i.e., they contain full text labels like 'Operations', not numbers).

        Now, answer the following question using the DataFrame:
        {user_query}
            """

    # ✅ Build the LangChain agent
    agent = create_pandas_dataframe_agent(
        ChatOpenAI(
            temperature=0,
            model="gpt-4o",
            openai_api_key=os.getenv("OPENAI_API_KEY")
        ),
        decoded_df,
        verbose=True,
        agent_type=AgentType.OPENAI_FUNCTIONS,
        allow_dangerous_code=True
    )

    # ✅ Run it
    try:
        return agent.run(prompt)
    except Exception as e:
        return f"❌ Error running SQL Agent: {str(e)}"