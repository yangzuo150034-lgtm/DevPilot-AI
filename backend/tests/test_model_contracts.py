"""Exercise real LangChain/Deep Agents adapters with a scripted local model, never an API."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.agents.models import RoleModels
from app.repositories import DEMO_FILES


class ScriptedModel(BaseChatModel):
    responses: list[AIMessage]

    @property
    def _llm_type(self):
        return "scripted-local-contract-test"

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=self.responses.pop(0))])


def message(name, arguments):
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": arguments, "id": "call-1"}],
        usage_metadata={"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
    )


def test_langchain_structured_plan_adapter(settings):
    adapter = RoleModels(settings, "demo", lambda *args: None)
    adapter.provider = "openai"
    adapter.model = ScriptedModel(
        responses=[message("Plan", {"steps": ["Inspect code"], "rationale": "Test"})]
    )
    assert adapter.plan("Fix add")["steps"] == ["Inspect code"]
    assert adapter.usage.snapshot()["input_tokens"] == 20


def test_deepagents_structured_patch_adapter(settings):
    adapter = RoleModels(settings, "demo", lambda *args: None)
    adapter.provider = "openai"
    adapter.model = ScriptedModel(
        responses=[
            message(
                "Proposal",
                {
                    "summary": "Fix sum",
                    "edits": [
                        {"path": "calculator.py", "old": "return a - b", "new": "return a + b"}
                    ],
                },
            )
        ]
    )
    proposal = adapter.code("Fix add", "calculator.py source", DEMO_FILES, deep=True, demo=False)
    assert proposal["edits"][0]["new"] == "return a + b"
    assert adapter.usage.calls == 1
