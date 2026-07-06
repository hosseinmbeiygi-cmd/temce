# test_kiss.py
from kiss_agent_framework import Agent, Tool

# تعریف یک عامل ساده
agent = Agent(
    name="test_agent",
    instructions="You are a helpful assistant."
)

# اجرای عامل با یک پیام
response = agent.run("سلام! وضعیت هوش مصنوعی چطور است؟")
print(response)