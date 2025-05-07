from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import uvicorn
import logging
import time
import asyncio
import os
from dotenv import load_dotenv
import base64
from io import BytesIO
from PIL import Image
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI app
app = FastAPI(title="E-commerce Test Automation API")

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000",'http://127.0.0.1:5500'],  # Only allow your frontend's origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
if not load_dotenv():
    logger.error("Failed to load .env file. Ensure .env exists in the project root.")
    raise RuntimeError("Missing .env file or incorrect path")

# Debug environment variables
logger.info(f"Loaded env: BASE_URL={os.getenv('BASE_URL')}, EMAIL={os.getenv('EMAIL')}, "
            f"PASSWORD={os.getenv('PASSWORD')}, PRODUCT_URL={os.getenv('PRODUCT_URL')}")

# Pydantic model for test inputs with environment variable defaults
class TestInput(BaseModel):
    url: str = os.getenv("BASE_URL")
    username: str = os.getenv("EMAIL")
    password: str = os.getenv("PASSWORD")
    product_url: str = os.getenv("PRODUCT_URL")

    # Validate that required fields are provided
    def __init__(self, **data):
        super().__init__(**data)
        if not self.url or not self.username or not self.password or not self.product_url:
            missing = [k for k, v in self.dict().items() if v is None]
            raise ValueError(f"Missing required environment variables: {missing}")

# Initialize Selenium WebDriver
def init_driver():
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(15)
    return driver

# Capture a screenshot and return it as a base64 string
def capture_screenshot(driver):
    screenshot = driver.get_screenshot_as_png()
    image = Image.open(BytesIO(screenshot))
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# Test case: Login to e-commerce website
async def test_login(driver, url, username, password):
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)

        wait.until(EC.element_to_be_clickable((By.ID, "joinBTn"))).click()
        await asyncio.sleep(2)

        wait.until(EC.element_to_be_clickable((By.ID, "sign-in-tab-tab-email"))).click()
        await asyncio.sleep(2)

        wait.until(EC.presence_of_element_located((By.NAME, "email"))).send_keys(username)
        await asyncio.sleep(1)

        wait.until(EC.presence_of_element_located((By.NAME, "email-pass"))).send_keys(password)
        await asyncio.sleep(1)

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))).click()

        # Wait for login success by checking for a post-login element (change selector as needed)
        wait.until(EC.presence_of_element_located((By.ID, "cart-icon")))  # Example: change to a real post-login element

        logger.info("Login test passed")
        return {"status": "success", "message": "Login successful"}
    except Exception as e:
        logger.error(f"Login test failed: {str(e)}")
        return {"status": "failed", "message": str(e), "screenshot": capture_screenshot(driver)}

# Test case: Add product to cart and proceed to checkout
async def test_add_to_cart_step1(driver, product_url):
    try:
        driver.get(product_url)
        wait = WebDriverWait(driver, 15)

        plus_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-plus")))
        plus_button.click()
        await asyncio.sleep(2)

        add_to_cart_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "product-buy-icon")))
        add_to_cart_button.click()
        await asyncio.sleep(5)

        cart_container = wait.until(EC.element_to_be_clickable((By.ID, "cart-icon")))
        cart_container.click()
        await asyncio.sleep(2)

        checkout_button = wait.until(EC.element_to_be_clickable((By.ID, "start-checkout")))
        checkout_button.click()
        await asyncio.sleep(5)

        return {"status": "success", "message": "Item added and moved to checkout"}

    except Exception as e:
        logger.error(f"Add to cart step failed: {str(e)}")
        return {"status": "failed", "message": str(e), "screenshot": capture_screenshot(driver)}
    
async def test_checkout_step2(driver):
    try:
        wait = WebDriverWait(driver, 15)

        tab_triggers = driver.find_elements(By.CSS_SELECTOR, "li[data-index]")
        for trigger in tab_triggers:
            try:
                index = trigger.get_attribute("data-index")
                logger.info(f"Processing tab with data-index='{index}'")

                index_li = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f"li[data-index='{index}']")))
                index_li.click()
                logger.info(f"Clicked tab with data-index='{index}'")
                await asyncio.sleep(2)

                tab_panel = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.tab-content div.tab-pane[aria-hidden='false']"))
                )

                slot_buttons = tab_panel.find_elements(By.CSS_SELECTOR, "div.tableRow div.tableColumn button[class*='slot-']")
                if not slot_buttons:
                    logger.info(f"No slot buttons in tab {index}")
                    continue

                for slot_button in slot_buttons:
                    try:
                        button_classes = slot_button.get_attribute("class") or ""
                        is_enabled = slot_button.is_enabled()
                        is_disabled_attribute = slot_button.get_attribute("disabled") is not None
                        has_disabled_class = "disabledButton" in button_classes

                        if has_disabled_class or not is_enabled or is_disabled_attribute:
                            continue

                        wait.until(EC.element_to_be_clickable(slot_button)).click()
                        await asyncio.sleep(2)

                        wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-oos-option"))).click()
                        await asyncio.sleep(2)

                        wait.until(EC.element_to_be_clickable((By.ID, "Comments"))).send_keys("Developer Automat Test")
                        await asyncio.sleep(2)

                        wait.until(EC.element_to_be_clickable((By.ID, "processCheckout"))).click()
                        await asyncio.sleep(5)

                        return {"status": "success", "message": "Checkout completed"}

                    except Exception as e:
                        logger.error(f"Slot button error in tab {index}: {str(e)}")
                        continue

            except Exception as e:
                logger.error(f"Tab processing error: {str(e)}")
                continue

        return {"status": "failed", "message": "No available slot found", "screenshot": capture_screenshot(driver)}

    except Exception as e:
        logger.error(f"Checkout step failed: {str(e)}")
        return {"status": "failed", "message": str(e), "screenshot": capture_screenshot(driver)}

# FastAPI endpoint to run tests
@app.post("/run-tests")
async def run_tests(test_input: TestInput):
    driver = init_driver()
    try:
        results = {}

        if test_input.username and test_input.password:
            results["login"] = await test_login(driver, test_input.url, test_input.username, test_input.password)

        if test_input.product_url:
            results["add_to_cart"] = await test_add_to_cart_step1(driver, test_input.product_url)

        if test_input.product_url:
            results["checkout"] = await test_checkout_step2(driver)    

        if not results:
            raise HTTPException(status_code=400, detail="No tests specified")

        return results
    finally:
        driver.quit()

# Run the FastAPI server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
