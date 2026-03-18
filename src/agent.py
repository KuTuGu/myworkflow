from smolagents import OpenAIModel, CodeAgent, ToolCallingAgent
from smolagents import WebSearchTool, WikipediaSearchTool, VisitWebpageTool, FinalAnswerTool
from tools import MarkItDownTool, DownloadTool, browser_tools
from tools.browser import helium_instructions, save_screenshot
import os

api_key = os.environ["OPENAI_API_KEY"]
api_base = os.environ["OPENAI_URL"]
model_id = os.environ["OPENAI_MODEL"]

model = OpenAIModel(
    model_id=model_id,
    api_base=api_base,
    api_key=api_key,
    temperature=0.7,
    max_tokens=100000,
    top_p=0.9,
)
markitdown = MarkItDownTool(api_key, api_base, model_id)

websearch_agent = ToolCallingAgent(
    tools=[WebSearchTool(), WikipediaSearchTool(), VisitWebpageTool()],
    model=model,
    name="web_search_agent",
    description="网络信息搜集者",
    max_steps=20,
    instructions="""
        请尽量搜索英语资料，搜索时请注意规划搜索顺序，而不是直接根据输入全局搜索；
        比如用户询问最近某个领域的趋势，你应该先确定搜索时间范围，再确定这个领域的核心网站是什么，
        如代码问题，优先在github、stackoverflow网站搜索。最后再根据时间和核心网站进行搜索。
    """,
)

webbrowser_agent = CodeAgent(
    tools=[VisitWebpageTool()] + browser_tools,
    model=model,
    additional_authorized_imports=["helium"],
    step_callbacks=[save_screenshot],
    name="webbrowser_agent",
    description="网页浏览者",
    max_steps=20,
    verbosity_level=2,
    instructions=helium_instructions + """
        你是一个浏览器控制agent，你可以使用BrowserTool来浏览当前页面、搜索文本、关闭弹窗，返回上一页等；
        注意：浏览超出屏幕的内容时，优先使用scale_down而不是滚动窗口，只有当scale_down缩小的内容你无法识别时，才考虑滚动窗口；
        还有不要忘了helium，它为你提供了更多页面操作。
    """,
)
webbrowser_agent.python_executor("from helium import *")

file_agent = ToolCallingAgent(
    tools=[DownloadTool(), markitdown],
    model=model,
    name="file_agent",
    description="文件处理者",
    max_steps=5,
    instructions="对于网络或截屏文件，请先使用download tool下载文件，再使用markitdown tool。",
)

root_agent = CodeAgent(
    model=model, add_base_tools=True, name="root_agent", description="管理者",
    tools=[FinalAnswerTool()], managed_agents=[websearch_agent, webbrowser_agent, file_agent],
    additional_authorized_imports=["datetime", "time", "math", "re"],
    instructions="""
        你是一个管理者，手下有许多聪明的agents，你可以统筹它们来回答用户的问题，注意回答时请始终保持中文。
        你可以创建多个agent来并行执行不同的任务，另一方面这也有助于控制成本，避免一个agent上下文过长。
        比如对于两个搜索问题，你应该思考拆分是否更有助于快速找到答案，而不是把搜索问题直接交给一个websearch_agent处理。
    """,
)
