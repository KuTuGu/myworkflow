from smolagents import OpenAIModel, CodeAgent, ToolCallingAgent
from smolagents import WebSearchTool, WikipediaSearchTool, VisitWebpageTool
from tools import MarkItDownTool, DownloadTool, browser_tools
from tools.browser import helium_instructions, save_screenshot
from skills import skills
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
web_tools = [WebSearchTool(), WikipediaSearchTool(), VisitWebpageTool()]
browser_tools = [VisitWebpageTool()] + browser_tools
file_tools = [DownloadTool(), markitdown]

MAX_EXECUTION_TIME_SECONDS = 600 # 10 mins
executor_kwargs = {
    "timeout_seconds": MAX_EXECUTION_TIME_SECONDS,
}

websearch_agent = CodeAgent(
    tools=web_tools + file_tools,
    add_base_tools=True,
    skills=skills,
    model=model,
    name="web_search_agent",
    description="网络信息搜集者",
    max_steps=20,
    executor_kwargs=executor_kwargs,
    instructions="""
        你是一个支持网络的多模态agent，可以搜索、读取各种多媒体资料，请尽量以英语资料为主；
        搜索时请注意规划搜索顺序，而不是直接根据完整输入进行搜索；
        比如用户询问最近某个领域的趋势，你应该先确定搜索时间范围，再确定这个领域的核心网站是什么；
        如果是代码问题，优先在github、stackoverflow网站搜索；最后再根据时间和核心网站进行搜索。
    """,
)

webbrowser_agent = CodeAgent(
    additional_authorized_imports=["helium"],
    tools=browser_tools + file_tools,
    add_base_tools=True,
    skills=skills,
    model=model,
    step_callbacks=[save_screenshot],
    name="webbrowser_agent",
    description="网页浏览者",
    executor_kwargs=executor_kwargs,
    verbosity_level=2,
    instructions=helium_instructions + """
        你是一个浏览器控制的多模态agent，你可以使用BrowserTool来浏览当前页面、搜索文本、关闭弹窗，返回上一页等；
        注意：浏览超出屏幕的内容时，优先使用scale_down而不是滚动窗口，只有当scale_down缩小的内容你无法识别时，才考虑滚动窗口；
        还有不要忘了helium，它为你提供了更多页面操作。
    """,
)
webbrowser_agent.python_executor("from helium import *")

local_agent = CodeAgent(
    additional_authorized_imports=["*"],
    tools=file_tools,
    add_base_tools=True,
    skills=skills,
    model=model,
    name="local_agent",
    description="本地工具调用",
    executor_kwargs=executor_kwargs,
    instructions="""
        你是一个本地工作的多模态agent，无法在网络搜索资料，只能利用本地的工具完成任务；
        利用本地工具，通过编排、规划，将复杂逻辑编码为python代码，快速完成任务。
    """,
)

root_agent = CodeAgent(
    additional_authorized_imports=["*"],
    managed_agents=[websearch_agent, webbrowser_agent, local_agent],
    tools=file_tools,
    add_base_tools=True,
    skills=skills,
    model=model,
    name="工作流",
    description="Agent管理者",
    executor_kwargs=executor_kwargs,
    instructions="""
        你是一个管理者，手下有支持多模态的agents，你可以统筹它们来回答用户的问题，注意回答时请始终保持中文。
        你可以创建多个agent来并行执行不同的任务，另一方面这也有助于控制成本，避免一个agent上下文过长。

        通过将复杂查询分解为子问题、执行迭代搜索并综合得出全面答案，执行多步骤深度研究。
        要对收集的资料来源进行追踪和引用管理，对不同信息来源使用不同置信度，
        汇总完子代理的研究成果后，综合成连贯的答案，最好生成数据分析的代码执行。具体步骤如下：
        1. 将模糊问题拆解为可执行的子问题，有需要的话创建一个子agent，检索该问题下的多个子主题；
        2. 根据不同的主题，创建不同的agents，并行收集资料，要求agents返回资料和引用来源；
        3. 根据中间的搜索结果，动态调整搜索策略和agents行为，增加或减少agent等；
        4. 对每个主题的资料进行整理，进行时间线梳理与因果推断等，合并重复的内容，检测并解决冲突，以置信度高的资料为主；
        5. 汇总完成后，根据主题生成不同层级的摘要、内容；
        6. 为了方便理解，尽可能使用结构化输出（表格、时间轴），展示具体数据分析。
    """,
)
