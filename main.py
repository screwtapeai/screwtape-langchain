"""LangChain agent + Screwtape judge step (pass -> return, retry -> redo with reasons, fail -> stop),
plus an optional consensus step across several independent samples.

pip install -r requirements.txt
export OPENAI_API_KEY=...  SCREWTAPE_API_KEY=...
python main.py            # judge loop
python main.py --consensus  # 3 samples -> consensus -> judge
"""
import sys

from langchain.agents import create_agent

from screwtape import consensus, judge

TASK = "State the crew size and launch site of the mission."
EVIDENCE = ["The mission launched on 2024-03-01 from Cape Canaveral.", "The crew size was 4."]
CRITERIA = ["crew size", "Cape Canaveral"]
MAX_ATTEMPTS = 3

agent = create_agent(
    "openai:gpt-4o-mini",
    tools=[],
    system_prompt="Answer only from the evidence you are given. Be brief.",
)


def ask(feedback: list[str] | None = None) -> str:
    prompt = f"Task: {TASK}\nEvidence:\n- " + "\n- ".join(EVIDENCE)
    if feedback:
        prompt += "\nA reviewer rejected your last answer because:\n- " + "\n- ".join(feedback)
    result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
    return result["messages"][-1].text


def judged_answer() -> str | None:
    feedback = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        output = ask(feedback)
        v = judge(TASK, output, EVIDENCE, CRITERIA)
        print(f"attempt {attempt}: {v['verdict']} score={v['score']} engine={v['engine']} id={v['request_id']} receipt={(v.get('receipt') or {}).get('receipt_id', '-')}")
        if v["verdict"] == "pass":
            return output
        if v["verdict"] == "fail":
            return None          # wrong, not fixable: stop spending calls
        feedback = v["reasons"]  # retry: feed the reasons back
    return None


def consensus_then_judge(n: int = 3) -> str | None:
    answers = [{"agent_id": f"sample-{i}", "output": ask()} for i in range(n)]
    c = consensus(TASK, answers)
    print(f"agreement={c['agreement_score']} risk={c['false_consensus_risk']}")
    v = judge(TASK, c["consensus_answer"], EVIDENCE, CRITERIA)  # never trust the vote alone
    print(f"judge: {v['verdict']} {v['reasons']}")
    return c["consensus_answer"] if v["verdict"] == "pass" else None


if __name__ == "__main__":
    answer = consensus_then_judge() if "--consensus" in sys.argv else judged_answer()
    print("ANSWER:", answer if answer is not None else "(rejected)")
