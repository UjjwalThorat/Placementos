"""Generic agent loop — Groq backend, Anthropic-shaped interface.
Every agent = system prompt + tools + this loop."""
import os, json
from groq import Groq

MODEL = os.environ.get("PLACEMENTOS_MODEL", "llama-3.3-70b-versatile")


class _Block:
    def __init__(self, **kw): self.__dict__.update(kw)


class _Response:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason


class _Messages:
    def __init__(self, g): self.g = g

    def create(self, model, max_tokens, system, messages, tools=None):
        oai = [{"role": "system", "content": system}]
        for m in messages:
            if m["role"] == "user":
                if isinstance(m["content"], str):
                    oai.append({"role": "user", "content": m["content"]})
                else:
                    for b in m["content"]:
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            oai.append({"role": "tool",
                                        "tool_call_id": b["tool_use_id"],
                                        "content": b["content"]})
            elif m["role"] == "assistant":
                texts, calls = [], []
                for b in m["content"]:
                    if getattr(b, "type", None) == "text":
                        texts.append(b.text)
                    elif getattr(b, "type", None) == "tool_use":
                        calls.append({"id": b.id, "type": "function",
                                      "function": {"name": b.name,
                                                   "arguments": json.dumps(b.input)}})
                am = {"role": "assistant", "content": "\n".join(texts) or None}
                if calls: am["tool_calls"] = calls
                oai.append(am)

        # kw = {"model": model, "max_tokens": max_tokens, "messages": oai}
        kw = {"model": model, "max_tokens": max_tokens, "messages": oai, "temperature": 0}
        
        if tools:
            kw["tools"] = [{"type": "function",
                            "function": {"name": t["name"],
                                         "description": t["description"],
                                         "parameters": t["input_schema"]}}
                           for t in tools]

        # r = self.g.chat.completions.create(**kw)
        r = self.g.chat.completions.create(**kw,tool_choice="auto")
        msg = r.choices[0].message
        blocks = []
        if msg.content:
            blocks.append(_Block(type="text", text=msg.content))
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                blocks.append(_Block(type="tool_use", id=tc.id,
                                     name=tc.function.name, input=args))
        stop = "tool_use" if msg.tool_calls else "end_turn"
        return _Response(blocks, stop)


class _Client:
    def __init__(self):
        key = os.environ.get("GROQ_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        self.g = Groq(api_key=key)
        self.messages = _Messages(self.g)


def client():
    return _Client()


def run_agent(system_prompt, user_message, tools, tool_impls,
              max_turns=6, model=None):
    messages = [{"role": "user", "content": user_message}]
    trace = []
    for _ in range(max_turns):
        resp = client().messages.create(
            model=model or MODEL, max_tokens=1500,
            system=system_prompt, tools=tools, messages=messages,
        )
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        texts = [b.text for b in resp.content if b.type == "text"]
        if resp.stop_reason == "end_turn" or not tool_uses:
            return {"answer": "\n".join(texts).strip(), "trace": trace}
        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for tu in tool_uses:
            impl = tool_impls.get(tu.name)
            try:
                result = impl(**tu.input) if impl else {"error": f"unknown tool {tu.name}"}
            except Exception as e:
                result = {"error": str(e)}
            trace.append({"tool": tu.name, "input": tu.input, "output": result})
            tool_results.append({"type": "tool_result",
                                 "tool_use_id": tu.id,
                                 "content": json.dumps(result, default=str)})
        messages.append({"role": "user", "content": tool_results})
    return {"answer": "(agent exceeded max turns)", "trace": trace}