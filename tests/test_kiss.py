import pytest

# Skip the entire module if the optional kiss_agent_framework is not installed.
kiss = pytest.importorskip("kiss_agent_framework", reason="kiss_agent_framework is not installed")


def test_kiss_agent():
    agent = kiss.Agent(name="test_agent", instructions="You are a helpful assistant.")
    response = agent.run("سلام! وضعیت هوش مصنوعی چطور است؟")
    print(response)
