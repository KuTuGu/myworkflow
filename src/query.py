from langchain.tools import tool
from ddgs import DDGS
from langfuse import Langfuse
from typing import List, Dict, Optional
import time

@tool
def text_search(
    query: str, 
    region: str = "us-en", 
    safesearch: str = "moderate",
    timelimit: Optional[str] = None,
    max_results: int = 20,
) -> List[Dict]:
    """
    文本搜索 - 最常用的搜索功能
    
    Args:
        query: 搜索关键词
        region: 搜索区域 (默认: "us-en" 英语)
            - "us-en": 美国英语
            - "cn-zh": 中国中文
        safesearch: 安全搜索级别
            - "on": 严格模式
            - "moderate": 中等模式 (默认)
            - "off": 关闭安全搜索
        timelimit: 时间限制
            - "d": 过去一天
            - "w": 过去一周
            - "m": 过去一月
            - "y": 过去一年
        max_results: 最大返回结果数量 (默认: 20)
            
    Returns:
        List[Dict]: 搜索结果列表，每个结果包含:
            - title: 标题
            - href: 链接
            - body: 内容摘要
    """
    try:
        results = ddgs.text(
            keywords=query,
            region=region,
            safesearch=safesearch,
            timelimit=timelimit,
            max_results=max_results
        )
        return list(results)
    except Exception as e:
        return [{"error": f"搜索失败: {str(e)}"}]

@tool
def news_search(
    query: str, 
    region: str = "us-en",
    timelimit: Optional[str] = None,
    max_results: int = 20,
) -> List[Dict]:
    """
    新闻搜索
    
    Args:
        query: 搜索关键词
        region: 搜索区域
        timelimit: 时间限制
        max_results: 最大返回结果数量 (默认: 20)
        
    Returns:
        List[Dict]: 新闻搜索结果
    """
    try:
        results = ddgs.news(
            keywords=query,
            region=region,
            timelimit=timelimit,
            max_results=max_results
        )
        return list(results)
    except Exception as e:
        return [{"error": f"新闻搜索失败: {str(e)}"}]

@tool
def image_search(
    query: str, 
    safesearch: str = "moderate",
    size: Optional[str] = None,
    color: Optional[str] = None,
    type_image: Optional[str] = None,
    max_results: int = 20,
) -> List[Dict]:
    """
    图片搜索
    
    Args:
        query: 搜索关键词
        safesearch: 安全搜索级别
        size: 图片尺寸
            - "small", "medium", "large", "wallpaper"
        color: 图片颜色
            - "color", "black", "transparent", "red", etc.
        type_image: 图片类型
            - "photo", "clipart", "gif", "transparent"
        max_results: 最大返回结果数量 (默认: 20)

    Returns:
        List[Dict]: 图片搜索结果，包含图片URL等信息
    """
    try:
        results = ddgs.images(
            keywords=query,
            safesearch=safesearch,
            size=size,
            color=color,
            type_image=type_image,
            max_results=max_results
        )
        return list(results)
    except Exception as e:
        return [{"error": f"图片搜索失败: {str(e)}"}]
