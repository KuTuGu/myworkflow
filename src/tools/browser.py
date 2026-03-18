from smolagents.vision_web_browser import search_item_ctrl_f, go_back, close_popups
from smolagents.vision_web_browser import helium_instructions, save_screenshot
from selenium import webdriver
from helium import helium
from selenium.webdriver.common.action_chains import ActionChains
from smolagents import tool

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--force-device-scale-factor=1")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-pdf-viewer")
chrome_options.add_argument("--window-position=0,0")
global driver
driver = helium.start_chrome(headless=True, options=chrome_options)

@tool
def scale_down(times: int) -> None:
    """
    Scale down the browser view to see more content by simulating Ctrl+minus key combinations.

    Args:
        times: Number of times to perform the scale down operation.
        Each time simulates one Ctrl+minus key press.
    """
    actions = ActionChains(driver)

    # Ctrl -，模拟缩小操作
    for _ in range(times):
        actions.key_down(Keys.CONTROL).send_keys(Keys.SUBTRACT).key_up(Keys.CONTROL)

    actions.perform()

browser_tools = [
    search_item_ctrl_f, 
    go_back,
    close_popups,
    scale_down,
]
