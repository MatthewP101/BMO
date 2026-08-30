from app.tools.system_tools import get_current_time


TOOLS = {
    "get_current_time": get_current_time,
}


def run_tool(tool_name):
    tool = TOOLS.get(tool_name)

    if tool is None:
        return "Tool not found."

    return tool()