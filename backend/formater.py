import json
from pprint import pformat


def content_to_text(content):
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if "text" in item:
                    parts.append(item["text"])
                elif "content" in item:
                    parts.append(str(item["content"]))
            else:
                parts.append(str(item))
        return "\n".join(parts)

    return str(content)


def tidy_message(msg):
    return {
        "type": msg.__class__.__name__,
        "content": content_to_text(getattr(msg, "content", "")),
        "tool_calls": [
            {
                "name": call.get("name"),
                "args": call.get("args"),
            }
            for call in getattr(msg, "tool_calls", []) or []
        ],
    }


def tidy_agent_result(result):
    if not isinstance(result, dict):
        return pformat(result, width=120)

    tidy = {}

    if "__interrupt__" in result:
        tidy["interrupt"] = str(result["__interrupt__"])

    if "messages" in result:
        tidy["messages"] = [
            tidy_message(msg)
            for msg in result["messages"]
        ]

    for key, value in result.items():
        if key not in ["messages", "__interrupt__"]:
            tidy[key] = str(value)

    return json.dumps(tidy, indent=2, ensure_ascii=False)