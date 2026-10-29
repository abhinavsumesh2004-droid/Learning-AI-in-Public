from typing import Annotated, TypedDict

from dotenv import load_dotenv
from groq import Groq

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

import sqlite3
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.runnables import RunnableConfig

conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
memory = SqliteSaver(conn)




class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    category: str
    retry_count: int
    query:str




load_dotenv()

client = Groq()
MODEL = "openai/gpt-oss-120b"


def ask(prompt):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    return (response.choices[0].message.content or "").strip()

query = input("Enter query: ")




def classify(state: AgentState):

    query = state["query"]

    prompt = f"""
    Classify the following user query into exactly one
    of these categories:

    - research
    - casual

    User query:
    {query}

    Return ONLY the category name.

    If the question is any personal question like
    name of the user etc, return research.
    """

    category = ask(prompt).lower()

    return {
        "category": category,
        "messages": [
            {
                "role": "ai",
                "content": f"Classification: {category}"
            }
        ],
        "query":query
    }



def cat_router(state: AgentState):

    category = state["category"]

    if category == "research":
        return "research"

    elif category == "casual":
        return "casual"

    else:
        return "retry"


def llm(state: AgentState):

    query = state["query"]

    answer = ask(query)

    return {
        "messages": [
            {
                "role": "ai",
                "content": answer
            }
        ]
    }




def research(state: AgentState):

    return {
        "messages": [
            {
                "role": "ai",
                "content": "The user is Abhinav"
            }
        ]
    }




def check(state: AgentState):

    return {
        "retry_count": state["retry_count"] + 1
    }



def retry_router(state: AgentState):

    if state["retry_count"] >= 2:
        return "reject"

    return "continue"




graph = StateGraph(AgentState)

# Nodes
graph.add_node("classify", classify)
graph.add_node("llm", llm)
graph.add_node("research", research)
graph.add_node("check", check)


graph.add_edge(START, "classify")


graph.add_conditional_edges(
    "classify",
    cat_router,
    {
        "casual": "llm",
        "research": "research",
        "retry": "check"
    }
)


graph.add_edge("llm", END)
graph.add_edge("research", END)


graph.add_conditional_edges(
    "check",
    retry_router,
    {
        "reject": END,
        "continue": "classify"
    }
)


checkpointer = InMemorySaver()



graph = graph.compile(checkpointer=memory)


config: RunnableConfig = {"configurable": {"thread_id": "3"}}

result = graph.invoke({
    "messages": [
        {
            "role": "user",
            "content": query
        }
    ],
    "category": "",
    "retry_count": 0,
    "query":query
},config)


print("\nFINAL STATE:")
#print(result)

print(graph.get_state(config))